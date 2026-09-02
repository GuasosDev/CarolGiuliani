#!/usr/bin/env python3
import sqlite3

db_path = "/home/diego/proyectos/GD-CarolGiuliani/db.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("ANÁLISIS DE CONTACTOS E INCONSISTENCIAS")
print("=" * 80)

# 1. Clientes con email pero SIN Contact
print("\n1️⃣  CLIENTES CON EMAIL PERO SIN CONTACT VINCULADO:")
cursor.execute("""
    SELECT c.id, c.name, c.email
    FROM clients_client c
    WHERE c.email != ''
      AND NOT EXISTS (
        SELECT 1 FROM communications_contact cc WHERE cc.client_id = c.id
      )
    ORDER BY c.name
    LIMIT 30
""")
rows = cursor.fetchall()
print(f"   Total: {len(rows)}")
for row in rows:
    print(f"   - ID: {row[0]}, Nombre: {row[1]}, Email: {row[2]}")

# 2. Contactos sin Cliente
print("\n2️⃣  CONTACTOS SIN CLIENTE VINCULADO:")
cursor.execute("""
    SELECT id, whatsapp_number, preferred_channel, created_at
    FROM communications_contact
    WHERE client_id IS NULL
    LIMIT 20
""")
rows = cursor.fetchall()
print(f"   Total: {len(rows)}")
for row in rows:
    print(f"   - ID: {row[0]}, WhatsApp: {row[1]}, Canal: {row[2]}, Creado: {row[3]}")

# 3. Resumen
print("\n" + "=" * 80)
print("RESUMEN GENERAL:")
print("=" * 80)

cursor.execute("SELECT COUNT(*) FROM clients_client")
total_clientes = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM clients_client WHERE email != ''")
clientes_con_email = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM communications_contact")
total_contacts = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM communications_contact WHERE client_id IS NOT NULL")
contacts_con_cliente = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM communications_contact WHERE client_id IS NULL")
contacts_sin_cliente = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*) FROM clients_client c
    WHERE c.email != ''
      AND NOT EXISTS (SELECT 1 FROM communications_contact cc WHERE cc.client_id = c.id)
""")
clientes_sin_contact = cursor.fetchone()[0]

print(f"Total de Clientes: {total_clientes}")
print(f"Clientes con email: {clientes_con_email}")
print(f"Clientes con email SIN Contact: {clientes_sin_contact} ⚠️")
print(f"\nTotal de Contacts: {total_contacts}")
print(f"Contacts con Cliente vinculado: {contacts_con_cliente}")
print(f"Contacts SIN Cliente: {contacts_sin_cliente} ⚠️")

conn.close()
