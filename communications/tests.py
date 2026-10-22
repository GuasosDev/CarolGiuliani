from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from rest_framework.permissions import IsAuthenticated
from types import SimpleNamespace
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
    ContactMenuState,
    Conversation,
    EmailAccount,
    EmailMessage,
    InternalChatMessage,
    Message,
    WelcomeMenu,
    WelcomeMenuItem,
    WhatsAppAccount,
)
from communications.utils.email_threading import (
    clean_message_id,
    normalize_email_subject,
    subjects_match,
)
from communications.utils.html_cleaner import email_html_to_text, limpiar_email_html
from communications.whatsapp_handler import _has_unanswered_template
from communications.views import _render_internal_chat_content

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


class InternalChatMentionRenderingTests(SimpleTestCase):
    def test_mentions_render_with_display_name_and_avatar_initials(self):
        rendered = _render_internal_chat_content(
            'Hola @ ana, ¿puedes revisarlo?',
            {
                'ana': {
                    'name': 'Ana Pérez',
                    'initials': 'AP',
                },
            },
        )

        self.assertIn('class="internal-chat-mention"', rendered)
        self.assertIn('@Ana Pérez', rendered)
        self.assertNotIn('internal-chat-mention-avatar', rendered)

    def test_mentions_match_username_case_insensitively(self):
        rendered = _render_internal_chat_content(
            'Hola @ ANA',
            {
                'ana': {
                    'name': 'Ana Pérez',
                    'initials': 'AP',
                },
            },
        )

        self.assertIn('@Ana Pérez', rendered)

    def test_message_content_is_escaped_and_newlines_are_preserved(self):
        rendered = _render_internal_chat_content(
            '<script>alert(1)</script>\n@ana',
            {
                'ana': {
                    'name': 'Ana',
                    'initials': 'A',
                },
            },
        )

        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('<br>', rendered)
        self.assertIn('@Ana', rendered)


class InternalChatMessagesPartialTests(SimpleTestCase):
    @patch('communications.views.render')
    @patch('communications.views.User.objects.filter')
    @patch('communications.views.InternalChatMessage.objects.filter')
    @patch('communications.views.InternalChatReadState.objects.update_or_create')
    def test_messages_remain_available_for_template_after_rendering(
        self,
        _update_read_state,
        filter_messages,
        filter_users,
        render,
    ):
        author = SimpleNamespace(
            pk=1,
            username='maria',
            get_full_name=lambda: 'María Gómez',
        )
        current_user = SimpleNamespace(
            pk=2,
            username='ana',
            get_full_name=lambda: 'Ana Pérez',
        )
        message = SimpleNamespace(
            pk=10,
            author_id=author.pk,
            author=author,
            content='Hola @ana',
        )
        filter_messages.return_value.select_related.return_value.order_by.return_value = [message]
        filter_users.return_value.only.return_value = [current_user]
        request = RequestFactory().get('/communications/internal-chat/messages/')
        request.user = SimpleNamespace(is_authenticated=True, pk=current_user.pk)

        from communications.views import internal_chat_messages_partial

        internal_chat_messages_partial(request)

        rendered_messages = render.call_args.args[2]['messages']
        self.assertEqual(len(rendered_messages), 1)
        self.assertEqual(rendered_messages[0].author_display_name, 'María Gómez')
        self.assertIn('@Ana Pérez', rendered_messages[0].rendered_content)


