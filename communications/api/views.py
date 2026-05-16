"""
REST API Views for Communications
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from ..models import (
    Contact, Conversation, Message, InternalNote, QuickReply,
    WhatsAppAccount, EmailAccount, EmailTemplate, EmailSignature
)
from .serializers import (
    ContactSerializer, ConversationSerializer, ConversationListSerializer,
    MessageSerializer, InternalNoteSerializer, QuickReplySerializer,
    WhatsAppAccountSerializer, EmailAccountSerializer,
    EmailTemplateSerializer, EmailSignatureSerializer
)
from .permissions import IsAgentOrSupervisor, IsSupervisorOrAdmin, IsAssignedAgent
from ..whatsapp_handler import WhatsAppHandler
from ..email_handler import EmailHandler
from ..assignment_system import assign_conversation_to_agent, reassign_conversation
from django.db import transaction
from ..models import EmailQueue, EmailMessage, Message, EmailAttachment
from django.core.files.base import ContentFile
from ..tasks import send_queued_email

class ConversationViewSet(viewsets.ModelViewSet):
    """API endpoint for conversations"""
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.all()
        
        # Filter by assigned agent unless supervisor/admin
        if not (user.is_superuser or user.groups.filter(name='Supervisor').exists()):
            queryset = queryset.filter(assigned_to=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by channel
        channel_filter = self.request.query_params.get('channel')
        if channel_filter:
            queryset = queryset.filter(channel=channel_filter)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(contact__client__name__icontains=search) |
                Q(subject__icontains=search) |
                Q(last_message_preview__icontains=search)
            )
        
        return queryset.order_by('-updated_at')
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign conversation to an agent"""
        conversation = self.get_object()
        agent_id = request.data.get('agent_id')
        
        from django.contrib.auth.models import User
        try:
            agent = User.objects.get(id=agent_id)
            reassign_conversation(conversation, agent, request.user)
            return Response({'status': 'assigned'})
        except User.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a conversation"""
        conversation = self.get_object()
        conversation.close()
        return Response({'status': 'closed'})
    
    @action(detail=False, methods=['get'])
    def my_conversations(self, request):
        """Get conversations assigned to current user"""
        conversations = Conversation.objects.filter(
            assigned_to=request.user,
            status__in=['normal', 'pending']
        ).order_by('-updated_at')
        
        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    """API endpoint for messages"""
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by conversation
        conversation_id = self.request.query_params.get('conversation_id')
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        
        return queryset.order_by('created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read"""
        message = self.get_object()
        message.mark_as_read()
        return Response({'status': 'read'})


