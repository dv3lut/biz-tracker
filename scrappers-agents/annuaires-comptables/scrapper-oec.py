#!/usr/bin/env python3
"""
=============================================================================
 SCRAPER ANNUAIRE OEC - Experts-Comptables France  (v3)
 Source : annuaire.experts-comptables.org
=============================================================================

 INSTALLATION :
   pip install requests beautifulsoup4 lxml

 UTILISATION :
   python scraper_oec.py

 Au démarrage, le script propose 4 modes :
   1 → Collecte URLs + scraping complet (premier lancement)
   2 → Scraping seul (reprend la liste d'URLs déjà collectée)
   3 → Stats uniquement (affiche les stats du CSV actuel)
   4 → Scan IDs séquentiels (mode secours)

 CHAMPS CSV :
   id, nom_cabinet, adresse, code_postal, ville, latitude, longitude,
   telephone, type_tel, site_web, langues, membres, url_fiche, date_scraping

 SOURCES DE DONNÉES (confirmées sur le site réel) :
   - Téléphone, adresse, CP, ville, GPS → JSON-LD <script type="application/ld+json">
   - Site web                           → section "Nos sites" (lien "Site web")
   - Langues, membres                   → HTML de la fiche

 STATS EN FIN DE SCRAPING :
   - % cabinets avec site web
   - % cabinets avec téléphone
   - Répartition mobile (06/07) / fixe (01-05) / autre
=============================================================================
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import random
import re
import os
import sys
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

BASE_URL = "https://annuaire.experts-comptables.org"

DELAY_MIN   = 0.7   # Délai minimum entre requêtes (secondes)
DELAY_MAX   = 2.0   # Délai maximum entre requêtes (secondes)
MAX_RETRIES = 3
RETRY_DELAY = 10    # Délai entre tentatives en cas d'erreur (secondes)

OUTPUT_CSV            = "cabinets_oec.csv"
PROGRESS_URLS_FILE    = "progress_cabinet_urls.json"
PROGRESS_SCRAPED_FILE = "progress_scraped_ids.json"

EXCLUDED_DOMAINS = [
    "experts-comptables.org", "experts-comptables.fr",
    "linkedin.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "x.com", "t.co",
]

CSV_FIELDS = [
    "id", "nom_cabinet", "adresse", "code_postal", "ville",
    "latitude", "longitude",
    "telephone", "type_tel",
    "site_web", "langues", "membres",
    "url_fiche", "date_scraping",
]

REGIONS = [
    "auvergne-rhone-alpes", "bourgogne-franche-comte", "bretagne",
    "centre-val-de-loire", "corse", "grand-est", "guadeloupe", "guyane",
    "hauts-de-france", "ile-de-france", "la-reunion", "martinique",
    "mayotte", "normandie", "nouvelle-aquitaine", "occitanie",
    "pays-de-la-loire", "provence-alpes-cote-d-azur",
]

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_oec.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  SESSION HTTP
# ─────────────────────────────────────────────

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
})


# ─────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────

def polite_delay():
    """Pause aléatoire entre 0.7 et 2.0 secondes."""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def fetch(url, retries=MAX_RETRIES):
    """GET avec relances automatiques."""
    for attempt in range(1, retries + 1):
        try:
            polite_delay()
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = RETRY_DELAY * attempt
                log.warning(f"Rate limited (429). Attente {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 404:
                return None
            else:
                log.warning(f"HTTP {resp.status_code} pour {url} (tentative {attempt}/{retries})")
                time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            log.warning(f"Erreur réseau ({e}) — tentative {attempt}/{retries}")
            time.sleep(RETRY_DELAY)
    log.error(f"Échec définitif : {url}")
    return None


def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_csv_row(filepath, row, fieldnames):
    write_header = not os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def extract_cabinet_id(url):
    m = re.search(r"/expert-comptable/(\d+)-", url)
    return m.group(1) if m else url


# ─────────────────────────────────────────────
#  CLASSIFICATION DU TÉLÉPHONE
# ─────────────────────────────────────────────

def classify_phone(phone):
    """
    Classifie un numéro de téléphone français.
    Retourne : "mobile" | "fixe" | "autre" | ""
    """
    if not phone:
        return ""
    normalized = re.sub(r"[\s\.\-\(\)]", "", phone)
    normalized = re.sub(r"^\+33", "0", normalized)
    if re.match(r"^0[67]", normalized):
        return "mobile"
    elif re.match(r"^0[1-5]", normalized):
        return "fixe"
    return "autre"


# ─────────────────────────────────────────────
#  PARSING D'UNE FICHE CABINET
# ─────────────────────────────────────────────

def parse_cabinet_page(html, url):
    """
    Extrait toutes les données d'une fiche cabinet.

    Stratégie principale : JSON-LD <script type="application/ld+json">
      → Contient : telephone, adresse (streetAddress), ville (addressLocality),
                   code_postal (postalCode), latitude, longitude
      → Confirmé sur le site réel (ex: EXA CONSEIL, Scionzier 74950)

    Stratégies de secours pour le téléphone (si JSON-LD absent) :
      1. Variable JS avec "phone"/"telephone" dans un <script>
      2. Attribut data-phone sur un élément HTML
      3. Lien <a href="tel:..."> dans le HTML

    Site web : section "Nos sites" → lien labélisé "Site web" uniquement
               (LinkedIn, Twitter, YouTube sont ignorés)
    """
    soup = BeautifulSoup(html, "lxml")
    data = {field: "" for field in CSV_FIELDS}
    data["url_fiche"]     = url
    data["id"]            = extract_cabinet_id(url)
    data["date_scraping"] = datetime.now().strftime("%Y-%m-%d")

    # ── 1. JSON-LD (source principale : téléphone + adresse + GPS) ──
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            ld = json.loads(script.string or "")
            if isinstance(ld, list):
                ld = ld[0]

            # Téléphone
            data["telephone"] = ld.get("telephone", "").strip()

            # Nom (si pas encore trouvé via h1)
            if not data["nom_cabinet"]:
                data["nom_cabinet"] = ld.get("name", "").strip()

            # Adresse structurée
            addr = ld.get("address", {})
            if addr:
                data["adresse"]     = addr.get("streetAddress",   "").strip()
                data["ville"]       = addr.get("addressLocality", "").strip()
                data["code_postal"] = addr.get("postalCode",      "").strip()

            # Coordonnées GPS
            geo = ld.get("geo", {})
            if geo:
                data["latitude"]  = str(geo.get("latitude",  ""))
                data["longitude"] = str(geo.get("longitude", ""))

            break  # Un seul bloc JSON-LD suffit
        except Exception:
            pass

    # ── 2. Nom depuis H1 (prioritaire sur JSON-LD si différent) ──
    h1 = soup.find("h1")
    if h1:
        data["nom_cabinet"] = h1.get_text(strip=True)

    # ── 3. Adresse de secours (si JSON-LD absent) ──
    if not data["adresse"]:
        for selector in ["address", ".cabinet-address", "[itemprop='address']"]:
            el = soup.select_one(selector)
            if el:
                adresse_raw = el.get_text(" ", strip=True)
                cp_match = re.search(r"(\d{5})\s+(.+)", adresse_raw)
                if cp_match:
                    data["code_postal"] = cp_match.group(1)
                    data["ville"]       = cp_match.group(2).strip()
                    data["adresse"]     = adresse_raw[:adresse_raw.find(cp_match.group(0))].strip()
                else:
                    data["adresse"] = adresse_raw
                break
        if not data["adresse"]:
            for st in soup.find_all("strong"):
                text = st.get_text(strip=True)
                if re.search(r"\d{5}", text):
                    cp_match = re.search(r"(\d{5})\s+(.+)", text)
                    if cp_match:
                        data["code_postal"] = cp_match.group(1)
                        data["ville"]       = cp_match.group(2).strip()
                        data["adresse"]     = text[:text.find(cp_match.group(0))].strip()
                    break

    # ── 4. Téléphone de secours (si JSON-LD absent ou sans telephone) ──
    if not data["telephone"]:
        # Secours A : variable JS ("phone" ou "telephone" dans <script>)
        for script in soup.find_all("script"):
            text = script.string or ""
            m = re.search(
                r'"(?:phone|telephone)"\s*:\s*"([0-9\s\.\-\+\(\)]{7,20})"', text
            )
            if m:
                data["telephone"] = m.group(1).strip()
                break

    if not data["telephone"]:
        # Secours B : attribut data-phone
        el = soup.find(attrs={"data-phone": True})
        if el:
            data["telephone"] = el["data-phone"].strip()

    if not data["telephone"]:
        # Secours C : lien tel:
        tel_a = soup.find("a", href=re.compile(r"^tel:"))
        if tel_a:
            data["telephone"] = tel_a["href"].replace("tel:", "").replace("%2B", "+").strip()

    # Classer le téléphone
    data["type_tel"] = classify_phone(data["telephone"])

    # ── 5. Site web ──
    # Section "Nos sites" → chercher uniquement les liens labélisés "Site web"
    nos_sites = soup.find(string=re.compile(r"Nos sites", re.I))
    if nos_sites:
        container = nos_sites.find_parent()
        for _ in range(5):
            if container and container.find_all("a", href=re.compile(r"^https?://")):
                break
            container = container.parent if container else None
        if container:
            # Priorité : liens dont le texte ou le title contient "site web"
            for a in container.find_all("a", href=True):
                href  = a["href"]
                label = a.get_text(" ", strip=True).lower()
                title = a.get("title", "").lower()
                is_social = any(d in href for d in EXCLUDED_DOMAINS)
                if (href.startswith("http") and not is_social
                        and ("site web" in label or "site web" in title)):
                    data["site_web"] = href
                    break
            # Fallback : premier lien non-social dans la section
            if not data["site_web"]:
                for a in container.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and not any(d in href for d in EXCLUDED_DOMAINS):
                        data["site_web"] = href
                        break

    # ── 6. Langues parlées ──
    lang_section = soup.find(string=re.compile(r"Langues", re.I))
    if lang_section and lang_section.parent:
        lang_text = re.sub(
            r"Langues\s*parl[ée]es?\s*", "",
            lang_section.parent.get_text(" ", strip=True),
            flags=re.I
        )
        langues = [l.strip() for l in re.split(r"[,\n]", lang_text) if l.strip()]
        data["langues"] = ", ".join(langues)

    # ── 7. Membres experts-comptables ──
    membres = []
    membre_section = soup.find(string=re.compile(r"experts-comptables.*cabinet", re.I))
    if membre_section and membre_section.parent:
        container = membre_section.parent.parent
        if container:
            for p in container.find_all(["p", "span", "div"]):
                text = p.get_text(strip=True)
                if text and len(text) < 60 and re.search(r"[A-Z]{2,}", text):
                    membres.append(text)
    data["membres"] = " | ".join(membres[:5])

    return data


# ─────────────────────────────────────────────
#  ÉTAPE 1 : COLLECTE DES URLs
# ─────────────────────────────────────────────

def get_department_urls(region_slug):
    url  = f"{BASE_URL}/tous-les-cabinets-experts-comptables-par-region/{region_slug}"
    resp = fetch(url)
    if not resp:
        return []
    soup        = BeautifulSoup(resp.text, "lxml")
    dept_prefix = f"/tous-les-cabinets-experts-comptables-par-region/{region_slug}/"
    dept_urls   = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = urlparse(href).path if href.startswith("http") else href
        if path.startswith(dept_prefix):
            remainder = path[len(dept_prefix):].strip("/")
            if remainder and "/" not in remainder:
                dept_urls.add(urljoin(BASE_URL, path))
    return list(dept_urls)


def get_city_urls(dept_url):
    resp = fetch(dept_url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    return [urljoin(BASE_URL, a["href"]) for a in soup.select("a[href*='/recherche/ville/']")]


def get_cabinet_urls_from_city(city_url):
    cabinet_urls = []
    page = 1
    while True:
        url  = city_url if page == 1 else f"{city_url}&page={page}"
        resp = fetch(url)
        if not resp:
            break
        soup  = BeautifulSoup(resp.text, "lxml")
        links = soup.select("a[href*='/expert-comptable/']")
        if not links:
            break
        new_links = [
            urljoin(BASE_URL, a["href"])
            for a in links
            if "/expert-comptable/" in a["href"]
            and urljoin(BASE_URL, a["href"]) not in cabinet_urls
        ]
        if not new_links:
            break
        cabinet_urls.extend(new_links)
        if not soup.select_one("a[href*='page=']"):
            break
        page += 1
    return list(set(cabinet_urls))


def collect_all_cabinet_urls():
    log.info("=" * 60)
    log.info("ÉTAPE 1 : Collecte des URLs de cabinets")
    log.info("=" * 60)

    progress         = load_json(PROGRESS_URLS_FILE)
    all_cabinet_urls = set(progress.get("cabinet_urls", []))
    done_cities      = set(progress.get("done_cities",  []))
    log.info(f"Reprise : {len(all_cabinet_urls):,} URLs, {len(done_cities):,} villes déjà traitées")

    for region in REGIONS:
        log.info(f"Région : {region}")
        dept_urls = get_department_urls(region)
        log.info(f"  → {len(dept_urls)} département(s)")

        for dept_url in dept_urls:
            city_urls = get_city_urls(dept_url)
            log.info(f"  {dept_url.split('/')[-1]} : {len(city_urls)} ville(s)")

            for city_url in city_urls:
                if city_url in done_cities:
                    continue
                urls      = get_cabinet_urls_from_city(city_url)
                count_new = len([u for u in urls if u not in all_cabinet_urls])
                all_cabinet_urls.update(urls)
                done_cities.add(city_url)
                city_name = (city_url.split("/ville/")[1].split("?")[0]
                             if "/ville/" in city_url else city_url)
                log.info(
                    f"    {city_name:25s} : {len(urls):4d} cabinets "
                    f"({count_new:4d} nouveaux) | Total : {len(all_cabinet_urls):,}"
                )
                save_json(PROGRESS_URLS_FILE, {
                    "cabinet_urls": list(all_cabinet_urls),
                    "done_cities":  list(done_cities),
                    "updated_at":   datetime.now().isoformat(),
                })

    log.info(f"✅ Collecte terminée : {len(all_cabinet_urls):,} URLs")
    return list(all_cabinet_urls)


# ─────────────────────────────────────────────
#  ÉTAPE 2 : SCRAPING
# ─────────────────────────────────────────────

def scrape_all_cabinets(cabinet_urls):
    log.info("=" * 60)
    log.info("ÉTAPE 2 : Scraping des fiches cabinets")
    log.info(f"Total dans la liste : {len(cabinet_urls):,} URLs")
    log.info("=" * 60)

    scraped  = load_json(PROGRESS_SCRAPED_FILE)
    done_ids = set(scraped.get("done_ids", []))
    todo     = [u for u in cabinet_urls if extract_cabinet_id(u) not in done_ids]
    log.info(f"Déjà scrapés : {len(done_ids):,} | Restants : {len(todo):,}")

    for i, url in enumerate(todo, 1):
        cabinet_id = extract_cabinet_id(url)
        resp = fetch(url)
        if not resp:
            log.warning(f"[{i}/{len(todo)}] Échec : {url}")
            done_ids.add(cabinet_id)
            continue

        row = parse_cabinet_page(resp.text, url)
        append_csv_row(OUTPUT_CSV, row, CSV_FIELDS)
        done_ids.add(cabinet_id)

        # Sauvegarde progression toutes les 50 fiches
        if i % 50 == 0:
            save_json(PROGRESS_SCRAPED_FILE, {
                "done_ids":   list(done_ids),
                "updated_at": datetime.now().isoformat(),
            })

        # Log toutes les 10 fiches
        if i % 10 == 0:
            tel_info = f"{row['telephone']} ({row['type_tel']})" if row["telephone"] else "—"
            log.info(
                f"[{i:>6}/{len(todo)}] "
                f"{row.get('nom_cabinet', '?')[:35]:<35s} | "
                f"{row.get('ville', '?'):<20s} | "
                f"Web: {'✓' if row['site_web'] else '✗'} | "
                f"Tel: {tel_info}"
            )

    save_json(PROGRESS_SCRAPED_FILE, {
        "done_ids":   list(done_ids),
        "updated_at": datetime.now().isoformat(),
    })
    log.info("✅ Scraping terminé !")
    print_stats()


# ─────────────────────────────────────────────
#  MODE SÉQUENTIEL (secours)
# ─────────────────────────────────────────────

def scrape_by_sequential_ids(start_id=1, end_id=50000):
    log.info("=" * 60)
    log.info(f"MODE SÉQUENTIEL : IDs {start_id:,} → {end_id:,}")
    log.info("=" * 60)

    seq_progress = load_json("progress_seq_ids.json")
    done_ids     = set(seq_progress.get("done_ids", []))

    for cabinet_id in range(start_id, end_id + 1):
        if str(cabinet_id) in done_ids:
            continue

        url  = f"{BASE_URL}/expert-comptable/{cabinet_id}"
        resp = fetch(url)
        done_ids.add(str(cabinet_id))

        if not resp or "expert-comptable" not in resp.url:
            continue

        row = parse_cabinet_page(resp.text, resp.url)
        append_csv_row(OUTPUT_CSV, row, CSV_FIELDS)

        if cabinet_id % 100 == 0:
            save_json("progress_seq_ids.json", {
                "done_ids":   list(done_ids),
                "updated_at": datetime.now().isoformat(),
            })
            log.info(f"ID {cabinet_id:>6} : {row.get('nom_cabinet','?')} — {row.get('ville','?')}")

    save_json("progress_seq_ids.json", {
        "done_ids":   list(done_ids),
        "updated_at": datetime.now().isoformat(),
    })
    log.info("✅ Scan séquentiel terminé")
    print_stats()


# ─────────────────────────────────────────────
#  STATS FINALES
# ─────────────────────────────────────────────

def print_stats():
    """Lit le CSV et affiche les statistiques de couverture."""
    if not os.path.exists(OUTPUT_CSV):
        log.warning("Aucun CSV trouvé.")
        return

    total = with_site = with_tel = mobile = fixe = autre_tel = 0

    with open(OUTPUT_CSV, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            total += 1
            if row.get("site_web", "").strip():
                with_site += 1
            tel = row.get("telephone", "").strip()
            if tel:
                with_tel += 1
                t = row.get("type_tel", "").strip()
                if   t == "mobile": mobile    += 1
                elif t == "fixe":   fixe      += 1
                else:               autre_tel += 1

    if total == 0:
        log.warning("CSV vide.")
        return

    def pct(n, d):
        return (n / d * 100) if d else 0.0

    sep = "=" * 60
    log.info(sep)
    log.info("  STATISTIQUES FINALES")
    log.info(sep)
    log.info(f"  Total cabinets scrapés            : {total:>7,}")
    log.info(f"")
    log.info(f"  ┌ Avec site web                   : {with_site:>7,}  ({pct(with_site, total):5.1f}%)")
    log.info(f"  └ Sans site web                   : {total - with_site:>7,}  ({pct(total - with_site, total):5.1f}%)")
    log.info(f"")
    log.info(f"  ┌ Avec téléphone                  : {with_tel:>7,}  ({pct(with_tel, total):5.1f}%)")
    log.info(f"  │   ├─ dont mobile  (06 / 07)      : {mobile:>7,}  ({pct(mobile, with_tel):5.1f}% des tél.)")
    log.info(f"  │   ├─ dont fixe    (01 → 05)      : {fixe:>7,}  ({pct(fixe, with_tel):5.1f}% des tél.)")
    log.info(f"  │   └─ dont autre   (08xx, +33…)   : {autre_tel:>7,}  ({pct(autre_tel, with_tel):5.1f}% des tél.)")
    log.info(f"  └ Sans téléphone                  : {total - with_tel:>7,}  ({pct(total - with_tel, total):5.1f}%)")
    log.info(sep)


# ─────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main():
    log.info("🚀 Scraper OEC Experts-Comptables v3")
    log.info(f"   Délai entre requêtes : {DELAY_MIN}s – {DELAY_MAX}s (aléatoire)")
    log.info(f"   Fichier de sortie    : {OUTPUT_CSV}")
    log.info("")

    progress     = load_json(PROGRESS_URLS_FILE)
    cabinet_urls = progress.get("cabinet_urls", [])
    scraped      = load_json(PROGRESS_SCRAPED_FILE)
    done_ids     = scraped.get("done_ids", [])

    print("\n" + "=" * 55)
    print("  SCRAPER OEC — Choisissez un mode")
    print("=" * 55)
    if cabinet_urls:
        print(f"  URLs collectées   : {len(cabinet_urls):,}")
    if done_ids:
        print(f"  Déjà scrapés      : {len(done_ids):,}")
    if os.path.exists(OUTPUT_CSV):
        size_mb = os.path.getsize(OUTPUT_CSV) / 1024 / 1024
        print(f"  CSV actuel        : {size_mb:.1f} Mo")
    print()
    print("  1 → Collecte URLs + scraping complet")
    print("  2 → Scraping seul  (liste existante)")
    print("  3 → Stats uniquement")
    print("  4 → Scan IDs séquentiels (secours)")
    print()

    choix = input("  Votre choix [1/2/3/4] : ").strip()
    print()

    if choix == "1":
        cabinet_urls = collect_all_cabinet_urls()
        scrape_all_cabinets(cabinet_urls)

    elif choix == "2":
        if not cabinet_urls:
            log.error("Aucune URL collectée. Lancez d'abord le mode 1.")
            return
        log.info(f"Mode scraping seul — {len(cabinet_urls):,} URLs dans la liste")
        scrape_all_cabinets(cabinet_urls)

    elif choix == "3":
        print_stats()

    elif choix == "4":
        try:
            start = int(input("  ID de départ [défaut 1]     : ").strip() or "1")
            end   = int(input("  ID de fin    [défaut 50000] : ").strip() or "50000")
        except ValueError:
            start, end = 1, 50000
        scrape_by_sequential_ids(start_id=start, end_id=end)

    else:
        log.warning("Choix non reconnu.")


if __name__ == "__main__":
    main()

# dorian.businesstracker@gmail.com