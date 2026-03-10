from core.views import GenericListView, GenericCreateView, GenericUpdateView, GenericDeleteView
from .models import Client, ClientTag
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django import forms

class ClientListView(GenericListView):
    model = Client
    list_fields = ['name', 'business_name', 'email', 'phone', 'tags_display']
    list_headers = ['Nombre', 'Razón Social', 'Email', 'Teléfono', 'Etiquetas']
    title = "Listado de Contactos"
    create_url_name = 'client_create'
    update_url_name = 'client_update'
    delete_url_name = 'client_delete'
    action_template_name = 'clients/client_list_actions.html'

class ClientCreateView(GenericCreateView):
    model = Client
    fields = ['name', 'business_name', 'cuit', 'email', 'phone', 'job_title', 'address', 'fiscal_address', 'additional_info', 'tags']
    title = "Crear Contacto"
    template_name = 'clients/client_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tags'].widget = forms.CheckboxSelectMultiple()
        return form

class ClientUpdateView(GenericUpdateView):
    model = Client
    fields = ['name', 'business_name', 'cuit', 'email', 'phone', 'job_title', 'address', 'fiscal_address', 'additional_info', 'tags']
    title = "Editar Contacto"
    template_name = 'clients/client_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tags'].widget = forms.CheckboxSelectMultiple()
        return form

class ClientDeleteView(GenericDeleteView):
    model = Client

# ============================================================================
# TAG MANAGEMENT
# ============================================================================

class ClientTagListView(LoginRequiredMixin, ListView):
    model = ClientTag
    template_name = 'clients/tag_manager.html'
    context_object_name = 'tags'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'client_id' in self.kwargs:
            context['client'] = get_object_or_404(Client, pk=self.kwargs['client_id'])
        return context

class ClientTagCreateView(LoginRequiredMixin, CreateView):
    model = ClientTag
    fields = ['name', 'color']
    template_name = 'clients/tag_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'client_id' in self.kwargs:
            context['client_id'] = self.kwargs['client_id']
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Trigger': 'tagsChanged'})
        return super().form_valid(form)
        
    def get_success_url(self):
        return reverse_lazy('client_tag_list')

class ClientTagUpdateView(LoginRequiredMixin, UpdateView):
    model = ClientTag
    fields = ['name', 'color']
    template_name = 'clients/tag_form.html'
    
    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('HX-Request'):
             return HttpResponse(status=204, headers={'HX-Trigger': 'tagsChanged'})
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('client_tag_list')

class ClientTagDeleteView(LoginRequiredMixin, DeleteView):
    model = ClientTag
    template_name = 'clients/tag_confirm_delete.html'
    
    def form_valid(self, form):
        self.object.delete()
        if self.request.headers.get('HX-Request'):
             return HttpResponse(status=204, headers={'HX-Trigger': 'tagsChanged'})
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('client_tag_list')

class ClientManageTagsView(LoginRequiredMixin, View):
    """View to assign/remove tags for a specific client via HTMX"""
    
    def post(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        tag_id = request.POST.get('tag_id')
        action = request.POST.get('action') # 'add' or 'remove'
        
        if tag_id and action:
            tag = get_object_or_404(ClientTag, pk=tag_id)
            if action == 'add':
                client.tags.add(tag)
            elif action == 'remove':
                client.tags.remove(tag)
                
        # Return 204 to signal success and trigger updates
        return HttpResponse(status=204, headers={'HX-Trigger': 'tagsChanged, clientTagsChanged'})
