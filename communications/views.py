"""
Django views for communications web interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.utils import timezone
from django.template.loader import get_template
from xhtml2pdf import pisa
import json
import logging
import re
import uuid
import os
import mimetypes
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from .models import Conversation, Contact, Message, WhatsAppAccount, EmailAccount, QuickReply, WelcomeMenu, WelcomeMenuItem,EmailMessage, InternalNote
from .models import InternalChatMessage, InternalChatReadState
from .forms import QuickReplyForm, ConversationReportForm, ClientQuickCreateForm
from .whatsapp_handler import process_whatsapp_webhook
from .assignment_system import get_agent_conversations, assign_conversation_to_agent
from clients.models import Client
from core.views import GenericCreateView
from django.db.models import Prefetch
logger = logging.getLogger(__name__)

@login_required
def add_conversation_note(request, conversation_id):
    """View to add a note to a conversation and return the notes list partial"""
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            InternalNote.objects.create(
                conversation=conversation,
                author=request.user,
                content=content
            )
    
    notes = conversation.internal_notes.all().order_by('-created_at')
    return render(request, 'communications/partials/notes_list_partial.html', {
        'notes': notes,
    })

def get_agent_conversations(user):
    """
    Devuelve todas las conversaciones visibles para el usuario:
    1. Conversaciones asignadas a él (WhatsApp o Email).
    2. Conversaciones de Email vinculadas a sus cuentas configuradas.
    3. Todas si es superusuario o supervisor.
    """
    if user.is_superuser or user.groups.filter(name='Supervisor').exists():
        return Conversation.objects.all()
        
    # IDs de conversaciones de email vinculadas a las cuentas del usuario
    email_convo_ids = EmailMessage.objects.filter(
        email_account__user=user
    ).values_list('message__conversation_id', flat=True)
    
    # Retornar conversaciones asignadas al usuario O vinculadas por email
    return Conversation.objects.filter(
        models.Q(assigned_to=user) | models.Q(id__in=email_convo_ids)
    ).distinct()
@login_required
def dashboard(request):
    """Main communication dashboard"""
    # Get user's conversations
    status_filter = request.GET.get('status')
    channel_filter = request.GET.get('channel')
    user_filter = request.GET.get('user')
    
    base_qs = get_agent_conversations(request.user).select_related(
    "contact__client"
).prefetch_related("messages")
    
    # Base filtering
    conversations = base_qs
    
    # Filter by specific user (only for supervisors/admins)
    if user_filter and (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
        conversations = conversations.filter(assigned_to_id=user_filter)
    
    if channel_filter:
        if channel_filter != 'multichannel':
            conversations = conversations.filter(channel=channel_filter)
        
        # If filtering by channel, we generally want to see all unless specific status is requested
        if status_filter and status_filter != 'all':
            conversations = conversations.filter(status=status_filter)
    else:
        # Default behavior (no channel filter)
        if not status_filter:
            status_filter = 'normal' # Default status
            
        if status_filter == 'inbox':
            # Inbox logic: Group by client
            # We want to show all conversations grouped by client
            pass # Filtering handled below/separately
        elif status_filter == 'pending':
            # Show all pending conversations
            conversations = conversations.filter(status='pending')
        elif status_filter == 'unread':
            # Show conversations with unread inbound messages
           conversations = conversations.filter(
    messages__direction='inbound',
    messages__is_read=False
).distinct()
        elif status_filter != 'all':
            conversations = conversations.filter(status=status_filter)
        
    if status_filter == 'inbox':
        # Group conversations by client in Python
        from collections import defaultdict
        client_groups = defaultdict(list)
        
        # Get recent conversations from all statuses
        inbox_qs = base_qs.select_related('contact__client').prefetch_related('messages').order_by('-updated_at')[:100]
        
        for conv in inbox_qs:
            if conv.contact and conv.contact.client:
                client = conv.contact.client
                client_groups[client].append(conv)
            
        grouped_conversations = []
        for client, convs in client_groups.items():
            grouped_conversations.append({
                'client': client,
                'conversations': convs,
                'latest_update': convs[0].updated_at if convs else None
            })
            
        # Sort groups by latest activity
        grouped_conversations.sort(key=lambda x: x['latest_update'] or '', reverse=True)
        
        # We don't use the main 'conversations' queryset for the list in this case
        # But we keep it for other context if needed
    else:
        conversations = conversations.order_by('-updated_at')[:50]
        grouped_conversations = None

    clients = Client.objects.all().order_by('name')[:200]
    
    # Get users for filtering (only for supervisors/admins)
    from django.contrib.auth.models import User
    available_users = []
    if request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists():
        available_users = User.objects.filter(is_active=True).order_by('first_name', 'username')
    
    # Get counts using helper
    counts = _get_conversation_counts(request.user)
    
    # Calculate percentages for donut chart
    whatsapp_count = counts['whatsapp_count']
    email_count = counts['email_count']
    total_channel_count = counts['total_channel_count']
    
    if total_channel_count > 0:
        whatsapp_percent = int((whatsapp_count / total_channel_count) * 100)
        email_percent = int((email_count / total_channel_count) * 100)
        # Adjust so they sum to 100 if there's rounding error
        if whatsapp_percent + email_percent < 100:
            if whatsapp_count >= email_count:
                whatsapp_percent += (100 - (whatsapp_percent + email_percent))
            else:
                email_percent += (100 - (whatsapp_percent + email_percent))
    else:
        whatsapp_percent = 0
        email_percent = 0
    
    context = {
        'conversations': conversations,
        'grouped_conversations': grouped_conversations,
        'whatsapp_percent': whatsapp_percent,
        'email_percent': email_percent,
        'current_status': status_filter,
        'current_channel': channel_filter,
        'current_user': user_filter,
        'available_users': available_users,
        'clients': clients,
        **counts # Unpack counts into context
    }

    return render(request, 'communications/dashboard.html', context)


def _get_conversation_counts(user):
    """Helper to get conversation counts for the sidebar"""
    base_qs = get_agent_conversations(user)
    
    whatsapp_count = base_qs.filter(channel='whatsapp').count()
    email_count = base_qs.filter(channel='email').count()
    read_state, _ = InternalChatReadState.objects.get_or_create(user=user)
    last_read_at = read_state.last_read_at
    internal_unread_count = InternalChatMessage.objects.exclude(author=user)
    if last_read_at:
        internal_unread_count = internal_unread_count.filter(created_at__gt=last_read_at)
    internal_unread_count = internal_unread_count.count()
    
    return {
        'normal_count': base_qs.filter(status='normal').count(),
        'pending_count': base_qs.filter(status='pending').count(),
        'closed_count': base_qs.filter(status='closed').count(),
        'unread_count': base_qs.filter(messages__is_read=False, messages__direction='inbound').distinct().count(),
        'whatsapp_count': whatsapp_count,
        'email_count': email_count,
        'total_channel_count': whatsapp_count + email_count,
        'internal_unread_count': internal_unread_count,
    }


@login_required
def open_client_whatsapp(request, client_id, channel='whatsapp'):
    client = get_object_or_404(Client, pk=client_id)
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': channel}
    )
    
    conversation = Conversation.objects.filter(
        contact=contact,
        channel=channel,
        status__in=['normal', 'pending','open', 'assigned']
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(
            contact=contact,
            channel=channel,
            status='normal',
            priority='normal',
            subject=f"Conversación con {client.name}" if channel == 'email' else None
        )
        assign_conversation_to_agent(conversation, agent=request.user, assigned_by=request.user)
    
    from django.urls import reverse
    url = reverse('communications:dashboard')
    return redirect(f'{url}?channel={channel}&conversation={conversation.pk}')


@login_required
def contact_details_modal(request, conversation_id):
    """View to show contact details in a modal"""
    conversation = get_object_or_404(
        Conversation.objects.select_related('contact', 'contact__client'),
        pk=conversation_id
    )

    if conversation.contact and not conversation.contact.client:
        matched_contact = None
        wa = (conversation.contact.whatsapp_number or "").strip()
        digits = re.sub(r"\D+", "", wa)
        if len(digits) >= 10:
            suffix = digits[-10:]
            matched_contact = Contact.objects.select_related('client').filter(
                whatsapp_number__endswith=suffix,
                client__isnull=False
            ).first()

            if not matched_contact:
                client_match = Client.objects.filter(phone__endswith=suffix).first()
                if client_match:
                    contact_for_client = Contact.objects.filter(client=client_match).first()
                    if contact_for_client:
                        matched_contact = contact_for_client
                    else:
                        conversation.contact.client = client_match
                        conversation.contact.save(update_fields=['client'])

        if not conversation.contact.client and conversation.channel == 'email':
            from_address = EmailMessage.objects.filter(
                message__conversation=conversation,
                message__direction='inbound'
            ).order_by('-created_at').values_list('from_address', flat=True).first()
            if from_address:
                client_match = Client.objects.filter(email__iexact=from_address).first()
                if client_match:
                    contact_for_client = Contact.objects.filter(client=client_match).first()
                    if contact_for_client:
                        matched_contact = contact_for_client
                    else:
                        conversation.contact.client = client_match
                        conversation.contact.save(update_fields=['client'])

        if matched_contact and matched_contact.pk != conversation.contact_id:
            if wa and not matched_contact.whatsapp_number and conversation.channel == 'whatsapp':
                matched_contact.whatsapp_number = wa
                matched_contact.save(update_fields=['whatsapp_number'])
            conversation.contact = matched_contact
            conversation.save(update_fields=['contact'])
            conversation = Conversation.objects.select_related('contact', 'contact__client').get(pk=conversation.pk)

    notes = conversation.internal_notes.all().order_by('-created_at')
    
    return render(request, 'communications/partials/contact_details_modal.html', {
        'conversation': conversation,
        'notes': notes,
    })


@login_required
def quick_create_client_modal(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related('contact', 'contact__client'),
        pk=conversation_id
    )

    if conversation.contact and conversation.contact.client:
        notes = conversation.internal_notes.all().order_by('-created_at')
        return render(request, 'communications/partials/contact_details_modal.html', {
            'conversation': conversation,
            'notes': notes,
        })

    phone_guess = ''
    if conversation.contact:
        phone_guess = conversation.contact.whatsapp_number or conversation.contact.get_display_phone() or ''

    if request.method == 'POST':
        form = ClientQuickCreateForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.email = (client.email or '').strip()

            if not client.email:
                while True:
                    candidate = f"no-email-{uuid.uuid4().hex}@example.invalid"
                    if not Client.objects.filter(email__iexact=candidate).exists():
                        client.email = candidate
                        break

            client.save()

            if conversation.contact:
                conversation.contact.client = client
                if not conversation.contact.whatsapp_number and phone_guess:
                    conversation.contact.whatsapp_number = phone_guess
                conversation.contact.save(update_fields=['client', 'whatsapp_number'])

            notes = conversation.internal_notes.all().order_by('-created_at')
            conversation = Conversation.objects.select_related('contact', 'contact__client').get(pk=conversation.pk)
            return render(request, 'communications/partials/contact_details_modal.html', {
                'conversation': conversation,
                'notes': notes,
            })
    else:
        initial = {
            'name': conversation.get_display_name(),
            'phone': (phone_guess or '').strip(),
        }
        form = ClientQuickCreateForm(initial=initial)

    return render(request, 'communications/partials/quick_create_client_modal.html', {
        'conversation': conversation,
        'form': form,
    })


@login_required
def internal_chat(request):
    InternalChatReadState.objects.update_or_create(
        user=request.user,
        defaults={'last_read_at': timezone.now()}
    )
    counts = _get_conversation_counts(request.user)
    return render(request, 'communications/internal_chat.html', {**counts, 'current_channel': 'internal'})


@login_required
def internal_chat_messages_partial(request):
    InternalChatReadState.objects.update_or_create(
        user=request.user,
        defaults={'last_read_at': timezone.now()}
    )
    messages = InternalChatMessage.objects.select_related('author').order_by('-created_at')[:200]
    messages = reversed(list(messages))
    return render(request, 'communications/partials/internal_chat_messages.html', {
        'messages': messages,
    })


@login_required
@require_http_methods(["POST"])
def internal_chat_send(request):
    content = (request.POST.get('content') or '').strip()
    if not content:
        return JsonResponse({'error': 'Mensaje vacío'}, status=400)

    InternalChatMessage.objects.create(author=request.user, content=content)
    InternalChatReadState.objects.update_or_create(
        user=request.user,
        defaults={'last_read_at': timezone.now()}
    )
    return JsonResponse({'status': 'sent'})


@login_required
def forward_messages_modal(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    raw_ids = (request.GET.get('message_ids') or '').strip()
    ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    messages = Message.objects.filter(conversation=conversation, id__in=ids).order_by('created_at')

    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('first_name', 'username')

    return render(request, 'communications/partials/forward_messages_modal.html', {
        'conversation': conversation,
        'message_ids': ','.join(str(m.id) for m in messages),
        'messages_count': messages.count(),
        'users': users,
    })


@login_required
@require_http_methods(["POST"])
def forward_messages_send(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id)

    recipient_id = request.POST.get('recipient_id')
    try:
        recipient = User.objects.get(pk=recipient_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario inválido'}, status=400)

    raw_ids = (request.POST.get('message_ids') or '').strip()
    ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    if not ids:
        return JsonResponse({'error': 'No hay mensajes seleccionados'}, status=400)

    selected = list(Message.objects.filter(conversation=conversation, id__in=ids).order_by('created_at'))
    if not selected:
        return JsonResponse({'error': 'No hay mensajes para reenviar'}, status=400)

    InternalChatMessage.objects.create(
        author=request.user,
        content=f"Para @{recipient.username}\nReenviado de {conversation.get_display_name()} (#{conversation.id})"
    )

    for m in selected:
        who = "Cliente" if m.direction == 'inbound' else (m.sender.username if m.sender else "Sistema")
        ts = m.created_at.strftime("%d/%m %H:%M")
        msg = InternalChatMessage(
            author=request.user,
            content=f"[{ts}] {who}: {m.content}".strip()
        )

        if m.file:
            try:
                m.file.open('rb')
                data = m.file.read()
                m.file.close()

                original_name = os.path.basename(getattr(m.file, 'name', '') or 'adjunto')
                mime_type = (m.metadata or {}).get('media_mime_type') or mimetypes.guess_type(original_name)[0] or ''
                normalized_mime = (mime_type or '').split(';')[0].strip().lower()

                msg.original_filename = original_name
                msg.mime_type = normalized_mime or mime_type
                msg.file.save(original_name, ContentFile(data), save=False)
            except Exception:
                try:
                    m.file.close()
                except Exception:
                    pass

        msg.save()

    return JsonResponse({'status': 'sent'})


@login_required
def change_conversation_status(request, pk):
    """Change status of a conversation"""
    conversation = get_object_or_404(Conversation, pk=pk)
    
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists() or
            conversation.assigned_to == request.user):
        return HttpResponse('Unauthorized', status=403)
        
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['normal', 'pending', 'closed']:
            if new_status == 'closed':
                conversation.close()
            else:
                conversation.status = new_status
                conversation.save()
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)                 
    return redirect('communications:conversation_detail', pk=conversation.pk)


class ContactCreateView(GenericCreateView):
    model = Contact
    fields = ['client', 'whatsapp_number', 'preferred_channel', 'notes']
    title = "Nuevo Contacto de Comunicación"
    success_url = reverse_lazy('communications:dashboard')


@login_required
def conversation_detail(request, pk):
    """Conversation detail view"""
    try:
        conversation = get_object_or_404(Conversation, pk=pk)
        
        # Check permission (agents can only see their own, supervisors see all)
        # Relaxed check for debugging: if it's in the allowed list for the user, show it.
        # This prevents 401s on valid but unassigned conversations visible in dashboard
        if not (request.user.is_superuser or 
                request.user.groups.filter(name='Supervisor').exists() or
                conversation.assigned_to == request.user):
            # Check if user can see it via get_agent_conversations (e.g. unassigned pool)
                    if not get_agent_conversations(request.user).filter(pk=pk).exists():
                         # Return 200 even for error so HTMX displays the message
                         return HttpResponse('<div class="alert alert-danger m-3">No tienes permiso para ver esta conversación.</div>', status=200)
                
                # Mark inbound unread messages as read
        conversation.messages.filter(direction='inbound', is_read=False).update(is_read=True, read_at=timezone.now())
    
        messages = conversation.messages.all().order_by('created_at')
        notes = conversation.internal_notes.all()
        
        # Sidebar conversations (filtered by current conversation's status or default to normal)
        status_filter = request.GET.get('status', conversation.status)
        channel_filter = request.GET.get('channel')
        
        sidebar_qs = get_agent_conversations(request.user)
        
        if channel_filter:
            sidebar_qs = sidebar_qs.filter(channel=channel_filter)
            
        sidebar_conversations = sidebar_qs.filter(
            status=status_filter
        ).order_by('-updated_at')[:50]
        
        whatsapp_account = WhatsAppAccount.objects.filter(is_active=True).first()
        email_account = EmailAccount.objects.filter(is_active=True).first()
        
        # Get counts using helper
        counts = _get_conversation_counts(request.user)
        
        # Get quick replies
        quick_replies = QuickReply.objects.filter(
            models.Q(created_by=request.user) | models.Q(is_global=True)
        ).order_by('shortcut', 'title')

        # Get users available for conversation transfer
        from django.contrib.auth.models import User as AuthUser
        transfer_users = AuthUser.objects.filter(is_active=True).exclude(
            pk=request.user.pk
        ).order_by('first_name', 'username')

        context = {
            'conversation': conversation,
            'messages': messages,
            'notes': notes,
            'clients': Client.objects.all().order_by('name')[:100],
            'sidebar_conversations': sidebar_conversations,
            'current_status': status_filter,
            'current_channel': channel_filter,
            'whatsapp_account': whatsapp_account,
            'email_account': email_account,
            'quick_replies': quick_replies,
            'transfer_users': transfer_users,
            **counts # Unpack counts into context
        }
        
        # Check if it's an HTMX request (using both standard header and META for robustness)
        # Also check for explicit partial parameter to force partial rendering
        if request.headers.get('HX-Request') or request.META.get('HTTP_HX_REQUEST') or 'partial' in request.GET:
            return render(request, 'communications/partials/conversation_content.html', context)
        
        return render(request, 'communications/conversation_detail.html', context)
    except Exception as e:
                logger.exception("Error in conversation_detail")
                if request.headers.get('HX-Request') or request.META.get('HTTP_HX_REQUEST') or 'partial' in request.GET:
                    # Return 200 even for error so HTMX displays the message
                    return HttpResponse(f'<div class="alert alert-danger m-3">Error al cargar la conversación: {str(e)}</div>', status=200)
                raise


@login_required
def contact_360_view(request, pk):
    """360° contact view showing all communications"""
    contact = get_object_or_404(Contact, pk=pk)
    
    conversations = contact.conversations.all().order_by('-created_at')
    
    # Get all messages across all conversations
    all_messages = Message.objects.filter(
        conversation__contact=contact
    ).order_by('-created_at')[:100]
    
    context = {
        'contact': contact,
        'conversations': conversations,
        'recent_messages': all_messages,
    }
    
    return render(request, 'communications/contact_360.html', context)


from django.utils import timezone
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, DurationField
from datetime import timedelta

@login_required
def supervisor_dashboard(request):
    # Check if user has permission (Supervisor or Superuser)
    # Also allow manual testing with view_as
    mode = request.session.get('view_as')
    is_supervisor = request.user.is_superuser or \
                    mode == 'supervisor' or \
                    request.user.groups.filter(name='Supervisor').exists()

    if not is_supervisor:
        return redirect('communications:agent_dashboard')
    
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    
    # Get filters from request
    agent_id = request.GET.get('agent')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    channel_filter = request.GET.get('channel')
    
    # Get all agents for the filter dropdown
    agents = User.objects.filter(is_staff=True, is_active=True)
    
    # Base QuerySet for metrics
    conversations_qs = Conversation.objects.all()
    
    # Apply filters to the QuerySet
    if agent_id:
        conversations_qs = conversations_qs.filter(assigned_to_id=agent_id)
    if start_date:
        conversations_qs = conversations_qs.filter(created_at__date__gte=start_date)
    if end_date:
        conversations_qs = conversations_qs.filter(created_at__date__lte=end_date)
    if channel_filter:
        conversations_qs = conversations_qs.filter(channel=channel_filter)
    
    # Get metrics
    total_conversations = conversations_qs.count()
    open_conversations = conversations_qs.filter(status__in=['normal', 'pending']).count()
    
    # Closed today logic (reflecting filters if provided)
    closed_qs = conversations_qs.filter(status='closed')
    if not (start_date or end_date):
        closed_today = closed_qs.filter(closed_at__date=timezone.now().date()).count()
    else:
        closed_today = closed_qs.count()
    
    # Channel distribution (Filtered)
    channel_stats = conversations_qs.values('channel').annotate(count=Count('id'))
    
    # Agent workload
    agent_stats = []
    # If a specific agent is filtered, we only show that one in the table, otherwise all
    stat_agents = agents.filter(id=agent_id) if agent_id else agents
    
    for agent in stat_agents:
        active_count = Conversation.objects.filter(
            assigned_to=agent,
            status__in=['normal', 'pending']
        )
        # We don't usually filter current workload by historical date, but for consistency:
        if start_date: active_count = active_count.filter(created_at__date__gte=start_date)
        if end_date: active_count = active_count.filter(created_at__date__lte=end_date)
        
        agent_stats.append({
            'agent': agent,
            'active_conversations': active_count.count()
        })
    
    context = {
        'total_conversations': total_conversations,
        'open_conversations': open_conversations,
        'closed_today': closed_today,
        'agent_stats': agent_stats,
        'channel_stats': channel_stats,
        'agents': agents,
        'filters': {
            'agent': agent_id,
            'start_date': start_date,
            'end_date': end_date,
            'channel': channel_filter,
        }
    }

    return render(request, 'communications/supervisor_dashboard.html', context)


@login_required
def agent_dashboard(request):
    from django.db.models import Count, Q
    
    # My specific metrics
    open_conversations = Conversation.objects.filter(
        assigned_to=request.user, 
        status__in=['normal', 'pending']
    ).count()
    
    closed_today = Conversation.objects.filter(
        assigned_to=request.user,
        status='closed',
        closed_at__date=timezone.now().date()
    ).count()
    
    # Recent activity
    recent_conversations = Conversation.objects.filter(
        assigned_to=request.user
    ).select_related('contact').order_by('-updated_at')[:5]
    
    context = {
        'open_conversations': open_conversations,
        'closed_today': closed_today,
        'recent_conversations': recent_conversations,
    }
    return render(request, 'communications/agent_dashboard.html', context)


@login_required
def role_dashboard(request):
    mode = request.session.get('view_as')
    if mode == 'supervisor' or request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists():
        return redirect('communications:supervisor_dashboard')
    return redirect('communications:agent_dashboard')



@login_required
def settings_view(request):
    """Settings page for accounts and configuration"""
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()):
        return HttpResponse('Unauthorized', status=401)
    
    from .models import WhatsAppAccount, EmailAccount
    from django.contrib.auth.models import User, Group
    from core.models import WorkArea, UserRole
    
    whatsapp_accounts = WhatsAppAccount.objects.all()
    email_accounts = EmailAccount.objects.all()
    users = User.objects.all().select_related('userprofile', 'userprofile__work_area', 'userprofile__user_role')
    work_areas = WorkArea.objects.all()
    roles = UserRole.objects.all()
    groups = Group.objects.all().prefetch_related('permissions')
    
    context = {
        'whatsapp_accounts': whatsapp_accounts,
        'email_accounts': email_accounts,
        'users': users,
        'work_areas': work_areas,
        'roles': roles,
        'privileges': groups,
    }
    
    return render(request, 'communications/settings.html', context)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """WhatsApp Business API webhook endpoint"""
    print("ENTRÓ AL WEBHOOK")
    print("METHOD:", request.method)
    print("BODY:", request.body)
    if request.method == 'GET':
        # Webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        logger.info(f"Webhook verification attempt: mode={mode}, token={token}, challenge={challenge}")
        
        # Verify token (you should check against your configured token)
        from .models import WhatsAppAccount
        
        # Check if token matches any account
        if mode == 'subscribe' and WhatsAppAccount.objects.filter(webhook_verify_token=token).exists():
            logger.info("WhatsApp webhook verified successfully")
            return HttpResponse(challenge, content_type="text/plain")
        else:
            logger.warning(f"WhatsApp webhook verification failed. Token match: {WhatsAppAccount.objects.filter(webhook_verify_token=token).exists()}")
            return HttpResponse('Forbidden', status=403)
    
    elif request.method == 'POST':
        # Process incoming webhook
        try:
            data = json.loads(request.body)
            logger.info(f"Received WhatsApp webhook: {data}")
            
            process_whatsapp_webhook(data)
            
            return JsonResponse({'status': 'ok'})
        
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# QUICK REPLY MANAGEMENT
# ============================================================================

class QuickReplyListView(LoginRequiredMixin, ListView):
    model = QuickReply
    template_name = 'communications/quick_replies.html'
    context_object_name = 'quick_replies'

    def get_queryset(self):
        # Show user's own replies and global ones
        return QuickReply.objects.filter(
            models.Q(created_by=self.request.user) | models.Q(is_global=True)
        ).order_by('shortcut', 'title')

class QuickReplyCreateView(LoginRequiredMixin, CreateView):
    model = QuickReply
    form_class = QuickReplyForm
    template_name = 'communications/quick_reply_form.html'
    success_url = reverse_lazy('communications:quick_replies')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # Only supervisors/admins can create global replies
        if form.instance.is_global and not (self.request.user.is_superuser or self.request.user.groups.filter(name='Supervisor').exists()):
            form.instance.is_global = False
        return super().form_valid(form)

class QuickReplyUpdateView(LoginRequiredMixin, UpdateView):
    model = QuickReply
    form_class = QuickReplyForm
    template_name = 'communications/quick_reply_form.html'
    success_url = reverse_lazy('communications:quick_replies')

    def get_queryset(self):
        # Only allow editing own replies unless admin/supervisor
        if self.request.user.is_superuser or self.request.user.groups.filter(name='Supervisor').exists():
            return QuickReply.objects.all()
        return QuickReply.objects.filter(created_by=self.request.user)

# ============================================================================
# REPORTS
# ============================================================================

def render_pdf_view(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="conversation_report.pdf"'
    pisa_status = pisa.CreatePDF(
       html, dest=response)
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

class ConversationReportView(LoginRequiredMixin, View):
    def get(self, request):
        form = ConversationReportForm()
        return render(request, 'communications/report_modal.html', {'form': form})
    
    def post(self, request):
        form = ConversationReportForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data['client']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            
            conversations = Conversation.objects.filter(
                contact__client=client,
                created_at__date__range=[start_date, end_date]
            ).prefetch_related('messages').order_by('created_at')
            
            context = {
                'client': client,
                'start_date': start_date,
                'end_date': end_date,
                'conversations': conversations,
                'generated_at': timezone.now()
            }
            
            return render_pdf_view('communications/reports/conversation_pdf.html', context)
        
        return render(request, 'communications/report_modal.html', {'form': form})

class QuickReplyDeleteView(LoginRequiredMixin, DeleteView):
    model = QuickReply
    template_name = 'communications/quick_reply_confirm_delete.html'
    success_url = reverse_lazy('communications:quick_replies')

    def get_queryset(self):
        # Only allow deleting own replies unless admin/supervisor
        if self.request.user.is_superuser or self.request.user.groups.filter(name='Supervisor').exists():
            return QuickReply.objects.all()
        return QuickReply.objects.filter(created_by=self.request.user)


# ============================================================================
# WELCOME MENU MANAGEMENT
# ============================================================================

class WelcomeMenuListView(LoginRequiredMixin, ListView):
    model = WelcomeMenu
    template_name = 'communications/welcome_menus/list.html'
    context_object_name = 'menus'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
            from django.contrib import messages
            messages.error(request, 'No tenés permiso para acceder a esta sección.')
            return redirect('communications:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return WelcomeMenu.objects.prefetch_related('items__assigned_user').order_by('-is_active', 'name')


class WelcomeMenuCreateView(LoginRequiredMixin, View):
    template_name = 'communications/welcome_menus/form.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
            from django.contrib import messages
            messages.error(request, 'No tenés permiso para acceder a esta sección.')
            return redirect('communications:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from django.contrib.auth.models import User
        users = User.objects.filter(is_active=True).order_by('first_name', 'username')
        empty_data = {'name': '', 'trigger_keywords': '', 'greeting_text': '', 'footer_text': ''}
        return render(request, self.template_name, {'action': 'Crear', 'users': users, 'post_data': empty_data})

    def post(self, request):
        name = request.POST.get('name', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        greeting_text = request.POST.get('greeting_text', '').strip()
        footer_text = request.POST.get('footer_text', '').strip()
        keywords_raw = request.POST.get('trigger_keywords', '').strip()
        trigger_keywords = [k.strip().lower() for k in keywords_raw.split(',') if k.strip()]

        if not name or not greeting_text:
            return render(request, self.template_name, {
                'action': 'Crear',
                'error': 'El nombre y el texto de bienvenida son obligatorios.',
                'post_data': request.POST,
            })

        menu = WelcomeMenu.objects.create(
            name=name,
            is_active=is_active,
            greeting_text=greeting_text,
            footer_text=footer_text,
            trigger_keywords=trigger_keywords,
        )

        # Save items
        numbers = request.POST.getlist('item_number')
        labels = request.POST.getlist('item_label')
        users = request.POST.getlist('item_user')
        for i, num in enumerate(numbers):
            try:
                n = int(num)
                label = labels[i].strip() if i < len(labels) else ''
                uid = users[i] if i < len(users) else None
                if label:
                    WelcomeMenuItem.objects.create(
                        menu=menu,
                        number=n,
                        label=label,
                        assigned_user_id=uid if uid else None,
                    )
            except (ValueError, TypeError):
                continue

        from django.contrib import messages
        messages.success(request, f'Menú "{menu.name}" creado correctamente.')
        return redirect('communications:welcome_menus')


class WelcomeMenuUpdateView(LoginRequiredMixin, View):
    template_name = 'communications/welcome_menus/form.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
            from django.contrib import messages
            messages.error(request, 'No tenés permiso para acceder a esta sección.')
            return redirect('communications:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        menu = get_object_or_404(WelcomeMenu, pk=pk)
        items = menu.items.all().order_by('number')
        from django.contrib.auth.models import User
        users = User.objects.filter(is_active=True).order_by('first_name', 'username')
        post_data = {
            'name': menu.name,
            'is_active': 'on' if menu.is_active else '',
            'greeting_text': menu.greeting_text,
            'footer_text': menu.footer_text,
            'trigger_keywords': ', '.join(menu.trigger_keywords),
        }
        return render(request, self.template_name, {
            'action': 'Editar', 'menu': menu, 'items': items, 'users': users, 'post_data': post_data
        })

    def post(self, request, pk):
        menu = get_object_or_404(WelcomeMenu, pk=pk)
        menu.name = request.POST.get('name', '').strip()
        menu.is_active = request.POST.get('is_active') == 'on'
        menu.greeting_text = request.POST.get('greeting_text', '').strip()
        menu.footer_text = request.POST.get('footer_text', '').strip()
        keywords_raw = request.POST.get('trigger_keywords', '').strip()
        menu.trigger_keywords = [k.strip().lower() for k in keywords_raw.split(',') if k.strip()]
        menu.save()

        # Rebuild items
        menu.items.all().delete()
        numbers = request.POST.getlist('item_number')
        labels = request.POST.getlist('item_label')
        users = request.POST.getlist('item_user')
        for i, num in enumerate(numbers):
            try:
                n = int(num)
                label = labels[i].strip() if i < len(labels) else ''
                uid = users[i] if i < len(users) else None
                if label:
                    WelcomeMenuItem.objects.create(
                        menu=menu,
                        number=n,
                        label=label,
                        assigned_user_id=uid if uid else None,
                    )
            except (ValueError, TypeError):
                continue

        from django.contrib import messages
        messages.success(request, f'Menú "{menu.name}" actualizado correctamente.')
        return redirect('communications:welcome_menus')


class WelcomeMenuDeleteView(LoginRequiredMixin, DeleteView):
    model = WelcomeMenu
    template_name = 'communications/welcome_menus/confirm_delete.html'
    success_url = reverse_lazy('communications:welcome_menus')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists()):
            from django.contrib import messages
            messages.error(request, 'No tenés permiso para acceder a esta sección.')
            return redirect('communications:dashboard')
        return super().dispatch(request, *args, **kwargs)
from django.contrib.auth import get_user_model

from django.contrib.auth import get_user_model

User = get_user_model()
   
@login_required
def transfer_conversation_modal(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    users = User.objects.filter(is_active=True)

    return render(request, "communications/partials/transfer_modal.html", {
        "conversation": conversation,
        "users": users
    })
@login_required
@require_http_methods(["POST"])
def transfer_conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)

    # Permisos
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name='Supervisor').exists() or
        conversation.assigned_to == request.user
    ):
        return HttpResponse(
            "<div class='alert alert-danger'>Sin permiso</div>",
            status=403
        )

    new_user_id = request.POST.get('user_id')

    if not new_user_id:
        return render(request, "communications/partials/transfer_modal.html", {
            "conversation": conversation,
            "users": User.objects.filter(is_active=True),
            "error": "Debe seleccionar un usuario"
        })

    try:
        new_user = User.objects.get(pk=new_user_id, is_active=True)

    except User.DoesNotExist:
        return HttpResponse(
            "<div class='alert alert-danger'>Usuario no encontrado</div>",
            status=404
        )

    from .assignment_system import reassign_conversation
    reassign_conversation(conversation, new_user, request.user)
    conversation.status = 'closed'
    conversation.save()
    # 🔥 RESPUESTA HTMX (HTML, no JSON)
    return render(request, "communications/partials/transfer_success.html", {
        "message": f"Conversación derivada a {new_user.get_full_name() or new_user.username}"
    })

@login_required
def open_client_email(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'email'}
    )

    conversation = Conversation.objects.filter(
        contact=contact,
        channel='email',
        status__in=['normal', 'pending', 'open', 'assigned']
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(
            contact=contact,
            channel='email',
            status='normal',
            priority='normal',
            subject=f"Email con {client.name}"
        )

        assign_conversation_to_agent(
            conversation,
            agent=request.user,
            assigned_by=request.user
        )
    from django.urls import reverse
    url = reverse('communications:dashboard')

    return redirect(f'{url}?channel=email&conversation={conversation.pk}')

    
