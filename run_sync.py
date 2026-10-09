import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
import django
django.setup()

from communications.tasks import sync_all_email_accounts, sync_email_account
from communications.models import EmailAccount

print("=" * 60)
print("DISPARANDO SYNC MANUAL (directamente, sin Celery)")
print("=" * 60)

accounts = EmailAccount.objects.filter(is_active=True, sync_enabled=True)
for a in accounts:
    print(f"\nSyncing {a.email_address} (id={a.id})...")
    result = sync_email_account(a.id)
    print(f"  Resultado: {result} emails nuevos")

print("\nListo. Verifica en BD si llegaron los emails nuevos.")
