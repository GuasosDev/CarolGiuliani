"""
Email handler for IMAP/SMTP operations
Handles email synchronization, sending, and threading
"""
from email.utils import formataddr, parseaddr, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.utils import timezone
from .models import Message, EmailMessage
import logging
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import parseaddr, formataddr,make_msgid
import logging
from django.utils import timezone
from django.core.files.base import ContentFile
from .models import (
    EmailAccount, EmailMessage, EmailThread, Message,
    Conversation, Contact, EmailAttachment,User
)

logger = logging.getLogger(__name__)


class EmailHandler:
    """Handler for email operations"""
    
    def __init__(self, email_account):
        self.account = email_account
        self.imap_connection = None
        self.smtp_connection = None
    
    def connect_imap(self):
        """Connect to IMAP server"""
        try:
            if self.account.imap_use_ssl:
                self.imap_connection = imaplib.IMAP4_SSL(
                    self.account.imap_host,
                    self.account.imap_port
                )
            else:
                self.imap_connection = imaplib.IMAP4(
                    self.account.imap_host,
                    self.account.imap_port
                )
            
            password = self.account.get_password()
            self.imap_connection.login(self.account.username, password)
            logger.info(f"Connected to IMAP: {self.account.email_address}")
            return True
            
        except Exception as e:
            logger.error(f"IMAP connection error: {str(e)}")
            return False
    
    def connect_smtp(self):
        """Connect to SMTP server"""
        try:
            if self.account.smtp_use_tls:
                self.smtp_connection = smtplib.SMTP(
                    self.account.smtp_host,
                    self.account.smtp_port
                )
                self.smtp_connection.starttls()
            else:
                self.smtp_connection = smtplib.SMTP_SSL(
                    self.account.smtp_host,
                    self.account.smtp_port
                )
            
            password = self.account.get_password()
            self.smtp_connection.login(self.account.username, password)
            logger.info(f"Connected to SMTP: {self.account.email_address}")
            return True
            
        except Exception as e:
            logger.error(f"SMTP connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connections"""
        if self.imap_connection:
            try:
                self.imap_connection.logout()
            except:
                pass
        
        if self.smtp_connection:
            try:
                self.smtp_connection.quit()
            except:
                pass
    
    def fetch_new_emails(self, folder='INBOX'):
        """Fetch new emails from IMAP server"""
        
        if not self.connect_imap():
            return []
        
        try:
            self.imap_connection.select(folder)
            
            # Search for unseen emails
            status, messages = self.imap_connection.search(None, 'UNSEEN')
            
            if status != 'OK':
                return []
            
            email_ids = messages[0].split()
            fetched_emails = []
            
            for email_id in email_ids:
                status, msg_data = self.imap_connection.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Process and store email
                processed = self.process_incoming_email(email_message)
                if processed:
                    fetched_emails.append(processed)
            
            # Update last sync time
            self.account.last_sync_at = timezone.now()
            self.account.save()
            
            logger.info(f"Fetched {len(fetched_emails)} new emails for {self.account.email_address}")
            return fetched_emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            return []
        finally:
            self.disconnect()
    
    def process_incoming_email(self, email_message):
        """Process an incoming email and create database records"""
        try:
            # Extract email headers
            from_address = parseaddr(email_message.get('From', ''))[1]
            to_addresses = [parseaddr(addr)[1] for addr in email_message.get_all('To', [])]
            cc_addresses = [parseaddr(addr)[1] for addr in email_message.get_all('Cc', [])]
            subject = email_message.get('Subject', '(No Subject)')
            message_id = email_message.get('Message-ID', '')
            in_reply_to = email_message.get('In-Reply-To', '')
            references = email_message.get('References', '')
            date = email_message.get('Date', '')
            
            # Extract body
            html_body = None
            plain_body = None
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    
                    if content_type == 'text/plain' and not plain_body:
                        plain_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_type == 'text/html' and not html_body:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                content_type = email_message.get_content_type()
                if content_type == 'text/plain':
                    plain_body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == 'text/html':
                    html_body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Get or create contact based on email address
            contact = self.get_or_create_contact_from_email(from_address)
            
            # Get or create conversation
            conversation = self.get_or_create_conversation(contact, subject, in_reply_to, references)
            
            # Create message
            message = Message.objects.create(
                conversation=conversation,
                message_type='email',
                direction='inbound',
                content=plain_body or html_body or '(Empty message)',
                sender_name=parseaddr(email_message.get('From', ''))[0] or from_address,
                metadata={'date': date}
            )
            
            # Get or create email thread
            email_thread = self.get_or_create_thread(conversation, subject, in_reply_to, references)
            
            # Create email message
            email_msg = EmailMessage.objects.create(
                message=message,
                email_account=self.account,
                subject=subject,
                html_body=html_body,
                plain_body=plain_body,
                email_message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                thread=email_thread,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                from_address=from_address
            )
            
            # Process attachments
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    
                    filename = part.get_filename()
                    if filename:
                        file_data = part.get_payload(decode=True)
                        self.save_attachment(email_msg, filename, file_data, part.get_content_type())
            
            logger.info(f"Processed incoming email: {message_id}")
            return email_msg
            
        except Exception as e:
            logger.error(f"Error processing incoming email: {str(e)}")
            return None
    
    def get_or_create_contact_from_email(self, email_address):
        """Get or create contact from email address"""
        # Try to find existing client by email
        from clients.models import Client
        
        try:
            client = Client.objects.get(email=email_address)
            contact, _ = Contact.objects.get_or_create(
                client=client,
                defaults={'preferred_channel': 'email'}
            )
        except Client.DoesNotExist:
            # Create a placeholder contact (can be linked to client later)
            contact, _ = Contact.objects.get_or_create(
            email=email_address,
            defaults={
            'client': client,
            'preferred_channel': 'email'
            }
            )
        
        return contact
    
    def get_or_create_conversation(self, contact, subject, in_reply_to, references):

        # 1️⃣ Buscar por In-Reply-To
        if in_reply_to:
            parent_email = EmailMessage.objects.filter(
                email_message_id=in_reply_to.strip()
            ).first()

            if parent_email:
                return parent_email.thread.conversation

        # 2️⃣ Buscar por References
        if references:
            reference_ids = references.split()
            parent_email = EmailMessage.objects.filter(
                email_message_id__in=reference_ids
            ).order_by('-created_at').first()

            if parent_email and parent_email.thread:
               return parent_email.thread.conversation

        # 3️⃣ Fallback: mismo contacto + subject similar abierto
        normalized_subject = subject.replace("Re:", "").strip()

        existing_conversation = Conversation.objects.filter(
            contact=contact,
            subject__icontains=normalized_subject,
            status__in=["open", "assigned", "pending"]
        ).order_by('-created_at').first()

        if existing_conversation:
            return existing_conversation

        # 4️⃣ Crear nueva conversación
        conversation = Conversation.objects.create(
            contact=contact,
            channel='email',
            status='open',
            priority='normal',
            subject=subject,
            
 
        )

        from .assignment_system import assign_conversation_to_agent
        assign_conversation_to_agent(conversation)

        return conversation
    
    def get_or_create_thread(self, conversation, subject, in_reply_to, references):
        """Get or create email thread"""
        # Try to find existing thread
        if in_reply_to:
            existing_thread = EmailThread.objects.filter(
                conversation=conversation,
                messages__email_message_id=in_reply_to
            ).first()
            
            if existing_thread:
                existing_thread.last_message_at = timezone.now()
                existing_thread.save()
                return existing_thread
        
        # Create new thread
        thread = EmailThread.objects.create(
            subject=subject,
            conversation=conversation,
            first_message_at=timezone.now(),
            last_message_at=timezone.now(),
            participants=[]
        )
        
        return thread
    
    def save_attachment(self, email_message, filename, file_data, mime_type):
        """Save email attachment"""
        try:
            attachment = EmailAttachment.objects.create(
                email_message=email_message,
                filename=filename,
                mime_type=mime_type,
                size=len(file_data)
            )
            
            attachment.file.save(filename, ContentFile(file_data), save=True)
            logger.info(f"Saved attachment: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving attachment: {str(e)}")
    
    

 

    def send_email(self, to_addresses, subject, body, html_body=None, cc_addresses=None, 
                bcc_addresses=None, attachments=None, conversation=None, signature=None):
        """Send an email and save records in DB"""
        if not self.connect_smtp():
            return False, "Failed to connect to SMTP server"
        
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['From'] = formataddr((self.account.name, self.account.email_address))
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = subject

            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)

            # Generar Message-ID si no existe
            msg_id = make_msgid()
            msg['Message-ID'] = msg_id

            # Agregar firma si existe
            if signature:
                if html_body:
                    html_body += f"<br><br>{signature.html_signature}"
                if body:
                    body += f"\n\n{signature.plain_signature}"

            # Adjuntar cuerpos
            if body:
                msg.attach(MIMEText(body, 'plain'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            # Adjuntar archivos
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['data'])
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={attachment["filename"]}')
                    msg.attach(part)

            # Enviar
            self.smtp_connection.send_message(msg)

            # Guardar en la DB si hay conversación
            

            logger.info(f"Email sent: {subject}")
            return True, "Email sent successfully"

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False, str(e)
        finally:
            self.disconnect()

from django.utils import timezone
from communications.models import EmailQueue, EmailAccount, Conversation
from clients.models import Client

def send_email_to_client(client_id):
    client = Client.objects.get(id=client_id)
    account = EmailAccount.objects.filter(is_active=True).first()

    conversation, _ = Conversation.objects.get_or_create(
        contact__client=client,
        channel='email',
        defaults={
            'status': 'open',
            'priority': 'normal',
            'subject': 'Consulta'
        }
    )

    EmailQueue.objects.create(
        email_account=account,
        to_addresses=[client.email],
        subject="Prueba desde el sistema",
        plain_body="Hola, este es un mensaje enviado desde el sistema.",
        conversation=conversation,
        scheduled_at=timezone.now()
    )