"""
Main URL configuration for communications app
"""

from django.urls import path, include
from . import views
from .views import ContactCreateView, open_client_whatsapp, WelcomeMenuListView, WelcomeMenuCreateView, WelcomeMenuUpdateView, WelcomeMenuDeleteView, transfer_conversation, transfer_conversation_modal,open_client_email

app_name = 'communications'

urlpatterns = [
    # API URLs
    path('api/', include('communications.api.urls')),
    
    # Webhook URLs
    path('webhook/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
    
    # Web interface URLs
    path('', views.dashboard, name='dashboard'),
    path('client/<int:client_id>/whatsapp/<str:channel>/', open_client_whatsapp, name='open_client_whatsapp'),
    path('client/<int:client_id>/whatsapp/', open_client_whatsapp, {'channel': 'whatsapp'}, name='open_client_whatsapp_legacy'),
    path('conversation/<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/<int:pk>/status/', views.change_conversation_status, name='change_conversation_status'),
    path('conversation/<int:conversation_id>/add-note/', views.add_conversation_note, name='add_conversation_note'),
    path('conversation/<int:conversation_id>/details-modal/', views.contact_details_modal, name='contact_details_modal'),
    path('conversation/<int:conversation_id>/quick-create-client/', views.quick_create_client_modal, name='quick_create_client_modal'),
    path('conversation/<int:conversation_id>/forward-messages-modal/', views.forward_messages_modal, name='forward_messages_modal'),
    path('conversation/<int:conversation_id>/forward-messages-send/', views.forward_messages_send, name='forward_messages_send'),
    path('internal-chat/', views.internal_chat, name='internal_chat'),
    path('internal-chat/messages/', views.internal_chat_messages_partial, name='internal_chat_messages'),
    path('internal-chat/send/', views.internal_chat_send, name='internal_chat_send'),
    path('contact/<int:pk>/', views.contact_360_view, name='contact_360'),
    path('contacts/create/', ContactCreateView.as_view(), name='contact_create'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('agent/', views.agent_dashboard, name='agent_dashboard'),
    path('panel/', views.role_dashboard, name='role_dashboard'),
    path('settings/', views.settings_view, name='settings'),
    
    # Quick Replies
    path('quick-replies/', views.QuickReplyListView.as_view(), name='quick_replies'),
    path('quick-replies/create/', views.QuickReplyCreateView.as_view(), name='quick_reply_create'),
    path('quick-replies/<int:pk>/update/', views.QuickReplyUpdateView.as_view(), name='quick_reply_update'),
    path('quick-replies/<int:pk>/delete/', views.QuickReplyDeleteView.as_view(), name='quick_reply_delete'),

    # Reports
    path('reports/conversation/', views.ConversationReportView.as_view(), name='conversation_report'),

    # Welcome Menus
    path('welcome-menus/', WelcomeMenuListView.as_view(), name='welcome_menus'),
    path('welcome-menus/create/', WelcomeMenuCreateView.as_view(), name='welcome_menu_create'),
    path('welcome-menus/<int:pk>/edit/', WelcomeMenuUpdateView.as_view(), name='welcome_menu_edit'),
    path('welcome-menus/<int:pk>/delete/', WelcomeMenuDeleteView.as_view(), name='welcome_menu_delete'),

    # Conversation Transfer
    path('conversation/<int:pk>/transfer/', transfer_conversation, name='transfer_conversation'),
    path(
        'conversation/<int:pk>/transfer/modal/',
        transfer_conversation_modal,
        name='transfer_conversation_modal'
    ),

    path('client/<int:client_id>/email/', open_client_email, name='open_client_email'),
    path('contacts/import/', views.import_contacts_csv, name='import_contacts_csv'),
]
