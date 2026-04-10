from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.models import User, Group, Permission
from .models import CompanySettings, UserProfile, WorkArea, UserRole
from django import forms
import json
from django.db.models import Q
# Import models inside methods to avoid circular imports if necessary, 
# but usually views.py is fine.
# We'll import inside the view just in case.

class GenericFormMixin:
    template_name = 'core/generic_form.html'
    title = "Form"
    success_url = "/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.title
        context['action_url'] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('HX-Request'):
            # Return 204 to signal success to HTMX (handled by js)
            response = HttpResponse(status=204)
            # If it's a secondary modal creation, we might want a different trigger or just reload
            # For now, let's keep reloadPage which is handled in main.js
            response['HX-Trigger'] = 'reloadPage' 
            return response
        return super().form_valid(form)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

class GenericListView(LoginRequiredMixin, ListView):
    template_name = 'core/generic_list.html'
    list_fields = [] # List of field names to display
    list_headers = [] # List of header names (must match list_fields length)
    title = "List"
    create_url_name = None
    update_url_name = None
    delete_url_name = None
    action_template_name = None # Optional template for custom actions

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
             return ['core/partials/generic_list_partial.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fields'] = self.list_fields
        context['headers'] = self.list_headers
        context['title'] = self.title
        context['create_url'] = reverse_lazy(self.create_url_name) if self.create_url_name else None
        context['update_url_name'] = self.update_url_name
        context['delete_url_name'] = self.delete_url_name
        context['detail_url_name'] = getattr(self, 'detail_url_name', None)
        context['action_template_name'] = self.action_template_name
        return context

class CompanySettingsUpdateView(LoginRequiredMixin, UserPassesTestMixin, GenericFormMixin, UpdateView):
    model = CompanySettings
    fields = ['name', 'address', 'phone', 'email']
    template_name = 'core/generic_form.html'

    def get_object(self, queryset=None):
        return CompanySettings.load()

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Configuración de Empresa"
        return context

class UserProfileUpdateView(LoginRequiredMixin, GenericFormMixin, UpdateView):
    model = User
    fields = ['first_name', 'last_name', 'email']
    template_name = 'core/profile_personalization.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Mi Perfil"
        context['profile'] = self.request.user.userprofile
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        profile = self.request.user.userprofile
        form.fields['phone'] = forms.CharField(initial=profile.phone, required=False, label="Teléfono")
        form.fields['avatar'] = forms.ImageField(required=False, label="Imagen de Perfil")
        form.fields['dark_mode'] = forms.BooleanField(initial=profile.dark_mode, required=False, label="Modo Oscuro")
        form.fields['font_size'] = forms.IntegerField(initial=profile.font_size, min_value=12, max_value=24, label="Tamaño de Fuente")
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        user.first_name = form.cleaned_data.get('first_name', user.first_name)
        user.last_name = form.cleaned_data.get('last_name', user.last_name)
        user.email = form.cleaned_data.get('email', user.email)
        user.save()
        
        profile = user.userprofile
        profile.phone = form.cleaned_data.get('phone')
        
        if 'avatar' in self.request.FILES:
            profile.avatar = self.request.FILES['avatar']
        
        profile.dark_mode = form.cleaned_data.get('dark_mode', profile.dark_mode)
        profile.font_size = form.cleaned_data.get('font_size', profile.font_size)
        profile.save()
        
        from django.contrib import messages
        messages.success(self.request, "Perfil actualizado correctamente.")
        
        return super().form_valid(form)

