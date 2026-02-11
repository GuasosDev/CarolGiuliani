"""
Django views for communications web interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
from .models import Conversation, Contact, Message
from .whatsapp_handler import process_whatsapp_webhook
from .assignment_system import get_agent_conversations

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Main communication dashboard"""
    # Get user's conversations
    conversations = get_agent_conversations(request.user).filter(
        status__in=['open', 'assigned', 'pending']
    )[:50]
    
    context = {
        'conversations': conversations,
        'active_count': conversations.filter(status='assigned').count(),
        'pending_count': conversations.filter(status='pending').count(),
    }
    
    return render(request, 'communications/dashboard.html', context)


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
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'notes': notes,
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
