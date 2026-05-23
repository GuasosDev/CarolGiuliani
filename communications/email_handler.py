"""
Email handler for IMAP/SMTP operations
Handles email synchronization, sending, and threading
"""
import mimetypes
from email.utils import formataddr, parseaddr, make_msgid
import uuid
import imaplib
import smtplib
import ssl
import email
from email import policy as email_policy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import parseaddr, formataddr,make_msgid
import logging
import traceback
from django.utils import timezone
from django.core.files.base import ContentFile
from .models import (
    EmailAccount, EmailMessage, EmailThread, Message,
    Conversation, Contact, EmailAttachment,User,QuickReply
)
from .utils.email_headers import decode_mime_header
from .utils.html_cleaner import plain_text_to_email_html
from .utils.email_threading import (
    clean_message_id,
    normalize_email_subject,
    subjects_match,
    _OPEN_CONVERSATION_STATUSES,
)

logger = logging.getLogger(__name__)


class EmailHandler:
    """Handler for email operations"""
    
    def __init__(self, email_account):
        self.account = email_account
        self.imap_connection = None
        self.smtp_connection = None
        self.last_smtp_error = None
    
    def connect_imap(self, timeout=30):
        """Connect to IMAP server"""
        try:
            if self.account.imap_use_ssl:
                self.imap_connection = imaplib.IMAP4_SSL(
                    self.account.imap_host,
                    self.account.imap_port,
                    timeout=timeout
                )
            else:
                self.imap_connection = imaplib.IMAP4(
                    self.account.imap_host,
                    self.account.imap_port,
                    timeout=timeout
                )
            
            password = self.account.get_password()
            self.imap_connection.login(self.account.username, password)
            logger.info(f"Connected to IMAP: {self.account.email_address}")
            return True
            
        except Exception as e:
            logger.error(f"IMAP connection error ({self.account.email_address}): {str(e)}\n{traceback.format_exc()}")
            return False
    
    def connect_smtp(self, timeout=30):
        """Connect to SMTP server"""
        self.last_smtp_error = None
        try:
            smtp_host = (self.account.smtp_host or '').strip()
            smtp_port = int(self.account.smtp_port or 0)
            if not smtp_host or not smtp_port:
                self.last_smtp_error = "SMTP host/puerto no configurado"
                return False

            ctx = ssl.create_default_context()

            use_starttls = bool(self.account.smtp_use_tls)
            use_ssl = not use_starttls

            if smtp_port == 465:
                use_ssl = True
                use_starttls = False
            elif smtp_port == 587:
                use_starttls = True
                use_ssl = False

            if use_ssl:
                self.smtp_connection = smtplib.SMTP_SSL(
                    smtp_host,
                    smtp_port,
                    timeout=timeout,
                    context=ctx,
                )
                try:
                    self.smtp_connection.ehlo()
                except Exception:
                    pass
            else:
                self.smtp_connection = smtplib.SMTP(
                    smtp_host,
                    smtp_port,
                    timeout=timeout
                )
                try:
                    self.smtp_connection.ehlo()
                except Exception:
                    pass
                if use_starttls:
                    try:
                        self.smtp_connection.starttls(context=ctx)
                        try:
                            self.smtp_connection.ehlo()
                        except Exception:
                            pass
                    except smtplib.SMTPNotSupportedError:
                        pass
            
            password = self.account.get_password()
            self.smtp_connection.login(self.account.username, password)
            logger.info(f"Connected to SMTP: {self.account.email_address}")
            return True
            
        except Exception as e:
            self.last_smtp_error = str(e) or e.__class__.__name__
            logger.error(f"SMTP connection error ({self.account.email_address}) on {self.account.smtp_host}:{self.account.smtp_port}: {str(e)}\n{traceback.format_exc()}")
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
        """Fetch emails from IMAP server using UID tracking"""

        if not self.connect_imap():
            return []

        try:
            self.imap_connection.select(folder)

            status = None
            messages = None

            def _imap_caps_text():
                caps = getattr(self.imap_connection, "capabilities", None) or []
                parts = []
                for c in caps:
                    if isinstance(c, bytes):
                        try:
                            parts.append(c.decode(errors="ignore"))
                        except Exception:
                            continue
                    else:
                        parts.append(str(c))
                return " ".join(parts).upper()

            caps_text = _imap_caps_text()
            supports_gmail_raw = (
                self.account.provider == "gmail"
                or "X-GM-EXT-1" in caps_text
                or "GMAIL" in (self.account.imap_host or "").upper()
            )

            if supports_gmail_raw:
                criteria = 'X-GM-RAW "category:primary OR category:promotions"'

                status, messages = self.imap_connection.uid(
                    'SEARCH',
                    None,
                    'ALL'
                )

            if status != "OK":
                criteria = ["ALL"]
                if self.account.last_sync_at:
                    criteria = ["SINCE", self.account.last_sync_at.strftime("%d-%b-%Y")]
                status, messages = self.imap_connection.uid("search", None, *criteria)

            if status != 'OK':
                try:
                    logger.error(
                        f"IMAP search failed ({self.account.email_address}) "
                        f"status={status} criteria={criteria if 'criteria' in locals() else 'X-GM-RAW'} messages={messages}"
                    )
                except Exception:
                    pass
                return []

            email_uids = messages[0].split()
            fetched_emails = []

            for uid in email_uids:

                # verificar si ya existe en DB
                if EmailMessage.objects.filter(email_account=self.account,imap_uid=uid.decode()).exists():
                    continue

                status, msg_data = self.imap_connection.uid(
                    'fetch',
                    uid,
                    '(RFC822)'
                )

                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)

                processed = self.process_incoming_email(
                    email_message,
                    imap_uid=uid.decode()
                )

                if processed:
                    fetched_emails.append(processed)

            self.account.last_sync_at = timezone.now()
            self.account.save()

            logger.info(
                f"Fetched {len(fetched_emails)} emails for {self.account.email_address}"
            )

            return fetched_emails

        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            return []

        finally:
            self.disconnect()

    def clean_email_body(self, body):
        if not body:
            return body

        separators = [
            "On ",
            "El ",
            "From:",
            "De:",
            "-----Original Message-----"
        ]

        for sep in separators:
            if sep in body:
                return body.split(sep)[0].strip()

        return body.strip()
    def normalize_subject(self, subject):
        import re

        if not subject:
            return "(No Subject)"

        subject = re.sub(
            r'^(re|rv|fw|fwd):\s*',
            '',
            subject,
            flags=re.IGNORECASE
        )

        return subject.strip()
    def process_incoming_email(self, email_message, imap_uid=None):
        """Process an incoming email and create database records"""
        try:
            # Extract email headers
            from_address = parseaddr(email_message.get('From', ''))[1]
            to_addresses = [parseaddr(addr)[1] for addr in email_message.get_all('To', []) if parseaddr(addr)[1]]
            cc_addresses = [parseaddr(addr)[1] for addr in email_message.get_all('Cc', []) if parseaddr(addr)[1]]
            bcc_addresses = [parseaddr(addr)[1] for addr in email_message.get_all('Bcc', []) if parseaddr(addr)[1]]
            subject_header = email_message.get('Subject', '') or '(No Subject)'
            raw_subject = decode_mime_header(subject_header) or '(No Subject)'
            subject = self.normalize_subject(raw_subject)
            message_id = email_message.get('Message-ID', '')
            if not message_id:
               message_id = f"<no-id-{uuid.uuid4()}@local>"
            if EmailMessage.objects.filter(email_message_id=message_id).exists():
                logger.warning(f"Duplicate email skipped: {message_id}")
                return None
            in_reply_to = email_message.get('In-Reply-To', '')
            references = email_message.get('References', '')
            date = email_message.get('Date', '')
            if message_id:
                exists = EmailMessage.objects.filter(email_message_id=message_id).exists()
                if exists:
                    logger.warning(f"Duplicate email skipped: {message_id}")
                    return None
            # Extract body (preferir HTML para mostrar en el visor)
            html_body = None
            plain_body = None
            if hasattr(email_message, 'get_body'):
                try:
                    bp = email_message.get_body(preferencelist=('html', 'plain'))
                except Exception:
                    bp = None
                if bp is not None:
                    try:
                        raw = bp.get_payload(decode=True)
                        if raw:
                            charset = bp.get_content_charset() or 'utf-8'
                            txt = raw.decode(charset, errors='ignore')
                            if bp.get_content_type() == 'text/html':
                                html_body = txt
                            else:
                                plain_body = txt
                    except Exception:
                        pass
            if html_body is None and plain_body is None:
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    ctype = part.get_content_type()
                    if ctype not in ('text/plain', 'text/html'):
                        continue
                    try:
                        payload = part.get_payload(decode=True)
                        if not payload:
                            continue
                        charset = part.get_content_charset() or 'utf-8'
                        txt = payload.decode(charset, errors='ignore')
                        if ctype == 'text/html':
                            html_body = txt
                        elif plain_body is None:
                            plain_body = txt
                    except Exception:
                        continue

            # Get or create contact based on email address
            contact = self.get_or_create_contact_from_email(from_address)
            
            # Get or create conversation
            conversation = self.get_or_create_conversation(contact, subject, in_reply_to, references)
            if conversation.user is None and self.account.user:
                conversation.user = self.account.user
                conversation.save()
            
            if html_body and html_body.strip():
                message_content = html_body.strip()
            else:
                plain_clean = self.clean_email_body(plain_body or '') if plain_body else ''
                message_content = plain_text_to_email_html(plain_clean or '(Sin contenido)')

            # Create message
            message = Message.objects.create(
                conversation=conversation,
                message_type='email',
                direction='inbound',
                content=message_content,
                sender_name=parseaddr(email_message.get('From', ''))[0] or from_address,
                metadata={'date': date}
            )
            
            # Get or create email thread
            email_thread = self.get_or_create_thread(conversation, subject, in_reply_to, references)
            
            # Create email message
            email_msg = EmailMessage.objects.create(
                message=message,
                email_account=self.account,
                imap_uid=imap_uid,
                subject=subject,
                html_body=html_body,
                plain_body=plain_body,
                email_message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                thread=email_thread,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                bcc_addresses=bcc_addresses,
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

        from clients.models import Client

        clients = Client.objects.filter(email__iexact=email_address)

        if clients.exists():
            client = clients.first()

            if clients.count() > 1:
                logger.warning(
                    f"Multiple clients found for {email_address}"
                )
        else:
            client = Client.objects.create(
                email=email_address,
                name=email_address.split("@")[0]
            )

        contact, _ = Contact.objects.get_or_create(
            client=client,
            defaults={
                "preferred_channel": "email"
            }
        )

        return contact
    def _conversation_from_message_id(self, message_id):
        """Busca conversación por Message-ID (In-Reply-To / References)."""
        mid = clean_message_id(message_id)
        if not mid:
            return None
        for lookup in (mid, f'<{mid}>'):
            email_msg = EmailMessage.objects.filter(
                email_message_id=lookup
            ).select_related('message__conversation').first()
            if email_msg:
                return email_msg.message.conversation
        return None

    def _find_open_conversation_by_contact_and_subject(self, contact, subject):
        """Mismo contacto + mismo asunto normalizado en conversación abierta."""
        norm = normalize_email_subject(subject)
        if not norm:
            return None

        open_convos = Conversation.objects.filter(
            contact=contact,
            channel='email',
            status__in=_OPEN_CONVERSATION_STATUSES,
        ).order_by('-updated_at')

        for conv in open_convos:
            if subjects_match(conv.subject, subject):
                return conv

        email_msgs = EmailMessage.objects.filter(
            message__conversation__contact=contact,
            message__conversation__channel='email',
            message__conversation__status__in=_OPEN_CONVERSATION_STATUSES,
        ).select_related('message__conversation').order_by('-message__created_at')

        seen = set()
        for em in email_msgs:
            conv = em.message.conversation
            if conv.id in seen:
                continue
            if subjects_match(em.subject, subject):
                seen.add(conv.id)
                return conv
        return None

    def get_or_create_conversation(self, contact, subject, in_reply_to, references):
        # 1) Hilo RFC: In-Reply-To
        if in_reply_to:
            conv = self._conversation_from_message_id(in_reply_to)
            if conv:
                return conv

        # 2) Hilo RFC: References (cualquier id de la cadena)
        if references:
            for ref in references.split():
                conv = self._conversation_from_message_id(ref)
                if conv:
                    return conv

        # 3) Mismo contacto + mismo asunto (normalizado), conversación abierta
        conv = self._find_open_conversation_by_contact_and_subject(contact, subject)
        if conv:
            return conv

        # 4) Nuevo hilo / conversación
        display_subject = decode_mime_header(subject or '') or '(Sin asunto)'
        conversation = Conversation.objects.create(
            contact=contact,
            channel='email',
            status='normal',
            priority='normal',
            subject=display_subject[:255],
        )

        from .assignment_system import assign_conversation_to_agent
        assign_conversation_to_agent(conversation)

        return conversation

    def get_or_create_thread(self, conversation, subject, in_reply_to, references):
        """Hilo dentro de la conversación (EmailThread)."""
        reply_mid = clean_message_id(in_reply_to)
        if reply_mid:
            for lookup in (reply_mid, f'<{reply_mid}>'):
                existing_thread = EmailThread.objects.filter(
                    conversation=conversation,
                    messages__email_message_id=lookup,
                ).first()
                if existing_thread:
                    existing_thread.last_message_at = timezone.now()
                    existing_thread.save(update_fields=['last_message_at'])
                    return existing_thread

        norm = normalize_email_subject(subject)
        if norm:
            for thread in EmailThread.objects.filter(conversation=conversation):
                if subjects_match(thread.subject, subject):
                    thread.last_message_at = timezone.now()
                    thread.save(update_fields=['last_message_at'])
                    return thread

        display_subject = decode_mime_header(subject or '') or '(Sin asunto)'
        return EmailThread.objects.create(
            subject=display_subject[:500],
            conversation=conversation,
            first_message_at=timezone.now(),
            last_message_at=timezone.now(),
            participants=[],
        )
    
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
               bcc_addresses=None, attachments=None, conversation=None, signature=None, email_msg=None):

        if not self.connect_smtp():
            return False, (self.last_smtp_error or "Failed to connect to SMTP server")

        try:
            # =========================
            # CREAR MENSAJE
            # =========================
            msg = MIMEMultipart('mixed')
            msg['From'] = formataddr((self.account.name, self.account.email_address))
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = subject

            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)

            if bcc_addresses:
                msg['Bcc'] = ', '.join(bcc_addresses)

            msg_id = make_msgid()
            msg['Message-ID'] = msg_id

            # =========================
            # FIRMA
            # =========================
            if signature:
                if html_body:
                    html_body += f"<br><br>{signature.html_signature}"
                if body:
                    body += f"\n\n{signature.plain_signature}"

            # =========================
            # BODY CORRECTO (IMPORTANTE)
            # =========================
            alternative_part = MIMEMultipart('alternative')

            if body:
                alternative_part.attach(MIMEText(body, 'plain'))

            if html_body:
                alternative_part.attach(MIMEText(html_body, 'html'))

            msg.attach(alternative_part)

            # =========================
            # ATTACHMENTS (FIX)
            # =========================
            if attachments:
                for attachment in attachments:
                    if hasattr(attachment, 'read'):
                        filename = attachment.name
                        data = attachment.read()
                        attachment.seek(0)
                        content_type = getattr(attachment, 'content_type', None)
                    else:
                        filename = getattr(attachment, 'filename', 'attachment')
                        data = attachment.file.read()
                        attachment.file.seek(0)
                        content_type = getattr(attachment, 'mime_type', 'application/octet-stream')

                    mime_type, _ = mimetypes.guess_type(filename)
                    if not mime_type:
                        mime_type = content_type or 'application/octet-stream'
                    
                    try:
                        main_type, sub_type = mime_type.split('/', 1)
                    except ValueError:
                        main_type, sub_type = 'application', 'octet-stream'

                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(data)
                    encoders.encode_base64(part)

                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )

                    msg.attach(part)

            # =========================
            # ENVIAR
            # =========================
            to_addrs = []
            if to_addresses:
                to_addrs.extend([x for x in to_addresses if x])
            if cc_addresses:
                to_addrs.extend([x for x in cc_addresses if x])
            if bcc_addresses:
                to_addrs.extend([x for x in bcc_addresses if x])
            self.smtp_connection.send_message(msg, to_addrs=to_addrs or None)
           
            # =========================
            # GUARDAR EN DB
            # =========================
            content = body or html_body

            if not content and attachments:
                content = f"📎 {len(attachments)} archivo(s) adjunto(s)"

            if not content:
                content = '(Empty message)'

            if conversation and not email_msg:
                message = Message.objects.create(
                    conversation=conversation,
                    message_type='email',
                    direction='outbound',
                    content = content,
                    sender_name=self.account.name,
                    metadata={'message_id': msg_id}
                )

                email_msg = EmailMessage.objects.create(
                    message=message,
                    email_account=self.account,
                    subject=subject,
                    html_body=html_body,
                    plain_body=body,
                    email_message_id=msg_id,
                    to_addresses=to_addresses,
                    cc_addresses=cc_addresses or [],
                    bcc_addresses=bcc_addresses or [],
                    from_address=self.account.email_address
                )

                if attachments:
                   

                    for attachment in attachments:
                        try:
                            if hasattr(attachment, 'read'):
                                file_data = attachment.read()
                                attachment.seek(0)

                                att = EmailAttachment.objects.create(
                                    email_message=email_msg,
                                    filename=attachment.name,
                                    mime_type=getattr(attachment, 'content_type', 'application/octet-stream'),
                                    size=attachment.size,
                                )

                                att.file.save(attachment.name, ContentFile(file_data), save=True)

                        except Exception as e:
                            logger.warning(f"No se pudo guardar attachment: {str(e)}")

            elif email_msg:
                # Actualizar el Message ID del mensaje pre-existente
                email_msg.email_message_id = msg_id
                email_msg.save()
                if email_msg.message:
                    email_msg.message.metadata['message_id'] = msg_id
                    email_msg.message.save()

            return True, "Email sent successfully"
        
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False, str(e)

        finally:
            self.disconnect()
