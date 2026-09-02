-- Verificar inconsistencias entre Clientes y Contactos
-- Ejecutar en SQLite

-- 1. Clientes con email pero SIN Contact asociado
SELECT COUNT(*) as 'Clientes con email SIN Contact'
FROM clients_client c
WHERE c.email != ''
  AND NOT EXISTS (
    SELECT 1 FROM communications_contact cc WHERE cc.client_id = c.id
  );

-- Ver detalles
SELECT c.id, c.name, c.email, 
       CASE WHEN cc.id IS NULL THEN 'SIN CONTACT' ELSE 'CON CONTACT' END as status
FROM clients_client c
LEFT JOIN communications_contact cc ON cc.client_id = c.id
WHERE c.email != ''
ORDER BY status, c.name
LIMIT 30;

-- 2. Contactos sin Cliente
SELECT COUNT(*) as 'Contactos SIN Cliente'
FROM communications_contact
WHERE client_id IS NULL;

-- Ver detalles
SELECT id, whatsapp_number, preferred_channel, created_at
FROM communications_contact
WHERE client_id IS NULL
LIMIT 20;

-- 3. Resumen general
SELECT 
  (SELECT COUNT(*) FROM clients_client) as total_clientes,
  (SELECT COUNT(*) FROM clients_client WHERE email != '') as clientes_con_email,
  (SELECT COUNT(*) FROM communications_contact) as total_contacts,
  (SELECT COUNT(*) FROM communications_contact WHERE client_id IS NOT NULL) as contacts_con_cliente,
  (SELECT COUNT(*) FROM communications_contact WHERE client_id IS NULL) as contacts_sin_cliente
;
