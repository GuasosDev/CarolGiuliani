import os
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
django.setup()

from django.contrib.auth.models import User
from clients.models import Client
from communications.models import Contact, Conversation, Message
from django.utils import timezone

def create_email_test_data():
    print("Iniciando creación de correos de prueba...")
    
    # 1. Usuario
    user = User.objects.first()
    
    # 2. Cliente
    client, _ = Client.objects.get_or_create(
        name="Empresa de Logística S.A.",
        defaults={'email': 'logistica@empresa.com', 'phone': '987654321'}
    )
    
    # 3. Contacto
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'email'}
    )
    
    # 4. Conversación de Email
    conv = Conversation.objects.create(
        contact=contact,
        channel='email',
        status='normal',
        assigned_to=user,
        subject="RE: Presupuesto para servicios de distribución mensual Q3"
    )
    
    # 5. Mensajes de Email
    emails = [
        "Estimados, adjunto enviamos la propuesta solicitada para la distribución de la zona norte. Quedamos a la espera de sus comentarios.",
        "Recibido. Lo revisamos con el equipo de finanzas y les respondemos a la brevedad. ¿Podrían enviarme también el anexo de costos por kilómetro?",
        "Claro que sí, aquí les envío el anexo detallado y el cronograma de entregas previsto para julio.",
        "Gracias por la celeridad. Una consulta adicional: ¿el seguro de carga está incluido en el precio base o se factura por separado?",
        "El seguro está incluido hasta un valor declarado de $500.000. Para valores superiores, aplicamos una tasa adicional del 0.5%. Adjunto la póliza para que vean las coberturas.",
        "Perfecto, la póliza se ve correcta. Procederemos con la firma del contrato. ¿Cuándo podemos coordinar la primera carga?",
        "Podemos iniciar este mismo lunes. Por favor, confirmen los datos del chofer y la patente del vehículo antes del viernes a las 15hs.",
        "Entendido. Los datos serán enviados mañana a primera hora. Saludos cordiales.",
        "Excelente. Quedamos atentos. Saludos."
    ]
    
    for i, texto in enumerate(emails):
        direction = 'inbound' if i % 2 == 0 else 'outbound'
        msg = Message.objects.create(
            conversation=conv,
            message_type='email',
            direction=direction,
            sender=user if direction == 'outbound' else None,
            sender_name=client.name if direction == 'inbound' else None,
            content=texto,
            created_at=timezone.now()
        )
        
        # Simular adjuntos para algunos mensajes de email
        if "adjunto" in texto.lower() or "anexo" in texto.lower() or "póliza" in texto.lower():
            # Nota: Esto asume que tienes el modelo EmailMessage y Attachment relacionado.
            # Como el sistema usa Message.file genérico para simplificar en algunos casos:
            msg.metadata = {"has_attachments": True, "subject": conv.subject}
            msg.save()
            print(f"   - Mensaje con adjunto simulado creado.")

    print(f"✅ ¡Éxito! Se creó la conversación de EMAIL ID: {conv.id}")
    print(f"Ver resultado en: /communications/dashboard/?conversation={conv.id}&channel=email")

if __name__ == "__main__":
    create_email_test_data()