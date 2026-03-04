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
from .models import Conversation, Contact, Message,InternalNote
from .whatsapp_handler import process_whatsapp_webhook
from .assignment_system import get_agent_conversations
from django.utils import timezone
from communications.models import EmailQueue, EmailAccount
from communications.tasks import process_email_queue
from django.utils import timezone
logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Professional helpdesk-style dashboard"""

    # Inbox general (no asignadas)
    unassigned_qs = Conversation.objects.filter(
        assigned_to__isnull=True,
        status__in=['open', 'pending']
    ).order_by('-last_message_at')

    # Mis conversaciones
    my_qs = Conversation.objects.filter(
        assigned_to=request.user,
        status__in=['open', 'assigned', 'pending']
    ).order_by('-last_message_at')

    context = {
        # Listas (limitadas visualmente)
        'unassigned_conversations': unassigned_qs[:20],
        'my_conversations': my_qs[:50],

        # Contadores reales
        'unassigned_count': unassigned_qs.count(),
        'my_active_count': my_qs.filter(status='assigned').count(),
        'my_pending_count': my_qs.filter(status='pending').count(),
    }

    return render(request, 'communications/dashboard.html', context)



from django.utils import timezone
from communications.models import EmailQueue, EmailAccount
from communications.tasks import process_email_queue

@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)

    if not (
        request.user.is_superuser or 
        request.user.groups.filter(name='Supervisor').exists() or
        conversation.assigned_to == request.user or
        conversation.assigned_to is None
    ):
        return HttpResponse('Unauthorized', status=401)

    if request.method == "POST":
        action = request.POST.get("action")

        # =========================
        # ENVIAR MENSAJE
        # =========================
        if action == "send_message":
            content = request.POST.get("content")

            if content:
                message = Message.objects.create(
                    conversation=conversation,
                    message_type=conversation.channel,
                    direction='outbound',
                    sender=request.user,
                    content=content
                )

                # Actualizar preview
                conversation.last_message_at = timezone.now()
                conversation.last_message_preview = content[:100]
                conversation.save()

                # 🚀 SI ES EMAIL, LO ENVIAMOS
                if conversation.channel == "email":

                    client = conversation.contact.client

                    if client and client.email:
                        account = EmailAccount.objects.filter(is_active=True).first()

                        EmailQueue.objects.create(
                            email_account=account,
                            to_addresses=[client.email],
                            subject=conversation.subject or "Respuesta",
                            plain_body=content,
                            conversation=conversation,
                            scheduled_at=timezone.now(),
                            status="pending"
                        )

                        process_email_queue.delay()

        # =========================
        # AGREGAR NOTA INTERNA
        # =========================
        elif action == "add_note":
            content = request.POST.get("note_content")

            if content:
                InternalNote.objects.create(
                    conversation=conversation,
                    author=request.user,
                    content=content
                )

        return redirect("communications:conversation_detail", pk=conversation.pk)

    messages = conversation.messages.all()
    notes = conversation.internal_notes.all()

    context = {
        'conversation': conversation,
        'messages': messages,
        'notes': notes,
    }

    return render(request, 'communications/conversation_detail.html', context)
from django.shortcuts import get_object_or_404, redirect
from communications.models import Conversation, Contact
from clients.models import Client

@login_required
def start_email_conversation(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    # Obtener o crear Contact
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'email'}
    )

    # Buscar conversación abierta de email
    conversation = Conversation.objects.filter(
        contact=contact,
        channel='email',
        status__in=['open', 'assigned', 'pending']
    ).first()

    # Si no existe, crearla
    if not conversation:
        conversation = Conversation.objects.create(
            contact=contact,
            channel='email',
            status='open',
            priority='normal',
            subject=f"Conversación con {client.name}"
        )

    return redirect("communications:conversation_detail", pk=conversation.pk)


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

    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()):
        return HttpResponse('Unauthorized', status=401)

    today = timezone.now().date()

    # Conversaciones base
    conversations = Conversation.objects.all()

    # Métricas principales
    total_conversations = conversations.count()

    open_conversations = conversations.filter(
        status__in=['open', 'assigned', 'pending']
    ).count()

    closed_today = conversations.filter(
        status='closed',
        closed_at__date=today
    ).count()

    unassigned = conversations.filter(
        assigned_to__isnull=True,
        status__in=['open', 'pending']
    ).count()

    # SLA simple (más de 30 min sin respuesta)
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)

    sla_breached = conversations.filter(
        status__in=['open', 'assigned'],
        updated_at__lt=thirty_minutes_ago
    ).count()

    # Estadísticas por agente optimizadas
    agent_stats = (
        Conversation.objects
        .filter(status__in=['open', 'assigned', 'pending'])
        .values('assigned_to__id',
                'assigned_to__username',
                'assigned_to__first_name',
                'assigned_to__last_name')
        .annotate(active_conversations=Count('id'))
        .order_by('-active_conversations')
    )

    context = {
        'total_conversations': total_conversations,
        'open_conversations': open_conversations,
        'closed_today': closed_today,
        'unassigned': unassigned,
        'sla_breached': sla_breached,
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
    print("ENTRÓ AL WEBHOOK")
    print("METHOD:", request.method)
    print("BODY:", request.body)
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

from django.db import transaction

@login_required
def take_conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)

    # Solo agentes pueden tomar
    if not request.user.is_staff:
        return HttpResponse("Unauthorized", status=401)

    if request.method == "POST":
        with transaction.atomic():
            conversation = Conversation.objects.select_for_update().get(pk=pk)

            if conversation.assigned_to is None:
                conversation.assign_to(request.user)
                conversation.status = "assigned"
                conversation.save()

        return redirect("communications:conversation_detail", pk=pk)

    return HttpResponse(status=400)