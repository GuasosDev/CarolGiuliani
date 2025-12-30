from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.models import User
from .models import CompanySettings, UserProfile
from django import forms
import json

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
        # Return 204 to signal success to HTMX (handled by js)
        # Or return a script to close modal and refresh
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'reloadPage' 
        return response

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
        # Let's save phone before calling super() if possible, or after?
        # GenericFormMixin returns response, so we must do it before returning.
        
        # Save User first (without committing? No, UpdateView saves it)
        # Let's rely on form.save() in GenericFormMixin
        
        response = super().form_valid(form)
        
        # Now save profile
        phone = form.cleaned_data.get('phone')
        # Ensure profile exists
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        profile.phone = phone
        profile.save()
        
        return response

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