class InternalChatMentionViewTests(SimpleTestCase):
    @patch('communications.views.InternalChatReadState.objects.update_or_create')
    @patch('communications.views.InternalChatMessage.objects.create')
    @patch('communications.views.User.objects.filter')
    def test_mention_sends_private_message_to_one_user(
        self,
        filter_users,
        create_message,
        _update_read_state,
    ):
        recipient = SimpleNamespace(pk=3, username='ana')
        filter_users.return_value.only.return_value = [recipient]
        request = RequestFactory().post(
            '/communications/internal-chat/send/',
            {'content': 'Hola @ ana'},
        )
        request.user = SimpleNamespace(is_authenticated=True, pk=2)

        from communications.views import internal_chat_send

        response = internal_chat_send(request)

        self.assertEqual(response.status_code, 200)
        create_message.assert_called_once_with(
            author=request.user,
            content='Hola @ ana',
            mentioned_user=recipient,
            is_private=True,
        )

    @patch('communications.views.InternalChatReadState.objects.update_or_create')
    @patch('communications.views.InternalChatMessage.objects.create')
    @patch('communications.views.User.objects.filter')
    def test_message_without_mention_remains_public(
        self,
        filter_users,
        create_message,
        _update_read_state,
    ):
        filter_users.return_value.only.return_value = [
            SimpleNamespace(pk=3, username='ana')
        ]
        request = RequestFactory().post(
            '/communications/internal-chat/send/',
            {'content': 'Hola a todos'},
        )
        request.user = SimpleNamespace(is_authenticated=True, pk=2)

        from communications.views import internal_chat_send

        response = internal_chat_send(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(create_message.call_args.kwargs['is_private'])
        self.assertIsNone(create_message.call_args.kwargs['mentioned_user'])

    @patch('communications.views.InternalChatMessage.objects.create')
    @patch('communications.views.User.objects.filter')
    def test_multiple_mentions_are_rejected_to_avoid_ambiguous_privacy(
        self,
        filter_users,
        create_message,
    ):
        filter_users.return_value.only.return_value = [
            SimpleNamespace(pk=3, username='ana'),
            SimpleNamespace(pk=4, username='maria'),
        ]
        request = RequestFactory().post(
            '/communications/internal-chat/send/',
            {'content': 'Hola @ana y @maria'},
        )
        request.user = SimpleNamespace(is_authenticated=True, pk=2)

        from communications.views import internal_chat_send

        response = internal_chat_send(request)

        self.assertEqual(response.status_code, 400)
        create_message.assert_not_called()


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


class WelcomeMenuAgentOutreachTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user('nati_wa', 'nati_wa@example.com', 'pass')
        self.contact = Contact.objects.create(
            whatsapp_number='5491112345678',
            preferred_channel='whatsapp',
        )
        self.conversation = Conversation.objects.create(
            contact=self.contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.agent,
        )

    def test_unanswered_template_skips_welcome_menu(self):
        from communications.whatsapp_handler import _has_unanswered_template

        Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='outbound',
            content='📄 Plantilla: inicio_conversacion',
            sender=self.agent,
            metadata={
                'template_name': 'inicio_conversacion',
                'template_language': 'es_AR',
            },
        )
        inbound = Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='inbound',
            content='hola',
        )
        self.assertTrue(_has_unanswered_template(self.contact, inbound))

    def test_client_first_message_does_not_look_like_template_reply(self):
        from communications.whatsapp_handler import _has_unanswered_template

        inbound = Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='inbound',
            content='hola',
        )
        self.assertFalse(_has_unanswered_template(self.contact, inbound))


class InboundReplyAfterTransferTests(TestCase):
    @patch('communications.websocket_utils.broadcast_new_message')
    @patch('communications.whatsapp_handler.WhatsAppHandler.mark_message_as_read', return_value=True)
    def test_reply_to_template_stays_on_transferred_conversation(self, _mark_read, _broadcast):
        from communications.whatsapp_handler import process_incoming_message

        nati = User.objects.create_user('nati_transfer', 'nati_transfer@example.com', 'pass')
        gise = User.objects.create_user('gise_transfer', 'gise_transfer@example.com', 'pass')
        client = Client.objects.create(
            name='Cliente transferido',
            email='cliente-transferido@example.com',
            phone='1112345678',
        )
        owner_contact = Contact.objects.create(
            client=client,
            preferred_channel='whatsapp',
        )
        shadow_contact = Contact.objects.create(
            whatsapp_number='5491112345678',
            preferred_channel='whatsapp',
        )
        conversation = Conversation.objects.create(
            contact=owner_contact,
            channel='whatsapp',
            status='normal',
            assigned_to=nati,
        )
        reassign_conversation(conversation, gise, nati)
        Message.objects.create(
            conversation=conversation,
            message_type='whatsapp',
            direction='outbound',
            content='📄 Plantilla: inicio_conversacion',
            sender=gise,
            metadata={'to': '5491112345678', 'template_name': 'inicio_conversacion'},
        )
        account = WhatsAppAccount.objects.create(
            name='WA',
            phone_number='5491100000000',
            phone_number_id='phone-1',
            business_account_id='biz-1',
            access_token='token',
            webhook_verify_token='verify',
        )

        process_incoming_message(
            account,
            {
                'from': '5491112345678',
                'id': 'wamid.hola.transfer',
                'timestamp': '1710000000',
                'type': 'text',
                'text': {'body': 'hola'},
            },
            {'contacts': [{'profile': {'name': 'Cliente transferido'}}]},
        )

        inbound = Message.objects.get(direction='inbound', content='hola')
        conversation.refresh_from_db()
        self.assertEqual(inbound.conversation_id, conversation.id)
        self.assertEqual(conversation.assigned_to_id, gise.id)
        self.assertFalse(
            Message.objects.filter(conversation__contact=shadow_contact, direction='inbound').exists()
        )


class ForceWelcomeMenuOnManualCloseTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user('agente_menu', 'agente_menu@example.com', 'pass')
        self.other = User.objects.create_user('ventas_menu', 'ventas_menu@example.com', 'pass')
        self.contact = Contact.objects.create(
            whatsapp_number='5491112345678',
            preferred_channel='whatsapp',
        )
        self.conversation = Conversation.objects.create(
            contact=self.contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.agent,
        )
        self.menu = WelcomeMenu.objects.create(
            name='Inicio',
            is_active=True,
            greeting_text='Hola, bienvenido',
            footer_text='Responda con el número',
        )
        WelcomeMenuItem.objects.create(
            menu=self.menu,
            number=2,
            label='Ventas',
            assigned_user=self.other,
        )
        self.account = WhatsAppAccount.objects.create(
            name='WA menu',
            phone_number='5491100000099',
            phone_number_id='phone-menu',
            business_account_id='biz-menu',
            access_token='token',
            webhook_verify_token='verify',
        )

    def test_manual_close_marks_contact_and_clears_menu_state(self):
        ContactMenuState.objects.create(contact=self.contact, menu=self.menu)

        self.conversation.close()

        self.contact.refresh_from_db()
        self.conversation.refresh_from_db()
        self.assertTrue(self.contact.force_welcome_menu)
        self.assertEqual(self.conversation.status, 'closed')
        self.assertFalse(ContactMenuState.objects.filter(contact=self.contact).exists())

    def test_manual_close_marks_contact_that_shares_the_phone(self):
        owner = Contact.objects.create(preferred_channel='whatsapp')
        shadow = Contact.objects.create(
            whatsapp_number='5491188887777',
            preferred_channel='whatsapp',
        )
        conversation = Conversation.objects.create(
            contact=owner,
            channel='whatsapp',
            status='normal',
        )
        Message.objects.create(
            conversation=conversation,
            message_type='whatsapp',
            direction='outbound',
            content='📄 Plantilla: inicio',
            metadata={'to': '5491188887777', 'template_name': 'inicio'},
        )

        conversation.close()

        owner.refresh_from_db()
        shadow.refresh_from_db()
        self.assertTrue(owner.force_welcome_menu)
        self.assertTrue(shadow.force_welcome_menu)

    def test_email_close_does_not_arm_flag(self):
        email_conversation = Conversation.objects.create(
            contact=self.contact,
            channel='email',
            status='normal',
            subject='Consulta',
        )

        email_conversation.close()

        self.contact.refresh_from_db()
        self.assertFalse(self.contact.force_welcome_menu)
        self.assertEqual(email_conversation.status, 'closed')

    def test_automatic_close_does_not_arm_flag(self):
        from datetime import timedelta

        from django.utils import timezone

        from communications.tasks import close_inactive_conversations

        Conversation.objects.filter(pk=self.conversation.pk).update(
            status='pending',
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        close_inactive_conversations()

        self.conversation.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.conversation.status, 'closed')
        self.assertFalse(self.contact.force_welcome_menu)

    @patch('communications.websocket_utils.broadcast_new_message')
    @patch('communications.whatsapp_handler.WhatsAppHandler.mark_message_as_read', return_value=True)
    @patch('communications.whatsapp_handler.requests.post')
    def test_client_text_same_day_forces_welcome_menu(self, post, _mark_read, _broadcast):
        from communications.whatsapp_handler import process_incoming_message

        post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'messages': [{'id': 'wamid.menu.nuevo'}]}),
            raise_for_status=Mock(),
        )
        Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='outbound',
            content='Hola, bienvenido',
            metadata={
                'welcome_menu': True,
                'welcome_menu_id': self.menu.id,
                'to': '5491112345678',
            },
        )
        Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='outbound',
            content='📄 Plantilla: inicio_conversacion',
            sender=self.agent,
            metadata={'to': '5491112345678', 'template_name': 'inicio_conversacion'},
        )
        ContactMenuState.objects.create(contact=self.contact, menu=self.menu)
        self.conversation.close()

        handled = process_incoming_message(
            self.account,
            {
                'from': '5491112345678',
                'id': 'wamid.cliente.2',
                'timestamp': '1710000000',
                'type': 'text',
                'text': {'body': '2'},
            },
            {'contacts': [{'profile': {'name': 'Cliente'}}]},
        )

        self.contact.refresh_from_db()
        self.conversation.refresh_from_db()
        welcome_messages = Message.objects.filter(
            direction='outbound',
            metadata__welcome_menu=True,
        )
        self.assertTrue(handled)
        self.assertEqual(welcome_messages.count(), 2)
        self.assertFalse(self.contact.force_welcome_menu)
        self.assertEqual(self.conversation.assigned_to_id, self.agent.id)
        self.assertFalse(
            Message.objects.filter(content__icontains='Te hemos conectado').exists()
        )
        self.assertFalse(
            Message.objects.filter(content__icontains='Opción no válida').exists()
        )
        self.assertTrue(ContactMenuState.objects.filter(contact=self.contact, menu=self.menu).exists())

    @patch('communications.whatsapp_handler.requests.post')
    def test_template_after_close_does_not_force_menu(self, post):
        from communications.whatsapp_handler import WhatsAppHandler, _handle_welcome_menu

        post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'messages': [{'id': 'wamid.plantilla'}]}),
            raise_for_status=Mock(),
        )
        self.conversation.close()
        self.contact.refresh_from_db()
        self.assertTrue(self.contact.force_welcome_menu)

        sent, _message_id = WhatsAppHandler(self.account).send_template_message(
            to_number='5491112345678',
            template_name='inicio_conversacion',
            language_code='es_AR',
            conversation=self.conversation,
            sender_user=self.agent,
        )
        self.contact.refresh_from_db()
        inbound = Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='inbound',
            content='hola',
        )

        class RecordingHandler:
            def __init__(self):
                self.sent = []

            def send_text_message(self, to_number, message_text, conversation=None, sender_user=None, metadata=None):
                self.sent.append(message_text)
                return True, 'wamid.no-debe'

        handler = RecordingHandler()
        _handle_welcome_menu(
            handler,
            self.contact,
            self.conversation,
            'hola',
            inbound,
            force_show=True,
        )

        self.assertTrue(sent)
        self.assertFalse(self.contact.force_welcome_menu)
        self.assertEqual(handler.sent, [])

    @patch('communications.websocket_utils.broadcast_new_message')
    @patch('communications.whatsapp_handler.WhatsAppHandler.mark_message_as_read', return_value=True)
    @patch('communications.whatsapp_handler.requests.post')
    def test_inbound_image_triggers_welcome_menu_as_contact_attempt(self, post, _mark_read, _broadcast):
        """Una imagen nueva solo marca inicio de contacto: se guarda y abre el menú."""
        from communications.whatsapp_handler import process_incoming_message

        post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'messages': [{'id': 'wamid.menu.img'}]}),
            raise_for_status=Mock(),
        )
        # Conversación nueva sin outreach previo (cliente inicia con imagen).
        self.conversation.assigned_to = None
        self.conversation.save(update_fields=['assigned_to'])

        handled = process_incoming_message(
            self.account,
            {
                'from': '5491112345678',
                'id': 'wamid.cliente.img',
                'timestamp': '1710000000',
                'type': 'image',
                'image': {'mime_type': 'image/jpeg'},
            },
            {'contacts': [{'profile': {'name': 'Cliente Img'}}]},
        )

        self.assertTrue(handled)
        inbound = Message.objects.get(direction='inbound', whatsapp_data__whatsapp_message_id='wamid.cliente.img')
        self.assertIn('[IMAGE]', inbound.content)
        welcome = Message.objects.filter(
            direction='outbound',
            metadata__welcome_menu=True,
        )
        self.assertEqual(welcome.count(), 1)
        self.assertTrue(ContactMenuState.objects.filter(contact=self.contact, menu=self.menu).exists())

    @patch('communications.whatsapp_handler.requests.post')
    def test_media_while_waiting_menu_does_not_count_as_selection(self, post):
        from communications.whatsapp_handler import _handle_welcome_menu

        ContactMenuState.objects.create(contact=self.contact, menu=self.menu)
        inbound = Message.objects.create(
            conversation=self.conversation,
            message_type='whatsapp',
            direction='inbound',
            content='[IMAGE]',
        )

        class RecordingHandler:
            def __init__(self):
                self.sent = []

            def send_text_message(self, to_number, message_text, conversation=None, sender_user=None, metadata=None):
                self.sent.append(message_text)
                return True, 'wamid.x'

        handler = RecordingHandler()
        _handle_welcome_menu(
            handler,
            self.contact,
            self.conversation,
            'inicio',
            inbound,
            media_contact_attempt=True,
        )
        self.assertEqual(handler.sent, [])
        self.assertTrue(ContactMenuState.objects.filter(contact=self.contact).exists())
