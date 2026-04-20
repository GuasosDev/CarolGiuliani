from django.db import models
from django.contrib.auth.models import User
from clients.models import Client
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import json


# ============================================================================
# CORE MODELS
# ============================================================================

class Contact(models.Model):
    """Extended contact information linked to Client model"""
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='communication_contact', null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="WhatsApp")
    preferred_channel = models.CharField(
        max_length=20,
        choices=[('whatsapp', 'WhatsApp'), ('email', 'Email')],
        default='email',
        verbose_name="Canal Preferido"
    )
    tags = models.JSONField(default=list, blank=True, verbose_name="Etiquetas")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contacto de Comunicación"
        verbose_name_plural = "Contactos de Comunicación"

    def __str__(self):
        client_name = self.client.name if self.client else "Sin cliente"
        return f"{client_name} - {self.preferred_channel}"

    def save(self, *args, **kwargs):
        if self.whatsapp_number:
            # Eliminar todo lo que no sea dígito
            digits = "".join(filter(str.isdigit, str(self.whatsapp_number)))
            if digits:
                # Lógica para Argentina (54) + 9 + número
                if digits.startswith("54"):
                    if not digits.startswith("549"):
                        # Insertar el 9 después del 54 (Argentina móvil format para WhatsApp)
                        digits = "549" + digits[2:]
                else:
                    # Si empieza con 0, quitarlo (prefijo local)
                    if digits.startswith("0"):
                        digits = digits[1:]
                    # Si no empieza con 54, asumimos Argentina y agregamos 549
                    digits = "549" + digits
                self.whatsapp_number = digits
        super().save(*args, **kwargs)

    def get_display_phone(self):
        """Returns the most relevant phone number, safely."""
        if self.whatsapp_number:
            return self.whatsapp_number
        if self.client:
            # Check for phone attribute on Client model (core app)
            return getattr(self.client, 'phone', "")
        return ""


class Conversation(models.Model):
    """Unified conversation container for all channels"""
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
    ]
    
    STATUS_CHOICES = [
        ('normal', 'Activo'),
        ('assigned', 'Asignada'),
        ('pending', 'Pendiente'),
        ('closed', 'Cerrado'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('normal', 'Normal'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
        null=True,
        blank=True
    )
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='conversations')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name="Canal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='normal', verbose_name="Estado")
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_conversations',
        verbose_name="Asignado a"
    )
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal', verbose_name="Prioridad")
    tags = models.JSONField(default=list, blank=True, verbose_name="Etiquetas")
    subject = models.CharField(max_length=255, blank=True, null=True, verbose_name="Asunto")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # For tracking last message
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['status', 'assigned_to']),
            models.Index(fields=['channel', 'status']),
        ]

    def __str__(self):
        display_name = self.get_display_name()
        return f"{display_name} - {self.get_channel_display()} ({self.get_status_display()})"

    def get_display_name(self):
        """Returns a human-readable name for the conversation, with fallbacks."""
        if self.contact and self.contact.client:
            return self.contact.client.name
        
        # Look for sender_name in messages if no client linked
        msg = self.messages.filter(direction='inbound').order_by('-created_at').first()
        if msg and msg.sender_name:
            return msg.sender_name
            
        if self.contact and self.contact.whatsapp_number:
            return self.contact.whatsapp_number
            
        return "Desconocido"

    def close(self):
        """Close the conversation"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()

    def assign_to(self, user):
        """Assign conversation to a user"""
        self.assigned_to = user
        self.status = 'normal'
        self.save()
        
        # Create assignment record
        ConversationAssignment.objects.create(
            conversation=self,
            agent=user,
            assigned_by=user  # Can be modified to track who assigned
        )


class Message(models.Model):
    """Base message model for all channels"""
    DIRECTION_CHOICES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, verbose_name="Tipo")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, verbose_name="Dirección")
    
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages')
    sender_name = models.CharField(max_length=255, blank=True, null=True)  # For external senders
    
    content = models.TextField(verbose_name="Contenido")
    metadata = models.JSONField(default=dict, blank=True)  # Store channel-specific data
    
    is_read = models.BooleanField(default=False, verbose_name="Leído")
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} - {self.conversation} - {self.created_at}"

    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            conversation = self.conversation

            conversation.last_message_at = self.created_at
            conversation.last_message_preview = self.content[:200]

            if self.direction == 'inbound' and conversation.status == 'closed':
              conversation.status = 'open'
              conversation.closed_at = None

            conversation.save(update_fields=[
            'last_message_at',
            'last_message_preview',
            'status',
            'closed_at',
            'updated_at'
        ])

class InternalNote(models.Model):
    """Agent notes on conversations"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='internal_notes')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField(verbose_name="Contenido")
    is_pinned = models.BooleanField(default=False, verbose_name="Fijada")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nota Interna"
        verbose_name_plural = "Notas Internas"
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"Nota de {self.author.username} - {self.conversation}"