class GlobalSearchView(LoginRequiredMixin, TemplateView):
    template_name = 'core/search_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.urls import reverse
        from django.utils.html import escape
        from django.utils.safestring import mark_safe
        import re

        query = (self.request.GET.get('q') or '').strip()

        def highlight(text):
            if not text:
                return ""
            safe_text = escape(str(text))
            if not query:
                return safe_text
            safe_query = escape(query)
            if not safe_query:
                return safe_text
            pattern = re.compile(re.escape(safe_query), re.IGNORECASE)
            return mark_safe(pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", safe_text))

        def snippet(text, limit=200):
            if not text:
                return ""
            raw = str(text).replace("\r", " ").replace("\n", " ").strip()
            if len(raw) > limit:
                raw = raw[:limit].rstrip() + "…"
            return highlight(raw)

        results = []

        if len(query) >= 2:
            from clients.models import Client, ClientTag
            from communications.models import Conversation, Message, InternalNote, QuickReply, Contact

            clients_qs = Client.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(business_name__icontains=query) |
                Q(cuit__icontains=query) |
                Q(address__icontains=query) |
                Q(fiscal_address__icontains=query) |
                Q(job_title__icontains=query) |
                Q(additional_info__icontains=query) |
                Q(internal_notes__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct().prefetch_related('tags')[:12]

            client_items = []
            for c in clients_qs:
                parts = []
                if c.phone:
                    parts.append(str(c.phone))
                if c.email:
                    parts.append(str(c.email))
                if c.business_name:
                    parts.append(str(c.business_name))
                client_items.append({
                    "title": highlight(c.name),
                    "subtitle": highlight(" • ".join(parts)),
                    "snippet": snippet(c.internal_notes or c.additional_info or c.address or ""),
                    "primary": {
                        "label": "Ver / Editar",
                        "hx_get": reverse('client_update', args=[c.pk]),
                    },
                    "secondary": {
                        "label": "Abrir chat",
                        "href": reverse('communications:open_client_whatsapp', args=[c.pk]),
                    },
                    "meta": "Contacto",
                })

            if client_items:
                results.append({
                    "title": "Contactos",
                    "icon": "fa-user",
                    "items": client_items,
                })

            contacts_qs = Contact.objects.filter(
                Q(whatsapp_number__icontains=query) |
                Q(notes__icontains=query) |
                Q(client__name__icontains=query) |
                Q(client__email__icontains=query) |
                Q(client__phone__icontains=query)
            ).select_related('client')[:10]

            contact_items = []
            for ct in contacts_qs:
                display = ct.client.name if ct.client else (ct.whatsapp_number or "Contacto")
                meta = []
                if ct.whatsapp_number:
                    meta.append(ct.whatsapp_number)
                if ct.client and getattr(ct.client, 'email', None):
                    meta.append(ct.client.email)
                contact_items.append({
                    "title": highlight(display),
                    "subtitle": highlight(" • ".join([m for m in meta if m])),
                    "snippet": snippet(ct.notes or ""),
                    "primary": {
                        "label": "Ver 360°",
                        "href": reverse('communications:contact_360', args=[ct.pk]),
                    },
                    "meta": "Communications",
                })

            if contact_items:
                results.append({
                    "title": "Contactos (Communications)",
                    "icon": "fa-address-card",
                    "items": contact_items,
                })

            conversations_qs = Conversation.objects.filter(
                Q(subject__icontains=query) |
                Q(contact__client__name__icontains=query) |
                Q(contact__client__email__icontains=query) |
                Q(contact__client__phone__icontains=query) |
                Q(contact__whatsapp_number__icontains=query) |
                Q(last_message_preview__icontains=query)
            ).select_related('contact__client')[:15]

            conversation_items = []
            for conv in conversations_qs:
                display_name = conv.get_display_name()
                conv_url = reverse('communications:dashboard')
                params = f"?conversation={conv.pk}&channel={conv.channel}"
                if conv.status:
                    params += f"&status={conv.status}"
                conversation_items.append({
                    "title": highlight(display_name),
                    "subtitle": highlight(f"{conv.get_channel_display()} • {conv.get_status_display()}"),
                    "snippet": snippet(conv.subject or conv.last_message_preview or ""),
                    "primary": {
                        "label": "Abrir conversación",
                        "href": f"{conv_url}{params}",
                    },
                    "meta": "Conversación",
                })

            if conversation_items:
                results.append({
                    "title": "Conversaciones",
                    "icon": "fa-comments",
                    "items": conversation_items,
                })

            messages_qs = Message.objects.filter(
                Q(content__icontains=query) |
                Q(sender_name__icontains=query) |
                Q(conversation__contact__client__name__icontains=query)
            ).select_related('conversation', 'conversation__contact__client').order_by('-created_at')[:25]

            message_items = []
            for msg in messages_qs:
                conv = msg.conversation
                display_name = conv.get_display_name()
                conv_url = reverse('communications:dashboard')
                params = f"?conversation={conv.pk}&channel={conv.channel}"
                message_items.append({
                    "title": highlight(display_name),
                    "subtitle": highlight(f"{conv.get_channel_display()} • {msg.created_at:%d/%m %H:%M}"),
                    "snippet": snippet(msg.content),
                    "primary": {
                        "label": "Ver en chat",
                        "href": f"{conv_url}{params}",
                    },
                    "meta": "Mensaje",
                })

            if message_items:
                results.append({
                    "title": "Mensajes",
                    "icon": "fa-message",
                    "items": message_items,
                })

            notes_qs = InternalNote.objects.filter(
                Q(content__icontains=query) |
                Q(author__username__icontains=query) |
                Q(conversation__contact__client__name__icontains=query)
            ).select_related('conversation', 'conversation__contact__client', 'author').order_by('-created_at')[:20]

            note_items = []
            for n in notes_qs:
                conv = n.conversation
                display_name = conv.get_display_name()
                conv_url = reverse('communications:dashboard')
                params = f"?conversation={conv.pk}&channel={conv.channel}"
                note_items.append({
                    "title": highlight(display_name),
                    "subtitle": highlight(f"Nota • {n.author.username} • {n.created_at:%d/%m %H:%M}"),
                    "snippet": snippet(n.content),
                    "primary": {
                        "label": "Abrir conversación",
                        "href": f"{conv_url}{params}",
                    },
                    "meta": "Nota interna",
                })

            if note_items:
                results.append({
                    "title": "Notas internas",
                    "icon": "fa-note-sticky",
                    "items": note_items,
                })

            quick_qs = QuickReply.objects.filter(
                Q(title__icontains=query) |
                Q(shortcut__icontains=query) |
                Q(content__icontains=query) |
                Q(category__icontains=query)
            ).select_related('created_by').order_by('-usage_count', 'title')[:20]

            quick_items = []
            for qr in quick_qs:
                quick_items.append({
                    "title": highlight(qr.title),
                    "subtitle": highlight(" • ".join([p for p in [qr.shortcut, qr.category, qr.get_channel_display()] if p])),
                    "snippet": snippet(qr.content),
                    "primary": {
                        "label": "Ver",
                        "href": reverse('communications:quick_replies'),
                    },
                    "meta": "Respuesta rápida",
                })

            if quick_items:
                results.append({
                    "title": "Respuestas rápidas",
                    "icon": "fa-bolt",
                    "items": quick_items,
                })

            tags_qs = ClientTag.objects.filter(name__icontains=query).order_by('name')[:20]
            tag_items = []
            for t in tags_qs:
                tag_items.append({
                    "title": highlight(t.name),
                    "subtitle": highlight("Etiqueta"),
                    "snippet": "",
                    "primary": {
                        "label": "Ver etiquetas",
                        "href": reverse('client_tag_full_list'),
                    },
                    "meta": "Clients",
                })

            if tag_items:
                results.append({
                    "title": "Etiquetas",
                    "icon": "fa-tags",
                    "items": tag_items,
                })

            users_qs = User.objects.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query)
            ).distinct().order_by('username')[:20]

            user_items = []
            for u in users_qs:
                name = (u.get_full_name() or u.username).strip()
                sub = " • ".join([p for p in [u.username, u.email] if p])
                user_items.append({
                    "title": highlight(name),
                    "subtitle": highlight(sub),
                    "snippet": "",
                    "primary": {
                        "label": "Ver usuario",
                        "href": reverse('user_management_update', args=[u.pk]),
                    },
                    "meta": "Usuarios",
                })

            if user_items:
                results.append({
                    "title": "Usuarios",
                    "icon": "fa-users",
                    "items": user_items,
                })

            roles_qs = UserRole.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            ).order_by('name')[:20]
            role_items = []
            for r in roles_qs:
                role_items.append({
                    "title": highlight(r.name),
                    "subtitle": highlight("Rol"),
                    "snippet": snippet(r.description or "", limit=160),
                    "primary": {
                        "label": "Ver roles",
                        "href": reverse('user_role_list'),
                    },
                    "meta": "Core",
                })

            if role_items:
                results.append({
                    "title": "Roles",
                    "icon": "fa-user-tag",
                    "items": role_items,
                })

            work_areas_qs = WorkArea.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            ).order_by('name')[:20]
            work_items = []
            for wa in work_areas_qs:
                work_items.append({
                    "title": highlight(wa.name),
                    "subtitle": highlight("Área laboral"),
                    "snippet": snippet(wa.description or "", limit=160),
                    "primary": {
                        "label": "Ver áreas",
                        "href": reverse('work_area_list'),
                    },
                    "meta": "Core",
                })

            if work_items:
                results.append({
                    "title": "Áreas laborales",
                    "icon": "fa-briefcase",
                    "items": work_items,
                })

            groups_qs = Group.objects.filter(name__icontains=query).order_by('name')[:20]
            group_items = []
            for g in groups_qs:
                group_items.append({
                    "title": highlight(g.name),
                    "subtitle": highlight("Grupo / privilegio"),
                    "snippet": "",
                    "primary": {
                        "label": "Ver privilegios",
                        "href": reverse('privilege_list'),
                    },
                    "meta": "Core",
                })

            if group_items:
                results.append({
                    "title": "Privilegios",
                    "icon": "fa-shield-halved",
                    "items": group_items,
                })

        context['query'] = query
        context['results'] = results
        context['total_results'] = sum(len(section.get('items', [])) for section in results)
        context['has_query'] = len(query) >= 2
        return context

