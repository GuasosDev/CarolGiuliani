from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from communications.models import Contact, Conversation


User = get_user_model()


class OpenClientWhatsAppTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('agent', password='pass')
        self.other_agent = User.objects.create_user('other-agent', password='pass')
        self.client_obj = Client.objects.create(
            name='Cliente con chat asignado',
            email='assigned@example.com',
        )
        self.contact = Contact.objects.create(
            client=self.client_obj,
            preferred_channel='whatsapp',
        )
        self.client.force_login(self.user)

    def test_warns_instead_of_opening_another_agents_conversation(self):
        conversation = Conversation.objects.create(
            contact=self.contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.other_agent,
        )

        response = self.client.get(reverse(
            'communications:open_client_whatsapp',
            args=[self.client_obj.pk, 'whatsapp'],
        ))

        self.assertRedirects(
            response,
            f"{reverse('communications:dashboard')}?channel=whatsapp",
            fetch_redirect_response=False,
        )
        self.assertEqual(Conversation.objects.filter(contact=self.contact).count(), 1)
        self.assertEqual(
            Conversation.objects.get(pk=conversation.pk).assigned_to,
            self.other_agent,
        )
        self.assertIn(
            'está asignada a other-agent',
            str(list(get_messages(response.wsgi_request))),
        )

    def test_opens_an_accessible_active_conversation(self):
        conversation = Conversation.objects.create(
            contact=self.contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.user,
        )

        response = self.client.get(reverse(
            'communications:open_client_whatsapp',
            args=[self.client_obj.pk, 'whatsapp'],
        ))

        self.assertRedirects(
            response,
            f"{reverse('communications:dashboard')}?channel=whatsapp&conversation={conversation.pk}",
            fetch_redirect_response=False,
        )
