from core.views import GenericListView, GenericCreateView, GenericUpdateView, GenericDeleteView
from .models import Client
from django.urls import reverse_lazy

class ClientListView(GenericListView):
    model = Client
    list_fields = ['name', 'email', 'phone']
    list_headers = ['Nombre', 'Email', 'Teléfono']
    title = "Listado de Contactos"
    create_url_name = 'client_create'
    update_url_name = 'client_update'
    delete_url_name = 'client_delete'

class ClientCreateView(GenericCreateView):
    model = Client
    fields = ['name', 'email', 'phone', 'address']
    title = "Crear Contacto"

class ClientUpdateView(GenericUpdateView):
    model = Client
    fields = ['name', 'email', 'phone', 'address']
    title = "Editar Contacto"

class ClientDeleteView(GenericDeleteView):
    model = Client
