from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.models import User, Group, Permission
from .models import CompanySettings, UserProfile, WorkArea
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
    template_name = 'core/generic_form.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Mi Perfil"
        # Add profile fields manual handling if needed, or use a Form that includes Profile fields.
        # For simplicity, let's just edit User fields here. 
        # To edit UserProfile.phone, we need a custom form.
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Add phone field from profile
        if hasattr(self.request.user, 'userprofile'):
            form.fields['phone'] =  forms.CharField(initial=self.request.user.userprofile.phone, required=False)
        else:
             form.fields['phone'] =  forms.CharField(required=False)
        return form

    def form_valid(self, form):
        # We need to call parent form_valid to save the User object, 
        # which will trigger GenericFormMixin.form_valid
        # But we also need to save the phone.
        
        # Save profile phone manually
        phone = form.cleaned_data.get('phone')
        if phone:
            profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
            profile.phone = phone
            profile.save()
            
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
    list_fields = ['username', 'first_name', 'last_name', 'email', 'userprofile__get_role_display', 'userprofile__work_area__name']
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
        form.fields['role'] = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Rol")
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
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        
        role = form.cleaned_data.get('role')
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'supervisor':
            user.is_superuser = False
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
            
        user.save()
        
        # Save groups
        groups = form.cleaned_data.get('groups')
        if groups:
            user.groups.set(groups)
        
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
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
        form.fields['role'] = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, initial=user_profile.role, label="Rol")
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
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        role = form.cleaned_data.get('role')
        
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'supervisor':
            user.is_superuser = False
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
            
        user.save()
        
        # Update groups
        groups = form.cleaned_data.get('groups')
        user.groups.set(groups if groups else [])
        
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
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
