"""
Main URL configuration for communications app
"""

from django.urls import path, include
from . import views
from .views import ContactCreateView, open_client_whatsapp

app_name = 'communications'

urlpatterns = [
    # API URLs
    path('api/', include('communications.api.urls')),
    
    # Webhook URLs
    path('webhook/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
    
    # Web interface URLs
    path('', views.dashboard, name='dashboard'),
    path('client/<int:client_id>/whatsapp/', open_client_whatsapp, name='open_client_whatsapp'),
    path('conversation/<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/<int:pk>/status/', views.change_conversation_status, name='change_conversation_status'),
    path('contact/<int:pk>/', views.contact_360_view, name='contact_360'),
    path('contacts/create/', ContactCreateView.as_view(), name='contact_create'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('settings/', views.settings_view, name='settings'),
]
