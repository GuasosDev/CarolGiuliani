"""Decodificación de cabeceras MIME (asunto, etc.)."""
from email.header import decode_header, make_header


def decode_mime_header(value):
    if not value or not isinstance(value, str):
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()
