"""
WebSocket URL routing for communications app
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/communications/$', consumers.CommunicationConsumer.as_asgi()),
]
