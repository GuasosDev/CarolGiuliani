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
        query = self.request.GET.get('q', '')
        
        # Import models here to avoid circular dependencies
        from clients.models import Client
        from communications.models import Message
        
        if query:
            # Search Clients (distinct to avoid duplicates if multiple fields match)
            clients = Client.objects.filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(business_name__icontains=query) |
                Q(cuit__icontains=query)
            ).distinct()[:10]
            
            # Search Messages
            messages = Message.objects.filter(
                content__icontains=query
            ).select_related('conversation', 'conversation__contact__client').order_by('-created_at')[:20]
            
            context['clients'] = clients
            context['messages'] = messages
            context['query'] = query
            
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
