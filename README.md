# Brute_lab
Brute-Lab is a brute-force login testing tool designed for ethical hacking and penetration testing environments. It automates the process of attempting to crack login credentials using different modes and strategies. The tool includes built-in support for bypassing CAPTCHAs (such as reCAPTCHA v2) using 2Captcha API when running in browser mode.
Features:

Basic Mode: Uses simple POST requests to try brute-forcing login forms.

Cloudflare Mode: Uses cloudscraper to bypass Cloudflare protections.

Browser Mode: Uses Selenium to simulate a real browser for more complex login forms and CAPTCHA solving. It integrates with 2Captcha for CAPTCHA bypass when an API key is provided.

Legal Disclaimer:

The tool is meant ONLY for controlled environments (e.g., penetration testing with authorization). Unauthorized usage may violate laws and ethical standards.

How to Run Brute-Lab in Terminal:

Install Dependencies:
Ensure that you have the required libraries installed:
pip install requests cloudscraper selenium beautifulsoup4 twocaptcha colorama webdriver-manager

Run the Script:
In the terminal, run the tool using the following command structure:
python Brute_lab.py [TARGET_URL] [USERNAME] [PASSWORD_FILE] --mode [MODE] --captcha-api [2CAPTCHA_API_KEY] (only cloudflare mode requires captcha api)

[TARGET_URL]: The URL of the login page.

[USERNAME]: The username to brute-force.

[PASSWORD_FILE]: Path to a file containing a list of passwords to test.

[MODE]: (Optional) Choose one of the modes: basic, cloudflare, or browser (default is basic).

[2CAPTCHA_API_KEY]: (Optional, only for browser mode) API key for 2Captcha to solve CAPTCHAs.

