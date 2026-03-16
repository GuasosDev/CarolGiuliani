from django.contrib import admin
from django import forms
from .models import (
    Contact, Conversation, Message, InternalNote, QuickReply,
    WhatsAppAccount, WhatsAppMessage, ConversationAssignment,
    EmailAccount, EmailMessage, EmailThread, EmailTemplate,
    EmailSignature, EmailAttachment, EmailQueue
)
from .forms import EmailAccountAdminForm 


# ============================================================================
# INLINE ADMINS
# ============================================================================

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('created_at', 'is_read', 'read_at')
    fields = ('direction', 'content', 'sender', 'is_read', 'created_at')


class InternalNoteInline(admin.TabularInline):
    model = InternalNote
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('author', 'content', 'is_pinned', 'created_at')


class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0
    readonly_fields = ('filename', 'mime_type', 'size', 'created_at')


# ============================================================================
# MODEL ADMINS
# ============================================================================

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('client', 'whatsapp_number', 'preferred_channel', 'created_at')
    list_filter = ('preferred_channel', 'created_at')
    search_fields = ('client__name', 'client__email', 'whatsapp_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('contact', 'channel', 'status', 'assigned_to', 'priority', 'created_at', 'last_message_at')
    list_filter = ('channel', 'status', 'priority', 'created_at')
    search_fields = ('contact__client__name', 'subject')
    readonly_fields = ('created_at', 'updated_at', 'closed_at', 'last_message_at')
    inlines = [MessageInline, InternalNoteInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('contact', 'channel', 'subject')
        }),
        ('Estado y Asignación', {
            'fields': ('status', 'assigned_to', 'priority', 'tags')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at', 'closed_at', 'last_message_at')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'message_type', 'direction', 'sender', 'is_read', 'created_at')
    list_filter = ('message_type', 'direction', 'is_read', 'created_at')
    search_fields = ('content', 'conversation__contact__client__name')
    readonly_fields = ('created_at', 'updated_at', 'read_at')


@admin.register(InternalNote)
class InternalNoteAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'author', 'is_pinned', 'created_at')
    list_filter = ('is_pinned', 'created_at')
    search_fields = ('content', 'conversation__contact__client__name', 'author__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(QuickReply)
class QuickReplyAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'category', 'usage_count', 'is_global', 'created_by')
    list_filter = ('channel', 'category', 'is_global')
    search_fields = ('title', 'content')
    readonly_fields = ('usage_count', 'created_at', 'updated_at')


@admin.register(WhatsAppAccount)
class WhatsAppAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'phone_number', 'is_active')
        }),
        ('Configuración de API', {
            'fields': ('phone_number_id', 'business_account_id', 'access_token', 'webhook_verify_token')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_message_id', 'wa_message_type', 'delivery_status', 'created_at')
    list_filter = ('wa_message_type', 'delivery_status', 'created_at')
    search_fields = ('whatsapp_message_id', 'message__content')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ConversationAssignment)
class ConversationAssignmentAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'agent', 'assigned_by', 'assigned_at', 'is_active')
    list_filter = ('is_active', 'assigned_at')
    search_fields = ('conversation__contact__client__name', 'agent__username')
    readonly_fields = ('assigned_at', 'unassigned_at')


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    form = EmailAccountAdminForm 
    list_display = ('name', 'email_address', 'provider', 'sync_enabled', 'is_active', 'last_sync_at')
    list_filter = ('provider', 'sync_enabled', 'is_active')
    search_fields = ('name', 'email_address')
    readonly_fields = ('created_at', 'updated_at', 'last_sync_at')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'email_address', 'provider', 'is_active', 'user')
        }),
        ('Configuración IMAP', {
            'fields': ('imap_host', 'imap_port', 'imap_use_ssl')
        }),
        ('Configuración SMTP', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_use_tls')
        }),
        ('Credenciales', {
            'fields': ('username','password')  # Password handled separately for security
        }),
        ('Sincronización', {
            'fields': ('sync_enabled', 'sync_interval', 'last_sync_at')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'from_address', 'message', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('subject', 'from_address', 'message_id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [EmailAttachmentInline]


@admin.register(EmailThread)
class EmailThreadAdmin(admin.ModelAdmin):
    list_display = ('subject', 'conversation', 'first_message_at', 'last_message_at')
    list_filter = ('created_at',)
    search_fields = ('subject',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_global', 'created_by', 'created_at')
    list_filter = ('category', 'is_global', 'created_at')
    search_fields = ('name', 'description', 'subject_template')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailSignature)
class EmailSignatureAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'is_default', 'created_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('user__username', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'email_message', 'mime_type', 'size', 'created_at')
    list_filter = ('mime_type', 'created_at')
    search_fields = ('filename',)
    readonly_fields = ('created_at',)


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display = ('subject', 'email_account', 'status', 'retry_count', 'scheduled_at', 'sent_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject',)
    readonly_fields = ('created_at', 'updated_at', 'sent_at')
    
    actions = ['retry_failed_emails']
    
    def retry_failed_emails(self, request, queryset):
        """Admin action to retry failed emails"""
        failed_emails = queryset.filter(status='failed')
        count = failed_emails.update(status='pending', retry_count=0, last_error=None)
        self.message_user(request, f'{count} emails marcados para reintento.')
    retry_failed_emails.short_description = "Reintentar emails fallidos"
