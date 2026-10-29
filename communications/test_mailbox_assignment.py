from django.contrib.auth import get_user_model
from django.test import TestCase

from clients.models import Client
from communications.assignment_system import reassign_conversation
from communications.email_handler import EmailHandler
from communications.models import (
    Contact,
    Conversation,
    EmailAccount,
    EmailMessage,
    Message,
)

User = get_user_model()


class MailboxAssignmentTest(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user('gise', 'gise@example.com', 'pass')
        self.user_b = User.objects.create_user('nati', 'nati@example.com', 'pass')
        self.account_a = EmailAccount.objects.create(
            user=self.user_a,
            name='Casilla A',
            email_address='gise@example.com',
            provider='imap',
            imap_host='imap.example',
            imap_port=993,
            imap_use_ssl=True,
            smtp_host='smtp.example',
            smtp_port=587,
            smtp_use_tls=True,
            username='gise',
            encrypted_password=b'0',
        )
        self.client_obj = Client.objects.create(
            name='Cliente Test',
            email='cliente@example.com',
        )
        self.contact = Contact.objects.create(
            client=self.client_obj,
            preferred_channel='email',
        )
        self.handler = EmailHandler(self.account_a)

    def _seed_message(self, conversation, message_id='<orig@test>'):
        msg = Message.objects.create(
            conversation=conversation,
            message_type='email',
            direction='inbound',
        )
        return EmailMessage.objects.create(
            message=msg,
            email_account=self.account_a,
            subject='Consulta',
            email_message_id=message_id,
            from_address='cliente@example.com',
        )

    def test_reply_to_derived_thread_stays_in_mailbox_a(self):
        conv_b = Conversation.objects.create(
            email_account=self.account_a,
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
            assigned_to=self.user_b,
        )
        self._seed_message(conv_b, '<orig@test>')

        result = self.handler.get_or_create_conversation(
            self.account_a,
            self.contact,
            'Re: Consulta',
            '<orig@test>',
            None,
        )

        self.assertNotEqual(result.id, conv_b.id)
        result.refresh_from_db()
        self.assertEqual(result.assigned_to_id, self.user_a.id)
        conv_b.refresh_from_db()
        self.assertEqual(conv_b.assigned_to_id, self.user_b.id)

    def test_same_subject_derived_thread_does_not_steal_new_mail(self):
        conv_b = Conversation.objects.create(
            email_account=self.account_a,
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
            assigned_to=self.user_b,
        )

        result = self.handler.get_or_create_conversation(
            self.account_a,
            self.contact,
            'Consulta',
            None,
            None,
        )

        self.assertNotEqual(result.id, conv_b.id)
        self.assertEqual(result.assigned_to_id, self.user_a.id)

    def test_own_thread_is_reused(self):
        conv_a = Conversation.objects.create(
            email_account=self.account_a,
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
            assigned_to=self.user_a,
        )
        self._seed_message(conv_a, '<mine@test>')

        result = self.handler.get_or_create_conversation(
            self.account_a,
            self.contact,
            'Re: Consulta',
            '<mine@test>',
            None,
        )

        self.assertEqual(result.id, conv_a.id)
        self.assertEqual(result.assigned_to_id, self.user_a.id)

    def test_unassigned_mailbox_thread_is_assigned_to_owner(self):
        conv = Conversation.objects.create(
            email_account=self.account_a,
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
        )

        result = self.handler.get_or_create_conversation(
            self.account_a,
            self.contact,
            'Consulta',
            None,
            None,
        )

        self.assertEqual(result.id, conv.id)
        result.refresh_from_db()
        self.assertEqual(result.assigned_to_id, self.user_a.id)

    def test_manual_derive_still_works(self):
        conv = Conversation.objects.create(
            email_account=self.account_a,
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
            assigned_to=self.user_a,
        )

        reassign_conversation(conv, self.user_b, self.user_a)
        conv.refresh_from_db()
        self.assertEqual(conv.assigned_to_id, self.user_b.id)