class QuickReply(models.Model):
    """Predefined message templates"""
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('both', 'Ambos'),
    ]

    title = models.CharField(max_length=100, verbose_name="Título")
    shortcut = models.CharField(max_length=50, blank=True, null=True, verbose_name="Atajo / Código")
    content = models.TextField(verbose_name="Contenido")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='both', verbose_name="Canal")
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name="Categoría")
    
    # Usage tracking
    usage_count = models.IntegerField(default=0, verbose_name="Veces Usado")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quick_replies')
    is_global = models.BooleanField(default=False, verbose_name="Global")  # Available to all users
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Respuesta Rápida"
        verbose_name_plural = "Respuestas Rápidas"
        ordering = ['-usage_count', 'title']

    def __str__(self):
        return self.title

    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.save()


# ============================================================================
# WHATSAPP MODELS
# ============================================================================

class WhatsAppAccount(models.Model):
    """WhatsApp Business API account configuration"""
    name = models.CharField(max_length=100, verbose_name="Nombre")
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Número de Teléfono")
    phone_number_id = models.CharField(max_length=100, verbose_name="Phone Number ID")
    business_account_id = models.CharField(max_length=100, verbose_name="Business Account ID")
    access_token = models.CharField(max_length=500, verbose_name="Access Token")
    webhook_verify_token = models.CharField(max_length=100, verbose_name="Webhook Verify Token")
    
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cuenta de WhatsApp"
        verbose_name_plural = "Cuentas de WhatsApp"

    def __str__(self):
        return f"{self.name} - {self.phone_number}"


class WhatsAppMessage(models.Model):
    """WhatsApp-specific message data"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Texto'),
        ('image', 'Imagen'),
        ('document', 'Documento'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('sticker', 'Sticker'),
        ('location', 'Ubicación'),
        ('contacts', 'Contactos'),
    ]
    
    STATUS_CHOICES = [
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('read', 'Leído'),
        ('failed', 'Fallido'),
    ]

    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='whatsapp_data')
    whatsapp_account = models.ForeignKey(WhatsAppAccount, on_delete=models.CASCADE, related_name='messages')
    
    whatsapp_message_id = models.CharField(max_length=100, unique=True, verbose_name="WhatsApp Message ID")
    wa_message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    
    # Media handling
    media_url = models.URLField(blank=True, null=True)
    media_id = models.CharField(max_length=100, blank=True, null=True)
    media_mime_type = models.CharField(max_length=100, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    
    # Template messages
    template_name = models.CharField(max_length=100, blank=True, null=True)
    template_language = models.CharField(max_length=10, blank=True, null=True)
    
    # Status tracking
    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mensaje de WhatsApp"
        verbose_name_plural = "Mensajes de WhatsApp"

    def __str__(self):
        return f"WA: {self.whatsapp_message_id}"


class ConversationAssignment(models.Model):
    """Track conversation assignments for multi-agent support"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='assignments')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_assignments')
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='assignments_made',
        verbose_name="Asignado por"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Asignación de Conversación"
        verbose_name_plural = "Asignaciones de Conversación"
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.conversation} -> {self.agent.username}"


# ============================================================================
# EMAIL MODELS
# ============================================================================

