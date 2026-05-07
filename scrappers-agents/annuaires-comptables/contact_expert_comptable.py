#!/usr/bin/env python3
"""
Daemon d'envoi de mails via l'annuaire des experts-comptables.

Usage: python contact_expert_comptable.py <N>
  N = nombre de cabinets à contacter par jour.

Comportement:
  - Boucle infinie. Chaque jour, choisit une heure aléatoire entre 09:30 et 12:30
    pour lancer une vague de N envois.
  - Si lancé pendant la fenêtre, démarre rapidement (avec un petit délai aléatoire).
  - Itère sur cabinets_oec.csv en sautant les déjà contactés (colonne `contacted`).
  - À la fin de chaque vague, envoie un email récap à dorian110620@gmail.com via le
    SMTP configuré dans biz-tracker-back/.env (vars EMAIL__*).

Prérequis:
  pip install selenium webdriver-manager
  Chrome + chromedriver (auto via webdriver-manager).
"""

import csv
import os
import random
import smtplib
import sys
import time
from datetime import datetime, timedelta, time as dtime
from email.message import EmailMessage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
)

# ============================================================
# CONFIGURATION
# ============================================================
PRENOM = "Dorian"
NOM = "Velut"
EMAIL = "dorian.businesstracker@gmail.com"
TELEPHONE = "06 52 51 77 88"
CALENDLY_URL = "https://calendly.com/julien-businesstracker/30min"

