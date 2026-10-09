from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from communications.api.views import _validate_template_header_attachment
from communications.models import Contact, Conversation, WhatsAppAccount
from communications.whatsapp_handler import WhatsAppHandler
from core.models import CompanySettings
from clients.models import Client


class WhatsAppTemplateAttachmentValidationTests(SimpleTestCase):
    def test_requires_a_file_for_a_media_header(self):
        error = _validate_template_header_attachment(None, 'image')

        self.assertEqual(error, 'Selecciona un archivo para el encabezado de la plantilla.')

    def test_rejects_file_that_does_not_match_header_type(self):
        uploaded_file = SimpleUploadedFile(
            'document.pdf',
            b'%PDF',
            content_type='application/pdf',
        )

        error = _validate_template_header_attachment(uploaded_file, 'image')

        self.assertIn('requiere un archivo', error)

    def test_rejects_image_above_whatsapp_size_limit(self):
        uploaded_file = SimpleUploadedFile(
            'image.png',
            b'x' * (5 * 1024 * 1024 + 1),
            content_type='image/png',
        )

        error = _validate_template_header_attachment(uploaded_file, 'image')

        self.assertIn('supera el límite de 5 MB', error)

    def test_accepts_valid_document_header(self):
        uploaded_file = SimpleUploadedFile(
            'document.pdf',
            b'%PDF',
            content_type='application/pdf',
        )

        self.assertIsNone(
            _validate_template_header_attachment(uploaded_file, 'document')
        )


class WhatsAppTemplateAttachmentPayloadTests(SimpleTestCase):
    @override_settings(
        WHATSAPP_API_URL='https://graph.facebook.com',
        WHATSAPP_API_VERSION='v99.0',
    )
    @patch('communications.whatsapp_handler.requests.post')
    def test_sends_template_header_media_component(self, post):
        post.return_value = Mock(
            json=Mock(return_value={'messages': [{'id': 'wamid.test'}]}),
        )
        handler = WhatsAppHandler(
            SimpleNamespace(phone_number_id='phone-id')
        )
        components = [
            {
                'type': 'header',
                'parameters': [{
                    'type': 'document',
                    'document': {'id': 'media-id'},
                }],
            },
            {
                'type': 'body',
                'parameters': [{'type': 'text', 'text': 'Junio'}],
            },
        ]

        result = handler.send_template_message(
            to_number='5491112345678',
            template_name='recordatorio_documento',
            language_code='es_AR',
            components=components,
            media_type='document',
            media_id='media-id',
        )

        self.assertEqual(result, (True, 'wamid.test'))
        self.assertEqual(
            post.call_args.kwargs['json']['template']['components'],
            components,
        )


class WhatsAppTemplateAttachmentApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            'template-agent',
            'template-agent@example.com',
            'pass',
        )
        self.account = WhatsAppAccount.objects.create(
            name='Test WhatsApp',
            phone_number='+5491112345678',
            phone_number_id='phone-id',
            business_account_id='business-id',
            access_token='token',
            webhook_verify_token='verify',
        )
        client_obj = Client.objects.create(
            name='Cliente plantilla',
            email='template-client@example.com',
            phone='1112345678',
        )
        contact = Contact.objects.create(
            client=client_obj,
            whatsapp_number='5491112345678',
            preferred_channel='whatsapp',
        )
        self.conversation = Conversation.objects.create(
            contact=contact,
            channel='whatsapp',
            status='normal',
            assigned_to=self.user,
        )
        settings = CompanySettings.load()
        settings.whatsapp_templates_enabled = True
        settings.whatsapp_templates = [{
            'name': 'saludo_con_imagen',
            'language': 'es_AR',
            'body_params': 1,
            'header_type': 'image',
        }]
        settings.save(update_fields=['whatsapp_templates_enabled', 'whatsapp_templates'])

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('communications.api.views.WhatsAppHandler')
    def test_uploads_and_sends_configured_header_attachment(self, handler_class):
        handler = handler_class.return_value
        handler.upload_media.return_value = (True, 'uploaded-media-id')
        handler.send_template_message.return_value = (True, 'wamid.test')

        response = self.client.post(
            reverse('whatsappaccount-send-template', kwargs={'pk': self.account.pk}),
            {
                'conversation_id': str(self.conversation.pk),
                'to_number': '5491112345678',
                'template_name': 'saludo_con_imagen',
                'language_code': 'es_AR',
                'body_params': ['Hola'],
                'header_attachment': SimpleUploadedFile(
                    'header.png',
                    b'png-data',
                    content_type='image/png',
                ),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        handler.upload_media.assert_called_once()
        handler.send_template_message.assert_called_once()
        self.assertEqual(
            handler.send_template_message.call_args.kwargs['components'],
            [
                {
                    'type': 'header',
                    'parameters': [{
                        'type': 'image',
                        'image': {'id': 'uploaded-media-id'},
                    }],
                },
                {
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': 'Hola'}],
                },
            ],
        )
