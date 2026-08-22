"""Decodificación de cabeceras MIME (asunto, nombre de remitente, etc.)."""
from email.header import decode_header, make_header


def decode_mime_header(value):
    if not value or not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    try:
        decoded = str(make_header(decode_header(raw))).strip()
    except Exception:
        decoded = raw
    if "=? " in decoded or decoded.startswith("=?"):
        try:
            parts = []
            for text, charset in decode_header(raw):
                if isinstance(text, bytes):
                    parts.append(text.decode(charset or "utf-8", errors="replace"))
                else:
                    parts.append(str(text))
            joined = "".join(parts).strip()
            if joined:
                decoded = joined
        except Exception:
            pass
    return decoded
