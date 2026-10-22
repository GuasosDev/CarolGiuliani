import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gd_soft_gty.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.messages import warning
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings
from django.utils.html import format_html

from communications.views import dashboard, open_client_whatsapp
from clients.models import Client
from communications.models import Contact, Conversation

User = get_user_model()


def attach_messages(request):
    request.session = {}
    messages = FallbackStorage(request)
    request._messages = messages
    return messages


def main():
    user = User.objects.filter(is_active=True).first()
    other = User.objects.exclude(pk=user.pk).filter(is_active=True).first()
    client = Client.objects.first()
    print('user=', user, 'other=', other, 'client=', client)
    if not user or not client:
        return

    contact, _ = Contact.objects.get_or_create(
        client=client,
        defaults={'preferred_channel': 'whatsapp'},
    )
    if other:
        conv = (
            Conversation.objects.filter(
                contact=contact,
                channel='whatsapp',
                status__in=['normal', 'pending', 'open', 'assigned'],
            ).first()
        )
        if not conv:
            conv = Conversation.objects.create(
                contact=contact,
                channel='whatsapp',
                status='normal',
                assigned_to=other,
            )
        else:
            conv.assigned_to = other
            conv.save(update_fields=['assigned_to'])

    rf = RequestFactory()
    with override_settings(ALLOWED_HOSTS=['*'], DEBUG=True):
        req = rf.get('/communications/')
        req.user = user
        attach_messages(req)
        warning(
            req,
            format_html(
                '<div class="comm-lock-msg"><strong class="comm-lock-msg__title">Conversación no disponible</strong></div>'
            ),
            extra_tags='comm-access-locked',
        )
        try:
            resp = dashboard(req)
            if hasattr(resp, 'render'):
                resp.render()
            print('dashboard', resp.status_code, 'overlay', b'commAccessLockedOverlay' in resp.content)
        except Exception:
            print('DASHBOARD FAIL')
            traceback.print_exc()

        if other:
            req2 = rf.get(f'/communications/client/{client.pk}/whatsapp/whatsapp/')
            req2.user = user
            attach_messages(req2)
            try:
                resp2 = open_client_whatsapp(req2, client.pk, 'whatsapp')
                print('open_client', getattr(resp2, 'status_code', resp2), getattr(resp2, 'url', None))
            except Exception:
                print('OPEN FAIL')
                traceback.print_exc()


if __name__ == '__main__':
    main()
