import os
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings') # Ajusta si tu settings tiene otro nombre
django.setup()

from django.contrib.auth.models import User
from clients.models import Client
from communications.models import Contact, Conversation, Message
from django.utils import timezone

def create_test_data():
    print("Iniciando creación de datos de prueba...")
    
    # 1. Obtener o crear un usuario (agente)
    user = User.objects.first()
    if not user:
        user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
    
    # 2. Crear un Cliente de prueba
    client, _ = Client.objects.get_or_create(
        name="Cliente de Prueba UI",
        defaults={'email': 'prueba@ejemplo.com', 'phone': '123456789'}
    )
    
    # 3. Crear un Contacto de comunicación
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'whatsapp_number': '5491122334455', 'preferred_channel': 'whatsapp'}
    )
    
    # 4. Crear una Conversación
    conv = Conversation.objects.create(
        contact=contact,
        channel='whatsapp',
        status='normal',
        assigned_to=user,
        subject="Prueba de densidad de mensajes"
    )
    
    # 5. Generar 30 mensajes para ver el scroll y la densidad
    mensajes = [
        "¡Hola! Necesito consultar sobre un pedido.",
        "Hola, con gusto te ayudo. ¿Cuál es tu número de orden?",
        "Es la #4502. Compré ayer y no me llegó el mail de confirmación.",
        "Entiendo. Déjame revisar en el sistema...",
        "Perfecto, aguardo.",
        "Ya lo encontré. Hubo un pequeño error en el tipeo del email.",
        "Ah, ¿en serio? ¿Qué email figura?",
        "Figura como 'clinte@ejemplo.com' en lugar de 'cliente@ejemplo.com'.",
        "¡Qué despistado! Sí, fue error mío al escribir rápido.",
        "No te preocupes, ya lo corregí. ¿Te lo reenvío ahora?",
        "Sí, por favor. Lo necesito para el seguimiento.",
        "Enviado. ¿Algo más en lo que pueda ayudarte hoy?",
        "De momento nada más. Muchas gracias por la rapidez.",
        "¡Un placer! Estamos para ayudarte. Que tengas un gran día.",
        "Igualmente, adiós.",
        "Este es un mensaje largo para probar cómo se ve la nueva burbuja de ancho extendido. Debería ocupar casi todo el ancho de la pantalla y permitir leer más contenido sin que la burbuja sea demasiado alta, optimizando así el espacio vertical del chat.",
        "Entendido, se ve mucho mejor así.",
        "¿Probamos con otro mensaje largo?",
        "Claro, dale. Mientras más texto pongamos, mejor veremos si el ajuste de márgenes de 10px entre mensajes funciona correctamente para ahorrar espacio.",
        "¡Exacto! Con el padding reducido a 15px en el área de mensajes también deberíamos ganar al menos 2 o 3 mensajes extra visibles en la misma pantalla."
    ]
    
    for i, texto in enumerate(mensajes):
        direction = 'inbound' if i % 2 == 0 else 'outbound'
        Message.objects.create(
            conversation=conv,
            message_type='whatsapp',
            direction=direction,
            sender=user if direction == 'outbound' else None,
            sender_name=client.name if direction == 'inbound' else None,
            content=texto,
            created_at=timezone.now()
        )
    
    print(f"✅ ¡Éxito! Se creó la conversación ID: {conv.id}")
    print(f"Ahora puedes ir a /communications/dashboard/?conversation={conv.id} para ver el resultado.")

if __name__ == "__main__":
    create_test_data()