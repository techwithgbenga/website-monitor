import requests
import smtplib
import ssl
import socket
import json
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time

# Load configuration
with open("config.json") as f:
    config = json.load(f)

URLS = config["urls"]
EMAIL_CONFIG = config["email"]

# Logging setup
logging.basicConfig(filename="monitor.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def send_email_alert(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_CONFIG["sender"]
        msg["To"] = EMAIL_CONFIG["receiver"]
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["port"], context=context) as server:
            server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
            server.sendmail(EMAIL_CONFIG["sender"], EMAIL_CONFIG["receiver"], msg.as_string())

        logging.info("Alert email sent.")
    except Exception as e:
        logging.error(f"Error sending email: {e}")

def check_ssl_expiry(domain):
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()
            expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry - datetime.utcnow()).days
            return days_left
    except Exception as e:
        logging.error(f"SSL check failed for {domain}: {e}")
        return None

def check_website(url):
    try:
        domain = url.split("//")[-1].split("/")[0]
        response = requests.get(url, timeout=10)
        status = response.status_code
        load_time = response.elapsed.total_seconds()

        ssl_days = check_ssl_expiry(domain)
        ssl_message = f"SSL expires in {ssl_days} days." if ssl_days is not None else "SSL check failed."

        log_message = f"{url} is UP - Status: {status} - Time: {load_time:.2f}s - {ssl_message}"
        logging.info(log_message)

        # Alert on slow site or low SSL days
        if load_time > 2 or (ssl_days is not None and ssl_days < 10):
            send_email_alert(f"⚠️ Warning for {url}",
                             f"Website responded in {load_time:.2f}s.\n{ssl_message}")

    except requests.RequestException as e:
        error_message = f"{url} is DOWN - Error: {e}"
        logging.error(error_message)
        send_email_alert(f"🚨 {url} is DOWN!", str(e))

def job():
    logging.info("Running monitor check...")
    for url in URLS:
        check_website(url)

schedule.every(10).minutes.do(job)

if __name__ == "__main__":
    logging.info("Starting website monitor...")
    job()  # Run at start
    while True:
        schedule.run_pending()
        time.sleep(1)
