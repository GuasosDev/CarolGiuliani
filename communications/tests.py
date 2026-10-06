from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.permissions import IsAuthenticated
from unittest.mock import Mock, patch

from clients.models import Client
from communications.api.views import WhatsAppAccountViewSet
from communications.assignment_system import (
    assign_conversation_to_agent,
    reassign_conversation,
)
from communications.email_handler import EmailHandler
from communications.models import (
    Contact,
    Conversation,
    EmailAccount,
    EmailMessage,
    Message,
)
from communications.utils.email_threading import (
    clean_message_id,
    normalize_email_subject,
    subjects_match,
)
from communications.utils.html_cleaner import email_html_to_text, limpiar_email_html
from communications.whatsapp_handler import _has_unanswered_template

User = get_user_model()


class EmailHtmlRenderingTests(SimpleTestCase):
    def test_search_preview_shows_plain_email_text_without_quoted_history(self):
        preview = email_html_to_text(
            '<div dir="auto">Mensaje reciente</div>'
            '<div class="gmail_quote gmail_quote_container">'
            '<blockquote><div>Contenido anterior</div></blockquote>'
            '</div>'
        )

        self.assertEqual(preview, 'Mensaje reciente')

    def test_gmail_quoted_history_is_collapsed_but_kept(self):
        rendered = limpiar_email_html(
            '<div>Mensaje nuevo</div>'
            '<div class="gmail_quote gmail_quote_container">'
            '<div class="gmail_attr">El mensaje anterior</div>'
            '<blockquote>Contenido citado</blockquote>'
            '</div>'
        )

        self.assertIn('Mensaje nuevo', rendered)
        self.assertIn('<details class="email-quoted-history">', rendered)
        self.assertIn('<summary>Mostrar mensaje citado</summary>', rendered)
        self.assertIn('Contenido citado', rendered)


class WhatsAppTemplatePermissionTests(SimpleTestCase):
    def test_sending_templates_requires_authentication_not_staff_status(self):
        self.assertEqual(
            WhatsAppAccountViewSet.send_template.kwargs['permission_classes'],
            [IsAuthenticated],
        )

    @patch('communications.whatsapp_handler.Message.objects.filter')
    def test_template_reply_is_recognized_even_after_midnight(self, filter_messages):
        conversation = object()
        inbound_message = Mock(created_at=object())
        prior_messages = Mock()
        earlier_inbound_messages = Mock()
        template_messages = Mock()

        filter_messages.return_value = prior_messages
        prior_messages.filter.side_effect = [
            earlier_inbound_messages,
            template_messages,
        ]
        earlier_inbound_messages.order_by.return_value.first.return_value = None
        template_messages.exists.return_value = True

        self.assertTrue(_has_unanswered_template(conversation, inbound_message))
        filter_messages.assert_called_once_with(
            conversation=conversation,
            message_type='whatsapp',
            created_at__lt=inbound_message.created_at,
        )


class EmailThreadingUtilsTest(SimpleTestCase):
    def test_normalize_strips_re_fwd(self):
        self.assertEqual(
            normalize_email_subject('Re: Fwd: Presupuesto marzo'),
            'presupuesto marzo',
        )

    def test_normalize_empty(self):
        self.assertEqual(normalize_email_subject(''), '')
        self.assertEqual(normalize_email_subject(None), '')

    def test_subjects_match_ignores_prefixes(self):
        self.assertTrue(subjects_match('Presupuesto', 'Re: Presupuesto'))
        self.assertFalse(subjects_match('Presupuesto', 'Consulta técnica'))

    def test_clean_message_id_brackets(self):
        self.assertEqual(
            clean_message_id('<abc@mail.test>'),
            'abc@mail.test',
        )


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


class ExclusiveAssignmentTest(TestCase):
    """Un hilo tomado por una secretaria no se pisa salvo derivación manual."""

    def setUp(self):
        self.gise = User.objects.create_user('gise2', 'gise2@example.com', 'pass')
        self.nati = User.objects.create_user('nati2', 'nati2@example.com', 'pass')
        self.client_obj = Client.objects.create(
            name='Cliente Exclusive',
            email='exclusive@example.com',
        )
        self.contact = Contact.objects.create(
            client=self.client_obj,
            preferred_channel='email',
        )

    def test_auto_assign_does_not_steal_from_other_secretary(self):
        conv = Conversation.objects.create(
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Hilo Gise',
            assigned_to=self.gise,
        )
        result = assign_conversation_to_agent(conv, agent=self.nati, assigned_by=self.nati)
        conv.refresh_from_db()
        self.assertEqual(conv.assigned_to_id, self.gise.id)
        self.assertEqual(result.id, self.gise.id)

    def test_assign_to_without_reassign_flag_refuses_steal(self):
        conv = Conversation.objects.create(
            contact=self.contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.gise,
        )
        ok = conv.assign_to(self.nati, allow_reassign=False)
        conv.refresh_from_db()
        self.assertFalse(ok)
        self.assertEqual(conv.assigned_to_id, self.gise.id)

    def test_distribute_workload_skips_assigned(self):
        from communications.assignment_system import distribute_workload

        Conversation.objects.create(
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Ya tomada',
            assigned_to=self.gise,
        )
        distribute_workload()
        conv = Conversation.objects.get(subject='Ya tomada')
        self.assertEqual(conv.assigned_to_id, self.gise.id)

    def test_manual_reassign_is_allowed(self):
        conv = Conversation.objects.create(
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Derivar',
            assigned_to=self.gise,
        )
        reassign_conversation(conv, self.nati, self.gise)
        conv.refresh_from_db()
        self.assertEqual(conv.assigned_to_id, self.nati.id)