class GenericCreateView(LoginRequiredMixin, GenericFormMixin, CreateView):
    pass

class GenericUpdateView(LoginRequiredMixin, GenericFormMixin, UpdateView):
    pass

class GenericDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'core/delete_confirm.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return render(request, self.template_name, {'object': self.object})
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'reloadPage' # Or refreshList
        return response

class PrivacyPolicyView(TemplateView):
    template_name = 'core/legal/privacy_policy.html'

class TermsOfServiceView(TemplateView):
    template_name = 'core/legal/terms_of_service.html'

class DataDeletionView(TemplateView):
    template_name = 'core/legal/data_deletion.html'

class UserRoleListView(UserPassesTestMixin, GenericListView):
    model = UserRole
    list_fields = ['name', 'is_active', 'is_staff', 'is_superuser']
    list_headers = ['Nombre del Rol', 'Activo', 'Staff', 'Superuser']
    title = "Roles de Usuario"
    create_url_name = 'user_role_create'
    update_url_name = 'user_role_update'
    delete_url_name = 'user_role_delete'

    def test_func(self):
        return self.request.user.is_superuser

class UserRoleCreateView(UserPassesTestMixin, GenericCreateView):
    model = UserRole
    fields = ['name', 'description', 'is_active', 'is_staff', 'is_superuser', 'groups']
    title = "Nuevo Rol"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class UserRoleUpdateView(UserPassesTestMixin, GenericUpdateView):
    model = UserRole
    fields = ['name', 'description', 'is_active', 'is_staff', 'is_superuser', 'groups']
    title = "Editar Rol"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class UserRoleDeleteView(UserPassesTestMixin, GenericDeleteView):
    model = UserRole
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class GroupListView(UserPassesTestMixin, GenericListView):
    model = Group
    list_fields = ['name']
    list_headers = ['Nombre del Grupo']
    title = "Grupos de Usuarios (Privilegios)"
    create_url_name = 'privilege_create'
    update_url_name = 'privilege_update'
    delete_url_name = 'privilege_delete'

    def test_func(self):
        return self.request.user.is_superuser

