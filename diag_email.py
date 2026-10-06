import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
import django
django.setup()

from communications.models import EmailAccount, EmailQueue, Conversation
from django.utils import timezone

print("=" * 60)
print("EMAIL ACCOUNTS")
print("=" * 60)
accounts = EmailAccount.objects.all()
print(f"Total accounts: {accounts.count()}")
for a in accounts:
    print(f"\n  [{a.id}] {a.email_address}")
    print(f"    is_active   = {a.is_active}")
    print(f"    sync_enabled= {a.sync_enabled}")
    print(f"    IMAP {a.imap_host}:{a.imap_port} (SSL={a.imap_use_ssl})")
    print(f"    user owner  = {a.user_id}")

print("\n" + "=" * 60)
print("EMAIL QUEUE STATUS")
print("=" * 60)
for status in ['pending', 'sending', 'sent', 'failed']:
    cnt = EmailQueue.objects.filter(status=status).count()
    print(f"  {status:8s}: {cnt}")

print("\n" + "=" * 60)
print("LAST 5 CONVERSATIONS EMAIL")
print("=" * 60)
convs = Conversation.objects.filter(channel='email').order_by('-updated_at')[:5]
for c in convs:
    print(f"  [{c.id}] {c.subject[:50] if c.subject else '(no subject)'} | status={c.status} | last_msg={c.last_message_at} | assigned={c.assigned_to_id}")

print("\n" + "=" * 60)
print("TESTING IMAP CONNECTIONS")
print("=" * 60)
from communications.email_handler import EmailHandler
for a in accounts.filter(is_active=True, sync_enabled=True):
    print(f"\n  Testing: {a.email_address} ...")
    try:
        handler = EmailHandler(a)
        ok = handler.connect_imap(timeout=15)
        print(f"    CONNECT: {'OK' if ok else 'FAILED'}")
        if ok:
            try:
                status, _ = handler.imap_connection.select('INBOX')
                print(f"    SELECT INBOX: {status}")
                status, msgs = handler.imap_connection.uid('search', None, 'UNSEEN')
                if status == 'OK' and msgs and msgs[0]:
                    unseen = len(msgs[0].split())
                    print(f"    UNSEEN MSGS: {unseen}")
                else:
                    print(f"    UNSEEN MSGS: 0")
            except Exception as e2:
                print(f"    ERROR after connect: {e2}")
            finally:
                handler.disconnect()
    except Exception as e:
        print(f"    EXCEPTION: {e}")
