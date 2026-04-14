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
from .models import Conversation, Contact, Message, WhatsAppAccount, EmailAccount, QuickReply, WelcomeMenu, WelcomeMenuItem,EmailMessage
from .forms import QuickReplyForm, ConversationReportForm
from .whatsapp_handler import process_whatsapp_webhook
from .assignment_system import get_agent_conversations, assign_conversation_to_agent
from clients.models import Client
from core.views import GenericCreateView
from django.db.models import Prefetch
logger = logging.getLogger(__name__)

# communications/views.py

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
    
    base_qs = get_agent_conversations(request.user).select_related(
    "contact__client"
).prefetch_related("messages")
    
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
def open_client_whatsapp(request, client_id, channel):
    client = get_object_or_404(Client, pk=client_id)
    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'channel'}
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
    return redirect(f'{url}?channel=whatsapp&conversation={conversation.pk}')


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

    if not (request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()):
        return HttpResponse('Unauthorized', status=401)
    
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    
    # Get all agents
    agents = User.objects.filter(is_staff=True, is_active=True)
    
    # Get metrics
    total_conversations = Conversation.objects.count()
    open_conversations = Conversation.objects.filter(status__in=['normal', 'pending']).count()
    closed_today = Conversation.objects.filter(
        status='closed',
        closed_at__date=timezone.now().date()
    ).count()
    
    # Agent workload
    agent_stats = []
    for agent in agents:
        active_count = Conversation.objects.filter(
            assigned_to=agent,
            status__in=['normal', 'pending']
        ).count()
        
        agent_stats.append({
            'agent': agent,
            'active_conversations': active_count
        })
    
    context = {
        'total_conversations': total_conversations,
        'open_conversations': open_conversations,
        'closed_today': closed_today,
        
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

    