class EmailAccount(models.Model):
    """Email account configuration"""
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Office365'),
        ('imap', 'IMAP/SMTP Genérico'),
    ]
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name="email_accounts",
    blank=True, null=True
    )

    name = models.CharField(max_length=100, verbose_name="Nombre")
    email_address = models.EmailField(unique=True, verbose_name="Dirección de Email")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name="Proveedor")
    
    # IMAP settings
    imap_host = models.CharField(max_length=255, verbose_name="Servidor IMAP")
    imap_port = models.IntegerField(default=993, verbose_name="Puerto IMAP")
    imap_use_ssl = models.BooleanField(default=True, verbose_name="Usar SSL (IMAP)")
    
    # SMTP settings
    smtp_host = models.CharField(max_length=255, verbose_name="Servidor SMTP")
    smtp_port = models.IntegerField(default=587, verbose_name="Puerto SMTP")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="Usar TLS (SMTP)")
    
    # Credentials (encrypted)
    username = models.CharField(max_length=255, verbose_name="Usuario")
    encrypted_password = models.BinaryField(verbose_name="Contraseña (Encriptada)")
    
    # Sync settings
    sync_enabled = models.BooleanField(default=True, verbose_name="Sincronización Activa")
    sync_interval = models.IntegerField(default=5, verbose_name="Intervalo de Sincronización (minutos)")
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cuenta de Email"
        verbose_name_plural = "Cuentas de Email"

    def __str__(self):
        return f"{self.name} - {self.email_address}"

    def set_password(self, password):
        from cryptography.fernet import Fernet
        from django.conf import settings

        fernet = Fernet(settings.EMAIL_ENCRYPTION_KEY)

        if isinstance(password, str):
            password = password.encode()  # convierte a bytes solo si es str

        self.encrypted_password = fernet.encrypt(password)

    def get_password(self):
        from cryptography.fernet import Fernet
        fernet = Fernet(settings.EMAIL_ENCRYPTION_KEY)
        return fernet.decrypt(self.encrypted_password).decode()


class EmailMessage(models.Model):
    """Email-specific message data"""
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='email_data')
    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='messages')
    
    subject = models.CharField(max_length=500, verbose_name="Asunto")
    html_body = models.TextField(blank=True, null=True, verbose_name="Cuerpo HTML")
    plain_body = models.TextField(blank=True, null=True, verbose_name="Cuerpo Texto Plano")
    
    # Email headers for threading
    email_message_id = models.CharField(max_length=255, unique=True, verbose_name="Message-ID")
    in_reply_to = models.CharField(max_length=255, blank=True, null=True, verbose_name="In-Reply-To")
    references = models.TextField(blank=True, null=True, verbose_name="References")
    
    # Threading
    thread = models.ForeignKey('EmailThread', on_delete=models.SET_NULL, null=True, related_name='messages')
    
    # Recipients
    to_addresses = models.JSONField(default=list, verbose_name="Para")
    cc_addresses = models.JSONField(default=list, blank=True, verbose_name="CC")
    bcc_addresses = models.JSONField(default=list, blank=True, verbose_name="BCC")
    from_address = models.EmailField(verbose_name="De")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mensaje de Email"
        verbose_name_plural = "Mensajes de Email"

    def __str__(self):
        return f"Email: {self.subject}"


class EmailThread(models.Model):
    """Groups related emails together"""
    subject = models.CharField(max_length=500, verbose_name="Asunto")
    participants = models.JSONField(default=list, verbose_name="Participantes")
    
    first_message_at = models.DateTimeField(verbose_name="Primer Mensaje")
    last_message_at = models.DateTimeField(verbose_name="Último Mensaje")
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='email_threads')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hilo de Email"
        verbose_name_plural = "Hilos de Email"
        ordering = ['-last_message_at']

    def __str__(self):
        return f"Thread: {self.subject}"


class EmailTemplate(models.Model):
    """Email templates with variables"""
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    subject_template = models.CharField(max_length=500, verbose_name="Plantilla de Asunto")
    body_template = models.TextField(verbose_name="Plantilla de Cuerpo")
    
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name="Categoría")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_templates')
    is_global = models.BooleanField(default=False, verbose_name="Global")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Email"
        verbose_name_plural = "Plantillas de Email"

    def __str__(self):
        return self.name

    def render(self, context):
        """Render template with context variables"""
        from django.template import Template, Context
        
        subject = Template(self.subject_template).render(Context(context))
        body = Template(self.body_template).render(Context(context))
        
        return subject, body