class GroupCreateView(UserPassesTestMixin, GenericCreateView):
    model = Group
    fields = ['name', 'permissions']
    title = "Nuevo Grupo de Privilegios"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class GroupUpdateView(UserPassesTestMixin, GenericUpdateView):
    model = Group
    fields = ['name', 'permissions']
    title = "Editar Grupo de Privilegios"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class GroupDeleteView(UserPassesTestMixin, GenericDeleteView):
    model = Group
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class WorkAreaListView(UserPassesTestMixin, GenericListView):
    model = WorkArea
    list_fields = ['name', 'description']
    list_headers = ['Nombre', 'Descripción']
    title = "Áreas Laborales"
    create_url_name = 'work_area_create'
    update_url_name = 'work_area_update'
    delete_url_name = 'work_area_delete'

    def test_func(self):
        return self.request.user.is_superuser

class WorkAreaCreateView(UserPassesTestMixin, GenericCreateView):
    model = WorkArea
    fields = ['name', 'description']
    title = "Nueva Área Laboral"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class WorkAreaUpdateView(UserPassesTestMixin, GenericUpdateView):
    model = WorkArea
    fields = ['name', 'description']
    title = "Editar Área Laboral"
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class WorkAreaDeleteView(UserPassesTestMixin, GenericDeleteView):
    model = WorkArea
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

class UserManagementListView(UserPassesTestMixin, GenericListView):
    model = User
    list_fields = ['username', 'first_name', 'last_name', 'email', 'userprofile__user_role__name', 'userprofile__work_area__name']
    list_headers = ['Usuario', 'Nombre', 'Apellido', 'Email', 'Rol', 'Área Laboral']
    title = "Gestión de Usuarios"
    create_url_name = 'user_management_create'
    update_url_name = 'user_management_update'
    delete_url_name = 'user_management_delete'

    def test_func(self):
        return self.request.user.is_superuser

