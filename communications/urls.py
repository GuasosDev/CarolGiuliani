"""
Main URL configuration for communications app
"""

from django.urls import path, include
from . import views

app_name = 'communications'

urlpatterns = [
    # API URLs
    path('api/', include('communications.api.urls')),
    
    # Webhook URLs
    path('webhook/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
    
    # Web interface URLs
    path('', views.dashboard, name='dashboard'),
    path('conversation/<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('contact/<int:pk>/', views.contact_360_view, name='contact_360'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path(
    "start-email/<int:client_id>/",
    views.start_email_conversation,
    name="start_email_conversation"
),
    
]
