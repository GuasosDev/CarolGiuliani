import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
django.setup()

from communications.models import EmailAccount
from communications.email_handler import EmailHandler
import logging

# Set up logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test_connection')

def test_accounts():
    accounts = EmailAccount.objects.filter(is_active=True)
    if not accounts.exists():
        print("No active email accounts found.")
        return

    for account in accounts:
        print(f"\nTesting account: {account.email_address}")
        handler = EmailHandler(account)
        
        print(f"Connecting to IMAP {account.imap_host}:{account.imap_port} (SSL: {account.imap_use_ssl})...")
        try:
            import imaplib
            if account.imap_use_ssl:
                conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
            else:
                conn = imaplib.IMAP4(account.imap_host, account.imap_port)
            print("IMAP Connection established.")
            
            password = account.get_password()
            print(f"Attempting login as {account.username}...")
            conn.login(account.username, password)
            print("IMAP Login successful!")
            conn.logout()
        except Exception as e:
            print(f"IMAP Failed: {str(e)}")

        print(f"Connecting to SMTP {account.smtp_host}:{account.smtp_port} (TLS: {account.smtp_use_tls})...")
        try:
            import smtplib
            if account.smtp_use_tls:
                smtp = smtplib.SMTP(account.smtp_host, account.smtp_port)
                smtp.starttls()
            else:
                smtp = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port)
            print("SMTP Connection established.")
            
            password = account.get_password()
            print(f"Attempting login as {account.username}...")
            smtp.login(account.username, password)
            print("SMTP Login successful!")
            smtp.quit()
        except Exception as e:
            print(f"SMTP Failed: {str(e)}")

if __name__ == "__main__":
    test_accounts()