class EmailSignature(models.Model):
    """User-specific email signatures"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_signatures')
    name = models.CharField(max_length=100, verbose_name="Nombre")
    
    html_signature = models.TextField(verbose_name="Firma HTML")
    plain_signature = models.TextField(verbose_name="Firma Texto Plano")
    
    is_default = models.BooleanField(default=False, verbose_name="Por Defecto")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Firma de Email"
        verbose_name_plural = "Firmas de Email"

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    def save(self, *args, **kwargs):
        """Ensure only one default signature per user"""
        if self.is_default:
            EmailSignature.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class EmailAttachment(models.Model):
    """Email attachments"""
    email_message = models.ForeignKey(EmailMessage, on_delete=models.CASCADE, related_name='attachments')
    
    file = models.FileField(upload_to='email_attachments/%Y/%m/%d/', verbose_name="Archivo")
    filename = models.CharField(max_length=255, verbose_name="Nombre de Archivo")
    mime_type = models.CharField(max_length=100, verbose_name="Tipo MIME")
    size = models.IntegerField(verbose_name="Tamaño (bytes)")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto de Email"
        verbose_name_plural = "Adjuntos de Email"

    def __str__(self):
        return self.filename


class EmailQueue(models.Model):
    """Queue for sending emails with retry logic"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sending', 'Enviando'),
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
    ]

    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='queued_emails')
    
    to_addresses = models.JSONField(verbose_name="Para")
    cc_addresses = models.JSONField(default=list, blank=True)
    bcc_addresses = models.JSONField(default=list, blank=True)
    
    subject = models.CharField(max_length=500, verbose_name="Asunto")
    html_body = models.TextField(blank=True, null=True)
    plain_body = models.TextField(blank=True, null=True)
    
    # Related conversation/message
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Retry logic
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    last_error = models.TextField(blank=True, null=True)
    
    scheduled_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cola de Email"
        verbose_name_plural = "Cola de Emails"
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.subject} - {self.get_status_display()}"


# ============================================================================
# WELCOME MENU MODELS
# ============================================================================

class WelcomeMenu(models.Model):
    """Configurable welcome menu for incoming WhatsApp messages"""
    name = models.CharField(max_length=100, verbose_name="Nombre del Menú")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    trigger_keywords = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Palabras Clave",
        help_text="Lista de palabras que activan el menú (ej: hola, buenas, inicio)"
    )
    greeting_text = models.TextField(
        verbose_name="Texto de Bienvenida",
        help_text="Texto que se muestra antes de las opciones"
    )
    footer_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Texto al Pie",
        default="Responda con el número de su elección"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Menú de Bienvenida"
        verbose_name_plural = "Menús de Bienvenida"
        ordering = ['-is_active', 'name']

    def __str__(self):
        status = "[ACTIVO]" if self.is_active else "[INACTIVO]"
        return f"{status} {self.name}"

    def build_message_text(self):
        """Build the full menu text to send via WhatsApp"""
        lines = [self.greeting_text, ""]
        for item in self.items.all().order_by('number'):
            lines.append(f"{item.number}. {item.label}")
        if self.footer_text:
            lines.append("")
            lines.append(self.footer_text)
        return "\n".join(lines)


class WelcomeMenuItem(models.Model):
    """A single option in a WelcomeMenu"""
    menu = models.ForeignKey(WelcomeMenu, on_delete=models.CASCADE, related_name='items')
    number = models.PositiveSmallIntegerField(verbose_name="Número de Opción")
    label = models.CharField(max_length=100, verbose_name="Etiqueta")
    assigned_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='menu_items',
        verbose_name="Usuario Asignado"
    )

    class Meta:
        verbose_name = "Opción de Menú"
        verbose_name_plural = "Opciones de Menú"
        ordering = ['number']
        unique_together = [['menu', 'number']]

    def __str__(self):
        user_str = self.assigned_user.get_full_name() or self.assigned_user.username if self.assigned_user else "Sin asignar"
        return f"{self.number}. {self.label} → {user_str}"


class ContactMenuState(models.Model):
    """Tracks a contact that has been shown a welcome menu and is awaiting a selection"""
    contact = models.OneToOneField(
        Contact,
        on_delete=models.CASCADE,
        related_name='menu_state'
    )
    menu = models.ForeignKey(WelcomeMenu, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Estado de Menú"
        verbose_name_plural = "Estados de Menú"

    def __str__(self):
        return f"{self.contact} esperando selección en '{self.menu.name}'"
