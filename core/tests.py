from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client as Customer
from communications.models import Contact, Conversation, EmailAccount, EmailMessage, Message


class GlobalSearchEmailLinkTests(TestCase):
    def test_contact_email_action_opens_latest_visible_email_conversation(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='search-agent',
            email='agent@example.com',
            password='test-password',
        )
        other_user = user_model.objects.create_user(
            username='other-agent',
            email='other@example.com',
            password='test-password',
        )
        account = EmailAccount.objects.create(
            user=user,
            name='Search account',
            email_address='agent@example.com',
            provider='imap',
            imap_host='imap.example.com',
            smtp_host='smtp.example.com',
            username='agent@example.com',
            encrypted_password=b'test',
        )
        client = Customer.objects.create(
            name='Global Search Email Client',
            email='client@example.com',
        )
        contact = Contact.objects.create(client=client)
        now = timezone.now()

        def create_email_conversation(assigned_to, email_date, subject):
            conversation = Conversation.objects.create(
                contact=contact,
                email_account=account,
                channel='email',
                assigned_to=assigned_to,
                subject=subject,
            )
            message = Message.objects.create(
                conversation=conversation,
                message_type='email',
                direction='inbound',
                content=subject,
            )
            EmailMessage.objects.create(
                message=message,
                email_account=account,
                subject=subject,
                email_message_id=f'<{subject}@example.com>',
                from_address='client@example.com',
                email_date=email_date,
            )
            return conversation

        visible_conversation = create_email_conversation(
            user,
            now - timedelta(days=1),
            'Visible thread',
        )
        create_email_conversation(
            other_user,
            now,
            'Thread assigned to another agent',
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse('global_search'),
            {'q': 'Global Search Email Client'},
        )

        self.assertEqual(response.status_code, 200)
        contact_section = next(
            section for section in response.context['results']
            if section['title'] == 'Contactos'
        )
        result = next(
            item for item in contact_section['items']
            if item['meta'] == 'Contacto'
        )
        self.assertIn(
            f'conversation={visible_conversation.pk}',
            result['tertiary']['href'],
        )

# Create your tests here.