class InternalNoteViewSet(viewsets.ModelViewSet):
    """API endpoint for internal notes"""
    queryset = InternalNote.objects.all()
    serializer_class = InternalNoteSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class QuickReplyViewSet(viewsets.ModelViewSet):
    """API endpoint for quick replies"""
    queryset = QuickReply.objects.all()
    serializer_class = QuickReplySerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Show global quick replies and user's own
        queryset = queryset.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )
        
        # Filter by channel
        channel = self.request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(Q(channel=channel) | Q(channel='both'))
        
        return queryset.order_by('-usage_count', 'title')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WhatsAppAccountViewSet(viewsets.ModelViewSet):
    """API endpoint for WhatsApp accounts"""
    queryset = WhatsAppAccount.objects.all()
    serializer_class = WhatsAppAccountSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a WhatsApp message"""
        account = self.get_object()
        handler = WhatsAppHandler(account)
        
        to_number = request.data.get('to_number')
        message_text = (request.data.get('message') or '').strip()
        conversation_id = request.data.get('conversation_id')
        attachments = request.FILES.getlist('attachments')
        
        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                conversation = None
        if not attachments:
            if not message_text:
                return Response({'error': 'Por favor escribe un mensaje o adjunta archivos antes de enviar.'}, status=status.HTTP_400_BAD_REQUEST)

            success, result = handler.send_text_message(to_number, message_text, conversation=conversation, sender_user=request.user)
            if success:
                return Response({'status': 'sent', 'message_id': result})
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)

        message_ids = []
        for idx, f in enumerate(attachments):
            f.seek(0)
            media_type = handler.detect_media_type(f)

            success, media_id_or_error = handler.upload_media(f)
            if not success:
                return Response({'error': media_id_or_error}, status=status.HTTP_400_BAD_REQUEST)

            caption = message_text if (idx == 0 and message_text) else None
            filename = getattr(f, 'name', None) if media_type == 'document' else None

            success, msg_id_or_error = handler.send_media_message(
                to_number=to_number,
                media_type=media_type,
                media_id=media_id_or_error,
                caption=caption,
                filename=filename,
                conversation=conversation,
                uploaded_file=f,
                sender_user=request.user
            )
            if not success:
                return Response({'error': msg_id_or_error}, status=status.HTTP_400_BAD_REQUEST)
            message_ids.append(msg_id_or_error)

        return Response({'status': 'sent', 'message_ids': message_ids})

    @action(detail=True, methods=['post'])
    def send_template(self, request, pk=None):
        account = self.get_object()

        from core.models import CompanySettings
        cs = CompanySettings.load()
        if not getattr(cs, 'whatsapp_templates_enabled', False):
            return Response({'error': 'Las plantillas de WhatsApp están deshabilitadas.'}, status=status.HTTP_403_FORBIDDEN)

        handler = WhatsAppHandler(account)
        to_number = request.data.get('to_number')
        conversation_id = request.data.get('conversation_id')
        template_name = (request.data.get('template_name') or request.data.get('name') or '').strip()
        language_code = (request.data.get('language_code') or request.data.get('language') or '').strip()

        if not template_name or not language_code:
            return Response({'error': 'Template y lenguaje son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                conversation = None

        body_params = []
        try:
            body_params = request.data.getlist('body_params')
        except Exception:
            raw_params = request.data.get('body_params')
            if isinstance(raw_params, list):
                body_params = raw_params
            elif isinstance(raw_params, str) and raw_params.strip():
                body_params = [p.strip() for p in raw_params.split(',') if p.strip()]

        body_params = [str(p) for p in body_params if str(p).strip() != '']

        components = None
        if body_params:
            components = [{
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in body_params]
            }]

        content_for_db = f"📄 Plantilla: {template_name}"

        success, result = handler.send_template_message(
            to_number=to_number,
            template_name=template_name,
            language_code=language_code,
            components=components,
            conversation=conversation,
            content_for_db=content_for_db,
            sender_user=request.user
        )

        if success:
            return Response({'status': 'sent', 'message_id': result})
        return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class EmailAccountViewSet(viewsets.ModelViewSet):
    """API endpoint for email accounts"""
    queryset = EmailAccount.objects.all()
    serializer_class = EmailAccountSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.groups.filter(name='Supervisor').exists():
            return qs
        user_email = (getattr(user, 'email', None) or '').strip()
        if user_email:
            return qs.filter(Q(user=user) | Q(user__isnull=True, email_address__iexact=user_email))
        return qs.filter(user=user)
    
    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """Trigger immediate email sync"""
        account = self.get_object()
        
        from ..tasks import sync_email_account
        sync_email_account.delay(account.id)
        
        return Response({'status': 'sync_queued'})
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Send an email asynchronously"""
        account = self.get_object()
        if not (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
            user_email = (getattr(request.user, 'email', None) or '').strip()
            allowed = (
                account.user_id == request.user.id
                or (
                    user_email
                    and account.user_id is None
                    and (account.email_address or '').strip().lower() == user_email.lower()
                )
            )
            if not allowed:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        to_addresses = request.data.get('to_addresses', [])
        if isinstance(to_addresses, str):
            to_addresses = [addr.strip() for addr in to_addresses.split(',') if addr.strip()]

        if not to_addresses:
            return Response({'error': 'Recipient addresses are required'}, status=status.HTTP_400_BAD_REQUEST)

        subject = request.data.get('subject') or '(Sin asunto)'
        body = request.data.get('body', '')
        html_body = request.data.get('html_body', '')
        conversation_id = request.data.get('conversation_id')
        attachments = request.FILES.getlist('attachments')
        agent_name = request.user.get_full_name() or request.user.username

        cc_addresses = request.data.get('cc_addresses', [])
        if isinstance(cc_addresses, str):
            cc_addresses = [addr.strip() for addr in cc_addresses.split(',') if addr.strip()]

        bcc_addresses = request.data.get('bcc_addresses', [])
        if isinstance(bcc_addresses, str):
            bcc_addresses = [addr.strip() for addr in bcc_addresses.split(',') if addr.strip()]

        conversation = None
        if conversation_id not in (None, '', []):
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except (Conversation.DoesNotExist, ValueError, TypeError):
                conversation = None

        source_email_message_id = request.data.get('source_email_message_id')
        source_email = None
        if source_email_message_id not in (None, '', [], 'null'):
            try:
                source_email = (
                    EmailMessage.objects.select_related('message', 'message__conversation', 'email_account')
                    .prefetch_related('attachments')
                    .get(pk=int(source_email_message_id))
                )
            except (EmailMessage.DoesNotExist, ValueError, TypeError):
                source_email = None

        if source_email is not None:
            src_conv = source_email.message.conversation if source_email.message_id else None
            allowed = (
                request.user.is_superuser
                or request.user.groups.filter(name='Supervisor').exists()
                or (src_conv and src_conv.assigned_to_id == request.user.id)
                or (source_email.email_account and source_email.email_account.user_id == request.user.id)
            )
            if not allowed:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        if conversation is None:
            handler = EmailHandler(account)
            primary_to = (to_addresses[0] or '').strip()
            if not primary_to:
                return Response({'error': 'Recipient addresses are required'}, status=status.HTTP_400_BAD_REQUEST)
            contact = handler.get_or_create_contact_from_email(primary_to)
            conversation = handler.get_or_create_conversation(contact, subject, None, None)

        if body and not html_body and ('<' in body and '>' in body):
            html_body = body
            from django.utils.html import strip_tags
            body = strip_tags(body)

        if source_email is not None:
            from django.utils.html import strip_tags
            forward_plain = source_email.plain_body or ''
            forward_html = source_email.html_body or ''
            if not forward_plain and forward_html:
                forward_plain = strip_tags(forward_html)

            forward_plain = ("\n\n---------- Mensaje reenviado ----------\n" + forward_plain).strip()
            if forward_html:
                forward_html = "<br><br><hr><p><b>Mensaje reenviado</b></p>" + forward_html
            elif forward_plain:
                forward_html = "<br><br><hr><pre style=\"white-space: pre-wrap;\">" + forward_plain.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre>"

            if body:
                body = (body.rstrip() + "\n\n" + forward_plain).strip()
            else:
                body = forward_plain

            if html_body:
                html_body = (html_body + forward_html)
            else:
                html_body = forward_html

        if body:
            body += f"\n\n---\n{agent_name}"

        if html_body:
            html_body += f"""
            <br><br>
            <hr>
            <p>
                <b>{agent_name}</b><br>
                {account.name}
            </p>
            """

        try:
            with transaction.atomic():
                content = body or html_body
                if not content and attachments:
                    content = f"📎 {len(attachments)} archivo(s) adjunto(s)"
                if not content:
                    content = '(Empty message)'

                msg = Message.objects.create(
                    conversation=conversation,
                    message_type='email',
                    direction='outbound',
                    content=content,
                    sender_name=account.name,
                    metadata={'status': 'queued'}
                )

                email_msg = EmailMessage.objects.create(
                    message=msg,
                    email_account=account,
                    subject=subject,
                    html_body=html_body,
                    plain_body=body,
                    email_message_id=f"pending-{msg.id}",
                    to_addresses=to_addresses,
                    cc_addresses=cc_addresses,
                    bcc_addresses=bcc_addresses,
                    from_address=account.email_address
                )

                if source_email is not None:
                    for src_att in source_email.attachments.all():
                        try:
                            src_att.file.open('rb')
                            file_data = src_att.file.read()
                        finally:
                            try:
                                src_att.file.close()
                            except Exception:
                                pass
                        copied = EmailAttachment.objects.create(
                            email_message=email_msg,
                            filename=src_att.filename,
                            mime_type=src_att.mime_type,
                            size=src_att.size,
                        )
                        copied.file.save(src_att.filename, ContentFile(file_data), save=True)

                for attachment in attachments:
                    file_data = attachment.read()
                    attachment.seek(0)
                    att = EmailAttachment.objects.create(
                        email_message=email_msg,
                        filename=attachment.name,
                        mime_type=getattr(attachment, 'content_type', 'application/octet-stream'),
                        size=attachment.size,
                    )
                    att.file.save(attachment.name, ContentFile(file_data), save=True)

                queue_entry = EmailQueue.objects.create(
                    email_account=account,
                    to_addresses=to_addresses,
                    cc_addresses=cc_addresses,
                    bcc_addresses=bcc_addresses,
                    subject=subject,
                    html_body=html_body,
                    plain_body=body,
                    conversation=conversation,
                    email_message=email_msg,
                    status='pending'
                )

            send_queued_email.apply_async(args=[queue_entry.id])

            return Response({'status': 'queued', 'queue_id': queue_entry.id}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """API endpoint for email templates"""
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class EmailSignatureViewSet(viewsets.ModelViewSet):
    """API endpoint for email signatures"""
    queryset = EmailSignature.objects.all()
    serializer_class = EmailSignatureSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
