#!/usr/bin/env python3
"""
Script d'envoi de mail via l'annuaire des experts-comptables.

Usage: python contact_expert_comptable.py <N>
  N = nombre de cabinets à contacter (itère sur cabinets_oec.csv en sautant
      ceux déjà marqués comme contactés).

Exemple:
  python contact_expert_comptable.py 10

Prérequis:
  pip install selenium webdriver-manager
"""

import csv
import os
import random
import sys
import time
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
MESSAGE = (
    """Bonjour,
Je développe un radar local qui détecte les nouvelles entreprises ouvertes autour de votre cabinet : restaurants, commerces, indépendants, sociétés récentes avec fiche Google active, etc.
L'objectif est simple : vous permettre d'identifier les prospects qui viennent de se lancer, avant qu'ils ne soient déjà accompagnés par un autre cabinet.
Chaque jour, vous recevez une liste courte, qualifiée, avec coordonnées, secteur, zone, fiche Google.
Je cherche quelques cabinets pour tester le format sur leur zone. Est-ce que ce type de signal commercial pourrait vous intéresser ?"""
)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cabinets_oec.csv")
CONTACTED_COL = "contacted"
# ============================================================


def short_delay(a=0.15, b=0.5):
    time.sleep(random.uniform(a, b))


def between_sites_delay():
    time.sleep(random.uniform(4.0, 7.0))


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

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


def accept_cookies(driver):
    cookie_selectors = [
        "//button[contains(text(), 'Refuser')]",
        "//button[contains(text(), 'refuser')]",
        "//button[contains(text(), 'Tout refuser')]",
        "//button[contains(text(), 'Accepter')]",
        "//*[@id='tarteaucitronAllDenied2']",
        "//*[@id='tarteaucitronPersonalize2']",
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


def type_slow(el, value):
    """Tape avec un petit délai aléatoire entre chaque caractère."""
    el.clear()
    for ch in value:
        el.send_keys(ch)
        time.sleep(random.uniform(0.01, 0.05))


def fill_form(driver):
    fields = [
        ("Prénom", PRENOM, "#contact_request_firstName"),
        ("Nom", NOM, "#contact_request_lastName"),
        ("Email", EMAIL, "#contact_request_email"),
        ("Téléphone", TELEPHONE, "#contact_request_phone"),
        ("Message", MESSAGE, "#contact_request_message"),
    ]
    filled = 0
    for _label, value, selector in fields:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            if el.is_displayed() and el.is_enabled():
                type_slow(el, value)
                filled += 1
                short_delay()
        except NoSuchElementException:
            continue
    return filled


def solve_math_question(driver):
    """Lit number1 + number2 (champs hidden) et remplit calcul."""
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
        inp = driver.find_element(By.CSS_SELECTOR, "#contact_request_calcul")
        type_slow(inp, str(answer))
        return True
    except NoSuchElementException:
        return False


def check_consent_checkbox(driver):
    """La checkbox Bootstrap custom-control-input est masquée par CSS:
    on doit cliquer sur le <label> associé (custom-control-label) pour la cocher.
    """
    try:
        cb = driver.find_element(By.CSS_SELECTOR, "#contact_request_confirm")
    except NoSuchElementException:
        return False

    if cb.is_selected():
        return True

    # 1) Cliquer sur le label associé (méthode la plus fiable pour custom-control)
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

    # 2) Fallback : cocher en JS et déclencher les events
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


def submit_form(driver):
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
# CSV helpers
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
        # normaliser la longueur des lignes
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


def process_one(driver, url):
    driver.get(url)
    time.sleep(random.uniform(2.0, 3.5))
    accept_cookies(driver)

    if not click_contacter_par_mail(driver):
        return False, "bouton contact introuvable"

    time.sleep(random.uniform(0.8, 1.5))

    filled = fill_form(driver)
    if filled < 5:
        return False, f"formulaire incomplet ({filled}/5)"

    short_delay()
    if not solve_math_question(driver):
        return False, "captcha math non résolu"

    short_delay()
    if not check_consent_checkbox(driver):
        return False, "checkbox consentement non cochée"

    short_delay(0.4, 0.9)
    if not submit_form(driver):
        return False, "envoi échoué"

    time.sleep(random.uniform(2.0, 3.0))
    return True, "ok"


def main():
    if len(sys.argv) < 2:
        print("Usage: python contact_expert_comptable.py <N>")
        sys.exit(1)

    try:
        n_to_contact = int(sys.argv[1])
    except ValueError:
        print("N doit être un entier (nombre de cabinets à contacter)")
        sys.exit(1)

    header, data = read_csv_rows()
    if not header:
        print("CSV vide.")
        sys.exit(1)

    contacted_idx = header.index(CONTACTED_COL)
    try:
        url_idx = header.index("url_fiche")
        name_idx = header.index("nom_cabinet")
    except ValueError:
        print("Colonnes 'url_fiche' / 'nom_cabinet' introuvables dans le CSV.")
        sys.exit(1)

    # Persister immédiatement l'ajout de la colonne si besoin
    write_csv_rows(header, data)

    targets = [i for i, r in enumerate(data) if (r[contacted_idx] or "").strip() == "" and (r[url_idx] or "").strip()]
    targets = targets[:n_to_contact]

    if not targets:
        print("Aucun cabinet restant à contacter.")
        return

    print(f"→ {len(targets)} cabinet(s) à contacter")

    driver = create_driver()
    try:
        for k, idx in enumerate(targets, 1):
            row = data[idx]
            url = row[url_idx]
            name = row[name_idx]
            try:
                ok, info = process_one(driver, url)
            except Exception as e:
                ok, info = False, f"exception: {e}"

            status = "OK " if ok else "ERR"
            print(f"[{k}/{len(targets)}] {status} {name} — {info}")

            data[idx][contacted_idx] = "1" if ok else f"err:{info}"
            write_csv_rows(header, data)

            if k < len(targets):
                between_sites_delay()
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
