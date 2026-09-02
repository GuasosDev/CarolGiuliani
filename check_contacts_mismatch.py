"""
Script para verificar inconsistencias entre Clientes y Contactos
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
django.setup()

from clients.models import Client
from communications.models import Contact

print("=" * 80)
print("ANÁLISIS DE CLIENTES SIN CONTACTO VINCULADO")
print("=" * 80)

# 1. Clientes con email pero SIN Contact asociado
clients_without_contact = Client.objects.exclude(email__exact='').filter(
    communication_contact__isnull=True
)
print(f"\n✅ Clientes con EMAIL pero SIN Contact vinculado: {clients_without_contact.count()}")
for client in clients_without_contact[:20]:
    print(f"   - ID: {client.id}, Nombre: {client.name}, Email: {client.email}")

# 2. Clientes SIN email pero CON Contact
clients_without_email = Client.objects.filter(
    communication_contact__isnull=False,
    email__exact=''
)
print(f"\n❌ Clientes SIN EMAIL pero CON Contact: {clients_without_email.count()}")
for client in clients_without_email[:20]:
    contact = client.communication_contact
    print(f"   - ID: {client.id}, Nombre: {client.name}, Contact ID: {contact.id}, WhatsApp: {contact.whatsapp_number}")

# 3. Contactos huérfanos (sin Client)
orphan_contacts = Contact.objects.filter(client__isnull=True)
print(f"\n👻 Contactos SIN Cliente vinculado: {orphan_contacts.count()}")
for contact in orphan_contacts[:20]:
    print(f"   - ID: {contact.id}, WhatsApp: {contact.whatsapp_number}, Canal: {contact.preferred_channel}")

# 4. Resumen
print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)
print(f"Total de Clientes: {Client.objects.count()}")
print(f"Total de Clientes con email: {Client.objects.exclude(email__exact='').count()}")
print(f"Total de Contacts: {Contact.objects.count()}")
print(f"Clientes con Contact vinculado: {Client.objects.filter(communication_contact__isnull=False).count()}")
print(f"Clientes SIN Contact pero CON email: {clients_without_contact.count()} ⚠️")
print(f"Contacts SIN Cliente: {orphan_contacts.count()} ⚠️")
