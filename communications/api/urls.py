"""
API URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConversationViewSet, MessageViewSet, InternalNoteViewSet,
    QuickReplyViewSet, WhatsAppAccountViewSet, EmailAccountViewSet,
    EmailTemplateViewSet, EmailSignatureViewSet
)

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'notes', InternalNoteViewSet, basename='note')
router.register(r'quick-replies', QuickReplyViewSet, basename='quickreply')
router.register(r'whatsapp-accounts', WhatsAppAccountViewSet, basename='whatsappaccount')
router.register(r'email-accounts', EmailAccountViewSet, basename='emailaccount')
router.register(r'email-templates', EmailTemplateViewSet, basename='emailtemplate')
router.register(r'email-signatures', EmailSignatureViewSet, basename='emailsignature')

urlpatterns = [
    path('', include(router.urls)),
]
