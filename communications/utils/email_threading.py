"""Agrupación de hilos de correo por cabeceras RFC y asunto normalizado."""
import re

from .email_headers import decode_mime_header

# Prefijos habituales en respuestas / reenvíos (es, en, etc.)
_RE_SUBJECT_PREFIX = re.compile(
    r'^(?:\s*(?:re|fw|fwd|rv|res|aw|antw|tr|transf|reen)\s*:\s*)+',
    re.IGNORECASE,
)

_OPEN_CONVERSATION_STATUSES = ('open', 'pending', 'normal', 'assigned')


def clean_message_id(value):
    """Normaliza Message-ID / In-Reply-To (quita <>, espacios)."""
    if not value:
        return ''
    mid = str(value).strip()
    if mid.startswith('<') and mid.endswith('>'):
        mid = mid[1:-1].strip()
    return mid


def normalize_email_subject(subject):
    """
    Asunto comparable para decidir si dos mails pertenecen al mismo hilo.
    No usar para mostrar en UI (ahí va decode_mime_header).
    """
    text = decode_mime_header(subject or '')
    if not text:
        return ''
    text = text.strip()
    while True:
        stripped = _RE_SUBJECT_PREFIX.sub('', text, count=1).strip()
        if stripped == text:
            break
        text = stripped
    text = re.sub(r'\s+', ' ', text).strip()
    return text.casefold()


def subjects_match(subject_a, subject_b):
    a = normalize_email_subject(subject_a)
    b = normalize_email_subject(subject_b)
    if not a or not b:
        return False
    return a == b
