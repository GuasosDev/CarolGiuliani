"""
Django views for communications web interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
import json
import logging
from .models import Conversation, Contact, Message, WhatsAppAccount, EmailAccount, QuickReply
from .forms import QuickReplyForm
from .whatsapp_handler import process_whatsapp_webhook
from .assignment_system import get_agent_conversations, assign_conversation_to_agent
from clients.models import Client
from core.views import GenericCreateView

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Main communication dashboard"""
    # Get user's conversations
    status_filter = request.GET.get('status')
    channel_filter = request.GET.get('channel')
    
    base_qs = get_agent_conversations(request.user)
    
    # Base filtering
    conversations = base_qs
    
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
            conversations = conversations.filter(messages__is_read=False, messages__direction='inbound').distinct()
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
        'clients': clients,
        **counts # Unpack counts into context
    }
    
    return render(request, 'communications/dashboard.html', context)


def _get_conversation_counts(user):
    """Helper to get conversation counts for the sidebar"""
    base_qs = get_agent_conversations(user)
    
    whatsapp_count = base_qs.filter(channel='whatsapp').count()
    email_count = base_qs.filter(channel='email').count()
    
    return {
        'normal_count': base_qs.filter(status='normal').count(),
        'pending_count': base_qs.filter(status='pending').count(),
        'closed_count': base_qs.filter(status='closed').count(),
        'unread_count': base_qs.filter(messages__is_read=False, messages__direction='inbound').distinct().count(),
        'whatsapp_count': whatsapp_count,
        'email_count': email_count,
        'total_channel_count': whatsapp_count + email_count,
    }


@login_required
def open_client_whatsapp(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'whatsapp'}
    )
    
    conversation = Conversation.objects.filter(
        contact=contact,
        channel='whatsapp',
        status__in=['normal', 'pending']
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(
            contact=contact,
            channel='whatsapp',
            status='normal',
            priority='normal'
        )
        assign_conversation_to_agent(conversation, agent=request.user, assigned_by=request.user)
    
    return redirect('communications:conversation_detail', pk=conversation.pk)


@login_required
def change_conversation_status(request, pk):
    """Change status of a conversation"""
    conversation = get_object_or_404(Conversation, pk=pk)
    
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists() or
            conversation.assigned_to == request.user):
        return HttpResponse('Unauthorized', status=401)
        
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['normal', 'pending', 'closed']:
            if new_status == 'closed':
                conversation.close()
            else:
                conversation.status = new_status
                conversation.save()
                
    return redirect('communications:conversation_detail', pk=conversation.pk)


class ContactCreateView(GenericCreateView):
    model = Contact
    fields = ['client', 'whatsapp_number', 'preferred_channel', 'notes']
    title = "Nuevo Contacto de Comunicación"
    success_url = reverse_lazy('communications:dashboard')


@login_required
def conversation_detail(request, pk):
    """Conversation detail view"""
    conversation = get_object_or_404(Conversation, pk=pk)
    
    # Check permission (agents can only see their own, supervisors see all)
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists() or
            conversation.assigned_to == request.user):
        return HttpResponse('Unauthorized', status=401)
    
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
        **counts # Unpack counts into context
    }
    
    return render(request, 'communications/conversation_detail.html', context)


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


@login_required
def supervisor_dashboard(request):
    """Supervisor dashboard with metrics and team overview"""
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()):
        return HttpResponse('Unauthorized', status=401)
    
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    
    # Get all agents
    agents = User.objects.filter(is_staff=True, is_active=True)
    
    # Get metrics
    total_conversations = Conversation.objects.count()
    open_conversations = Conversation.objects.filter(status__in=['open', 'assigned', 'pending']).count()
    closed_today = Conversation.objects.filter(
        status='closed',
        closed_at__date=timezone.now().date()
    ).count()
    
    # Agent workload
    agent_stats = []
    for agent in agents:
        active_count = Conversation.objects.filter(
            assigned_to=agent,
            status__in=['open', 'assigned', 'pending']
        ).count()
        
        agent_stats.append({
            'agent': agent,
            'active_conversations': active_count
        })
    
    context = {
        'total_conversations': total_conversations,
        'open_conversations': open_conversations,
        'closed_today': closed_today,
        'agent_stats': agent_stats,
    }
    
    return render(request, 'communications/supervisor_dashboard.html', context)


@login_required
def settings_view(request):
    """Settings page for accounts and configuration"""
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()):
        return HttpResponse('Unauthorized', status=401)
    
    from .models import WhatsAppAccount, EmailAccount
    
    whatsapp_accounts = WhatsAppAccount.objects.all()
    email_accounts = EmailAccount.objects.all()
    
    context = {
        'whatsapp_accounts': whatsapp_accounts,
        'email_accounts': email_accounts,
    }
    
    return render(request, 'communications/settings.html', context)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """WhatsApp Business API webhook endpoint"""
    
    if request.method == 'GET':
        # Webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Verify token (you should check against your configured token)
        from .models import WhatsAppAccount
        
        # Check if token matches any account
        if mode == 'subscribe' and WhatsAppAccount.objects.filter(webhook_verify_token=token).exists():
            logger.info("WhatsApp webhook verified")
            return HttpResponse(challenge)
        else:
            logger.warning("WhatsApp webhook verification failed")
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

class QuickReplyDeleteView(LoginRequiredMixin, DeleteView):
    model = QuickReply
    template_name = 'communications/quick_reply_confirm_delete.html'
    success_url = reverse_lazy('communications:quick_replies')

    def get_queryset(self):
        # Only allow deleting own replies unless admin/supervisor
        if self.request.user.is_superuser or self.request.user.groups.filter(name='Supervisor').exists():
            return QuickReply.objects.all()
        return QuickReply.objects.filter(created_by=self.request.user)
