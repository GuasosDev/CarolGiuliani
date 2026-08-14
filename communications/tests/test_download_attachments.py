from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
import zipfile

from django.contrib.auth import get_user_model

from communications.models import Conversation, Message, EmailMessage, EmailAttachment, EmailAccount

User = get_user_model()


class DownloadAttachmentsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'u@example.com', 'pass')
        self.client = Client()
        self.client.login(username='testuser', password='pass')

        # Conversation
        self.conversation = Conversation.objects.create(channel='email')

        # Email account (minimal required fields)
        self.email_account = EmailAccount.objects.create(
            user=self.user,
            name='Test Account',
            email_address='acct@example.com',
            provider='imap',
            imap_host='imap.example',
            imap_port=993,
            imap_use_ssl=True,
            smtp_host='smtp.example',
            smtp_port=587,
            smtp_use_tls=True,
            username='acctuser',
            encrypted_password=b'0'
        )

        # Message + EmailMessage
        msg = Message.objects.create(conversation=self.conversation, message_type='email', direction='inbound')
        email_msg = EmailMessage.objects.create(
            message=msg,
            email_account=self.email_account,
            subject='Test',
            email_message_id='msg-1',
            from_address='from@example.com'
        )

        # Attachment
        f = SimpleUploadedFile('foo.txt', b'hello world', content_type='text/plain')
        att = EmailAttachment.objects.create(email_message=email_msg, filename='foo.txt', mime_type='text/plain', size=len(b'hello world'))
        att.file.save('foo.txt', f, save=True)

    def test_download_contains_attachment(self):
        url = f'/communications/conversation/{self.conversation.id}/download-attachments/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Read response content into a BytesIO and inspect zip
        buf = BytesIO(resp.content)
        z = zipfile.ZipFile(buf)
        names = z.namelist()
        self.assertTrue(any('foo.txt' in n for n in names))