class UserManagementCreateView(UserPassesTestMixin, GenericCreateView):
    model = User
    fields = ['username', 'password', 'first_name', 'last_name', 'email']
    title = "Nuevo Usuario"
    template_name = 'core/user_management_form.html'
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['password'].widget = forms.PasswordInput()
        form.fields['user_role'] = forms.ModelChoiceField(
            queryset=UserRole.objects.all(),
            required=False,
            label="Rol"
        )
        form.fields['groups'] = forms.ModelMultipleChoiceField(
            queryset=Group.objects.all(),
            required=False,
            label="Privilegios (Grupos)",
            widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
        )
        form.fields['work_area'] = forms.ModelChoiceField(
            queryset=WorkArea.objects.all(),
            required=False,
            label="Área Laboral"
        )
        from communications.models import EmailAccount
        form.fields['email_account'] = forms.ModelChoiceField(
            queryset=EmailAccount.objects.all(),
            required=False,
            label="Cuenta de Email Asignada"
        )
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        
        user_role = form.cleaned_data.get('user_role')
        if user_role:
            user.is_active = user_role.is_active
            user.is_staff = user_role.is_staff
            user.is_superuser = user_role.is_superuser
        else:
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            
        user.save()
        
        # Sync groups from role AND add manually selected groups
        final_groups = set()
        if user_role:
            for g in user_role.groups.all():
                final_groups.add(g)
        
        selected_groups = form.cleaned_data.get('groups')
        if selected_groups:
            for g in selected_groups:
                final_groups.add(g)
        
        user.groups.set(list(final_groups))
        
        # Assign email account
        email_account = form.cleaned_data.get('email_account')
        if email_account:
            email_account.user = user
            email_account.save()
        
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.user_role = user_role
        profile.work_area = form.cleaned_data.get('work_area')
        profile.save()
        
        if self.request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'reloadPage'
            return response
        return super().form_valid(form)

class UserManagementUpdateView(UserPassesTestMixin, GenericUpdateView):
    model = User
    fields = ['first_name', 'last_name', 'email', 'is_active']
    title = "Editar Usuario"
    template_name = 'core/user_management_form.html'
    success_url = reverse_lazy('communications:settings')

    def test_func(self):
        return self.request.user.is_superuser

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user_profile, _ = UserProfile.objects.get_or_create(user=self.get_object())
        form.fields['user_role'] = forms.ModelChoiceField(
            queryset=UserRole.objects.all(),
            initial=user_profile.user_role,
            required=False,
            label="Rol"
        )
        form.fields['groups'] = forms.ModelMultipleChoiceField(
            queryset=Group.objects.all(),
            initial=self.get_object().groups.all(),
            required=False,
            label="Privilegios (Grupos)",
            widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
        )
        form.fields['work_area'] = forms.ModelChoiceField(
            queryset=WorkArea.objects.all(),
            initial=user_profile.work_area,
            required=False,
            label="Área Laboral"
        )
        from communications.models import EmailAccount
        assigned_email = EmailAccount.objects.filter(user=self.get_object()).first()
        form.fields['email_account'] = forms.ModelChoiceField(
            queryset=EmailAccount.objects.all(),
            initial=assigned_email,
            required=False,
            label="Cuenta de Email Asignada"
        )
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        user_role = form.cleaned_data.get('user_role')
        
        if user_role:
            user.is_active = user_role.is_active
            user.is_staff = user_role.is_staff
            user.is_superuser = user_role.is_superuser
        else:
            # If no role, keep current status or set defaults
            user.is_active = form.cleaned_data.get('is_active', user.is_active)
            
        user.save()
        
        # Sync groups from role AND add manually selected groups
        final_groups = set()
        if user_role:
            for g in user_role.groups.all():
                final_groups.add(g)
        
        selected_groups = form.cleaned_data.get('groups')
        if selected_groups:
            for g in selected_groups:
                final_groups.add(g)
        
        user.groups.set(list(final_groups))
        
        # Update assigned email account
        from communications.models import EmailAccount
        # First, clear existing assignment for this user
        EmailAccount.objects.filter(user=user).update(user=None)
        # Then, assign the new one
        email_account = form.cleaned_data.get('email_account')
        if email_account:
            email_account.user = user
            email_account.save()
        
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.user_role = user_role
        profile.work_area = form.cleaned_data.get('work_area')
        profile.save()
        
        if self.request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'reloadPage'
            return response
        return super().form_valid(form)

class UserManagementDeleteView(UserPassesTestMixin, GenericDeleteView):
    model = User
    success_url = reverse_lazy('user_management_list')

    def test_func(self):
        return self.request.user.is_superuser