MESSAGE_BODY = (
    """Je développe un radar local qui détecte les nouvelles entreprises ouvertes autour de votre cabinet : restaurants, commerces, indépendants, sociétés récentes avec fiche Google active, etc.
L'objectif est simple : vous permettre d'identifier les prospects qui viennent de se lancer, avant qu'ils ne soient déjà accompagnés par un autre cabinet.
Chaque jour, vous recevez une liste courte, qualifiée, avec coordonnées, secteur, zone, fiche Google.
Je cherche quelques cabinets pour tester le format sur leur zone. Est-ce que ce type de signal commercial pourrait vous intéresser ?

Vous pouvez réserver un créneau d'échange ici si vous le souhaitez : """
    + CALENDLY_URL
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# CSV_PATH peut être surchargé via la variable d'environnement (utile en container
# où le CSV est bind-mounté hors de l'image pour persister entre les redémarrages).
CSV_PATH = os.environ.get("CSV_PATH") or os.path.join(SCRIPT_DIR, "cabinets_oec.csv")

# .env (ordre de priorité):
#   1. ENV_FILE si exporté
#   2. .env dans le dossier du script (déploiement VPS)
#   3. ../../biz-tracker-back/.env.prod (dev local depuis le monorepo)
#   4. ../../biz-tracker-back/.env (dev local fallback)
ENV_CANDIDATES = [
    os.environ.get("ENV_FILE"),
    os.path.join(SCRIPT_DIR, ".env"),
    os.path.join(SCRIPT_DIR, "..", "..", "biz-tracker-back", ".env.prod"),
    os.path.join(SCRIPT_DIR, "..", "..", "biz-tracker-back", ".env"),
]
SUMMARY_TO = "dorian110620@gmail.com"

CONTACTED_COL = "contacted"
WINDOW_START = dtime(9, 30)
WINDOW_END = dtime(12, 30)

# Headless par défaut sur Linux (VPS), visible sur Mac pour debug
HEADLESS_DEFAULT = sys.platform.startswith("linux")
# ============================================================


def short_delay(a=0.15, b=0.5):
    time.sleep(random.uniform(a, b))


def between_sites_delay():
    time.sleep(random.uniform(4.0, 7.0))


# ============================================================
# .env loader (sans dépendance)
# ============================================================
def load_env_file(path: str) -> dict:
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip('"').strip("'")
            env[k.strip()] = v
    return env


def load_smtp_config() -> dict:
    """Charge la config SMTP depuis le 1er fichier .env utilisable.
    Les variables d'environnement déjà exportées priment sur le contenu du fichier.
    """
    env = {}
    for path in ENV_CANDIDATES:
        if not path:
            continue
        loaded = load_env_file(path)
        if loaded.get("EMAIL__SMTP_HOST") and loaded.get("EMAIL__PROVIDER") != "mailhog":
            env = loaded
            break
    # Override avec les vars d'environnement réelles si présentes
    for key in ("EMAIL__SMTP_HOST", "EMAIL__SMTP_PORT", "EMAIL__SMTP_USERNAME",
                "EMAIL__SMTP_PASSWORD", "EMAIL__USE_TLS", "EMAIL__FROM_ADDRESS"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return {
        "host": env.get("EMAIL__SMTP_HOST"),
        "port": int(env.get("EMAIL__SMTP_PORT") or 587),
        "username": env.get("EMAIL__SMTP_USERNAME"),
        "password": env.get("EMAIL__SMTP_PASSWORD"),
        "use_tls": (env.get("EMAIL__USE_TLS", "true").lower() == "true"),
        "from_address": env.get("EMAIL__FROM_ADDRESS") or "notification@business-tracker.fr",
    }


# ============================================================
# Selenium driver
# ============================================================
def create_driver(headless: bool):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # En container: CHROME_BIN pointe vers /usr/bin/chromium, CHROMEDRIVER vers /usr/bin/chromedriver
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.environ.get("CHROMEDRIVER")
    if chromedriver_path:
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(service=Service(executable_path=chromedriver_path), options=options)
    else:
        try:
            driver = webdriver.Chrome(options=options)
        except Exception:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service

                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except ImportError:
                print("❌ Impossible de lancer Chrome. pip install webdriver-manager")
                sys.exit(1)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ============================================================
# Page helpers
# ============================================================
def accept_cookies(driver):
    cookie_selectors = [
        "//*[@id='tarteaucitronAllDenied2']",
        "//*[@id='tarteaucitronPersonalize2']",
        "//button[contains(text(), 'Tout refuser')]",
        "//button[contains(text(), 'Refuser')]",
        "//button[contains(text(), 'Accepter')]",
    ]
    for selector in cookie_selectors:
        try:
            btn = driver.find_element(By.XPATH, selector)
            if btn.is_displayed():
                btn.click()
                short_delay()
                return
        except NoSuchElementException:
            continue


def extract_contact_name(driver):
    """Extrait le 1er prénom/nom dans .people .info → ('Firstname', 'Lastname').
    Le HTML expose typiquement: 1er <span> = NOM (uppercase), 2e <span> = prénom.
    Retourne (None, None) si introuvable.
    """
    try:
        info = driver.find_element(By.CSS_SELECTOR, ".people .info")
        spans = info.find_elements(By.TAG_NAME, "span")
        if len(spans) < 2:
            return None, None
        last = (spans[0].text or "").strip()
        first = (spans[1].text or "").strip()
        if not first or not last:
            return None, None
        # Capitalisation propre
        return first.title(), last.title()
    except NoSuchElementException:
        return None, None


def click_contacter_par_mail(driver):
    selectors = [
        "//span[contains(text(), 'Contacter par mail')]",
        "//button[contains(text(), 'Contacter par mail')]",
        "//a[contains(text(), 'Contacter par mail')]",
        "//*[contains(text(), 'Contacter par mail')]",
    ]
    for selector in selectors:
        try:
            for el in driver.find_elements(By.XPATH, selector):
                if el.is_displayed():
                    try:
                        el.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", el)
                    return True
        except Exception:
            continue
    return False


def paste_value(driver, selector: str, value: str) -> bool:
    """Injecte la valeur directement dans l'input via JS (pas de frappe humaine)
    et déclenche les events input/change pour les frameworks éventuels.
    """
    try:
        el = driver.find_element(By.CSS_SELECTOR, selector)
    except NoSuchElementException:
        return False
    if not (el.is_displayed() and el.is_enabled()):
        return False
    driver.execute_script(
        """
        const el = arguments[0]; const v = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(
            el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
            'value'
        ).set;
        setter.call(el, v);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        """,
        el,
        value,
    )
    return True


def fill_form(driver, message_text: str) -> int:
    fields = [
        ("#contact_request_firstName", PRENOM),
        ("#contact_request_lastName", NOM),
        ("#contact_request_email", EMAIL),
        ("#contact_request_phone", TELEPHONE),
        ("#contact_request_message", message_text),
    ]
    filled = 0
    for sel, val in fields:
        if paste_value(driver, sel, val):
            filled += 1
            short_delay(0.05, 0.2)
    return filled


def solve_math_question(driver) -> bool:
    try:
        n1 = driver.find_element(By.CSS_SELECTOR, "#contact_request_number1").get_attribute("value")
        n2 = driver.find_element(By.CSS_SELECTOR, "#contact_request_number2").get_attribute("value")
        op = driver.find_element(By.CSS_SELECTOR, "#contact_request_operator").get_attribute("value")
        a, b = int(n1), int(n2)
        if op == "+":
            answer = a + b
        elif op == "-":
            answer = a - b
        elif op in ("*", "x", "X"):
            answer = a * b
        else:
            answer = a + b
        return paste_value(driver, "#contact_request_calcul", str(answer))
    except NoSuchElementException:
        return False


def check_consent_checkbox(driver) -> bool:
    """La checkbox Bootstrap custom-control-input est masquée par CSS:
    on doit cliquer sur le <label> associé pour la cocher.
    """
    try:
        cb = driver.find_element(By.CSS_SELECTOR, "#contact_request_confirm")
    except NoSuchElementException:
        return False

    if cb.is_selected():
        return True

    try:
        label = driver.find_element(By.CSS_SELECTOR, "label[for='contact_request_confirm']")
        try:
            label.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", label)
        short_delay()
        if cb.is_selected():
            return True
    except NoSuchElementException:
        pass

    driver.execute_script(
        """
        const cb = arguments[0];
        cb.checked = true;
        cb.dispatchEvent(new Event('input', {bubbles: true}));
        cb.dispatchEvent(new Event('change', {bubbles: true}));
        cb.dispatchEvent(new Event('click', {bubbles: true}));
        """,
        cb,
    )
    return cb.is_selected()


def submit_form(driver) -> bool:
    selectors = [
        "button.submit-contact-request",
        "button[type='submit']",
    ]
    for selector in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed() and el.is_enabled():
                    try:
                        el.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", el)
                    return True
        except Exception:
            continue
    return False


# ============================================================
# CSV
# ============================================================
def read_csv_rows():
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    if not rows:
        return [], []
    header = rows[0]
    data = rows[1:]
    if CONTACTED_COL not in header:
        header.append(CONTACTED_COL)
        for r in data:
            while len(r) < len(header) - 1:
                r.append("")
            r.append("")
    else:
        for r in data:
            while len(r) < len(header):
                r.append("")
    return header, data


def write_csv_rows(header, data):
    tmp_path = CSV_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(data)
    os.replace(tmp_path, CSV_PATH)


# ============================================================
# Process
# ============================================================
def process_one(driver, url: str):
    driver.get(url)
    time.sleep(random.uniform(2.0, 3.5))
    accept_cookies(driver)

    first, last = extract_contact_name(driver)
    if first and last:
        greeting = f"Bonjour {first} {last},\n\n"
    else:
        greeting = "Bonjour,\n\n"
    message_text = greeting + MESSAGE_BODY

    if not click_contacter_par_mail(driver):
        return False, "bouton contact introuvable", first, last

    time.sleep(random.uniform(0.8, 1.5))

    filled = fill_form(driver, message_text)
    if filled < 5:
        return False, f"formulaire incomplet ({filled}/5)", first, last

    short_delay()
    if not solve_math_question(driver):
        return False, "captcha math non résolu", first, last

    short_delay()
    if not check_consent_checkbox(driver):
        return False, "checkbox consentement non cochée", first, last

    short_delay(0.4, 0.9)
    if not submit_form(driver):
        return False, "envoi échoué", first, last

    time.sleep(random.uniform(2.0, 3.0))
    return True, "ok", first, last


def run_batch(n_to_contact: int, headless: bool):
    header, data = read_csv_rows()
    if not header:
        print("CSV vide.")
        return None

    contacted_idx = header.index(CONTACTED_COL)
    try:
        url_idx = header.index("url_fiche")
        name_idx = header.index("nom_cabinet")
    except ValueError:
        print("Colonnes 'url_fiche' / 'nom_cabinet' introuvables dans le CSV.")
        return None

    write_csv_rows(header, data)

    targets = [
        i for i, r in enumerate(data)
        if (r[contacted_idx] or "").strip() == "" and (r[url_idx] or "").strip()
    ]
    targets = targets[:n_to_contact]

    if not targets:
        print("Aucun cabinet restant à contacter.")
        return {"successes": [], "failures": [], "started_at": datetime.now(), "ended_at": datetime.now()}

    print(f"→ {len(targets)} cabinet(s) à contacter")
    started_at = datetime.now()

    successes = []  # list of dicts
    failures = []

    driver = create_driver(headless=headless)
    try:
        for k, idx in enumerate(targets, 1):
            row = data[idx]
            url = row[url_idx]
            name = row[name_idx]
            try:
                ok, info, first, last = process_one(driver, url)
            except Exception as e:
                ok, info, first, last = False, f"exception: {e}", None, None

            status = "OK " if ok else "ERR"
            who = f"{first} {last}" if first and last else "-"
            print(f"[{k}/{len(targets)}] {status} {name} ({who}) — {info}")

            entry = {"name": name, "url": url, "contact": who, "info": info}
            if ok:
                successes.append(entry)
                data[idx][contacted_idx] = "1"
            else:
                failures.append(entry)
                data[idx][contacted_idx] = f"err:{info}"
            write_csv_rows(header, data)

            if k < len(targets):
                between_sites_delay()
    finally:
        driver.quit()

    return {
        "successes": successes,
        "failures": failures,
        "started_at": started_at,
        "ended_at": datetime.now(),
    }


# ============================================================
# Email summary
# ============================================================
def send_summary_email(summary: dict, n_target: int):
    cfg = load_smtp_config()
    if not cfg["host"] or cfg["host"] == "null":
        print("⚠️  SMTP non configuré (EMAIL__SMTP_HOST manquant). Pas d'email.")
        return

    s = summary
    n_ok = len(s["successes"])
    n_err = len(s["failures"])
    duration = s["ended_at"] - s["started_at"]

    subject = f"[OEC] Vague {n_ok}/{n_target} envoyés ({n_err} erreurs)"

    def fmt_list(items):
        if not items:
            return "  (aucun)\n"
        return "\n".join(
            f"  - {it['name']} — {it['contact']} — {it['info']}\n    {it['url']}" for it in items
        ) + "\n"

    body = (
        f"Vague terminée\n"
        f"  Démarrage : {s['started_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  Fin       : {s['ended_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  Durée     : {duration}\n"
        f"  Cible     : {n_target}\n"
        f"  Succès    : {n_ok}\n"
        f"  Échecs    : {n_err}\n\n"
        f"--- Succès ---\n{fmt_list(s['successes'])}\n"
        f"--- Échecs ---\n{fmt_list(s['failures'])}"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_address"]
    msg["To"] = SUMMARY_TO
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
            smtp.ehlo()
            if cfg["use_tls"]:
                smtp.starttls()
                smtp.ehlo()
            if cfg["username"] and cfg["password"]:
                smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)
        print(f"📧 Récap envoyé à {SUMMARY_TO}")
    except Exception as e:
        print(f"⚠️  Envoi du récap échoué: {e}")


# ============================================================
# Scheduler (boucle journalière)
# ============================================================
def compute_next_run(now: datetime) -> datetime:
    """Retourne le prochain datetime de lancement, dans la fenêtre [09:30, 12:30].
    - Si maintenant est avant la fenêtre : random aujourd'hui dans la fenêtre.
    - Si maintenant est dans la fenêtre   : random entre maintenant+1min et fin de fenêtre.
    - Si maintenant est après la fenêtre  : random demain dans la fenêtre.
    """
    today_start = datetime.combine(now.date(), WINDOW_START)
    today_end = datetime.combine(now.date(), WINDOW_END)

    if now < today_start:
        delta = (today_end - today_start).total_seconds()
        return today_start + timedelta(seconds=random.uniform(0, delta))
    if today_start <= now <= today_end:
        remaining = (today_end - now).total_seconds() - 60
        if remaining <= 0:
            # Fenêtre quasi finie, planifier demain
            tomorrow_start = today_start + timedelta(days=1)
            tomorrow_end = today_end + timedelta(days=1)
            return tomorrow_start + timedelta(
                seconds=random.uniform(0, (tomorrow_end - tomorrow_start).total_seconds())
            )
        return now + timedelta(seconds=random.uniform(60, remaining))

    tomorrow_start = today_start + timedelta(days=1)
    tomorrow_end = today_end + timedelta(days=1)
    delta = (tomorrow_end - tomorrow_start).total_seconds()
    return tomorrow_start + timedelta(seconds=random.uniform(0, delta))


def sleep_until(target: datetime):
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        # Sleep par tranches d'1h max pour rester réactif
        time.sleep(min(remaining, 3600))


# ============================================================
# Main
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python contact_expert_comptable.py <N>")
        sys.exit(1)

    try:
        n_per_day = int(sys.argv[1])
    except ValueError:
        print("N doit être un entier.")
        sys.exit(1)

    headless = os.environ.get("HEADLESS", "").lower() in ("1", "true", "yes") or HEADLESS_DEFAULT
    print(f"Démarrage daemon — {n_per_day} cabinets/jour, headless={headless}")

    while True:
        next_run = compute_next_run(datetime.now())
        print(f"⏰ Prochain envoi prévu à {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        sleep_until(next_run)

        print(f"\n=== Vague du {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        try:
            summary = run_batch(n_per_day, headless=headless)
        except Exception as e:
            print(f"❌ Erreur pendant la vague: {e}")
            summary = {
                "successes": [],
                "failures": [{"name": "BATCH", "url": "-", "contact": "-", "info": f"exception: {e}"}],
                "started_at": datetime.now(),
                "ended_at": datetime.now(),
            }

        if summary is not None:
            try:
                send_summary_email(summary, n_per_day)
            except Exception as e:
                print(f"⚠️  Erreur envoi récap: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
