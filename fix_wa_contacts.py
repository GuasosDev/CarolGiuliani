"""
Script de reparación: fusiona mensajes del contacto huérfano de WhatsApp
con la conversación correcta del cliente.

Uso:
    python manage.py shell < fix_wa_contacts.py
O:
    python manage.py shell -c "exec(open('fix_wa_contacts.py').read())"
"""
import django
from django.db import transaction

from communications.models import Contact, Conversation, Message, WhatsAppMessage

print("=== INICIANDO REPARACIÓN ===\n")

# Buscar todos los contactos huérfanos (sin cliente) que tengan número WA
orphan_contacts = Contact.objects.filter(client__isnull=True, whatsapp_number__isnull=False)
print(f"Contactos huérfanos con número WA: {orphan_contacts.count()}")

for orphan in orphan_contacts:
    wa_number = orphan.whatsapp_number
    if not wa_number:
        continue
    
    # Normalizar: tomar los últimos 10 dígitos
    digits = ''.join(c for c in wa_number if c.isdigit())
    suffix = digits[-10:] if len(digits) >= 10 else digits
    
    print(f"\n--- Procesando Contact ID:{orphan.id} | WA:{wa_number} ---")
    
    # Buscar el contacto real que tenga un cliente con ese número de teléfono
    from clients.models import Client
    real_client = Client.objects.filter(phone__endswith=suffix).first()
    
    if not real_client:
        print(f"  No se encontró cliente con el número {suffix}. Saltando.")
        continue
    
    real_contact = Contact.objects.filter(client=real_client).first()
    if not real_contact:
        print(f"  Cliente {real_client.name} encontrado, pero sin Contact. Saltando.")
        continue
    
    if real_contact.id == orphan.id:
        print(f"  Ya es el mismo contacto. Nada que hacer.")
        continue
    
    print(f"  ✓ Cliente real encontrado: {real_client.name} (Contact ID:{real_contact.id})")
    
    # Buscar la conversación "buena" del contacto real
    real_conv = Conversation.objects.filter(
        contact=real_contact, 
        channel='whatsapp'
    ).order_by('-updated_at').first()
    
    # Buscar las conversaciones del contacto huérfano
    orphan_convs = Conversation.objects.filter(contact=orphan)
    print(f"  Conversaciones huérfanas: {orphan_convs.count()}")
    
    with transaction.atomic():
        for orphan_conv in orphan_convs:
            msgs = orphan_conv.messages.all()
            print(f"  Conversación huérfana ID:{orphan_conv.id} tiene {msgs.count()} mensajes")
            
            if real_conv:
                # Mover los mensajes a la conversación real
                moved = msgs.update(conversation=real_conv)
                print(f"  ✓ {moved} mensajes movidos a Conversación ID:{real_conv.id}")
                
                # Actualizar timestamp de la conversación real
                real_conv.save()  # triggers auto_now on updated_at
            else:
                # Si no hay conversación real, reasignar la huérfana al contacto real
                orphan_conv.contact = real_contact
                orphan_conv.save()
                real_conv = orphan_conv
                print(f"  ✓ Conversación reasignada al contacto real")
        
        # Actualizar el número WA en el contacto real si no lo tiene
        if not real_contact.whatsapp_number:
            real_contact.whatsapp_number = wa_number
            real_contact.save(update_fields=['whatsapp_number'])
            print(f"  ✓ Número WA {wa_number} guardado en Contact ID:{real_contact.id}")
        
        # Eliminar conversaciones huérfanas vacías
        for orphan_conv in Conversation.objects.filter(contact=orphan):
            if orphan_conv.messages.count() == 0:
                orphan_conv.delete()
                print(f"  ✓ Conversación huérfana vacía eliminada")
        
        # Eliminar el contacto huérfano si ya no tiene conversaciones
        if not Conversation.objects.filter(contact=orphan).exists():
            orphan.delete()
            print(f"  ✓ Contacto huérfano ID:{orphan.id} eliminado")

print("\n=== REPARACIÓN COMPLETADA ===")
print("\nVerificación final:")
for conv in Conversation.objects.all().order_by('-updated_at')[:10]:
    print(f"Conv ID:{conv.id} | Contact:{conv.contact_id} | Client:{conv.contact.client_id} | Msgs:{conv.messages.count()} | Status:{conv.status}")
