from django import template

from ..utils.email_headers import decode_mime_header

register = template.Library()


@register.filter
def decode_email_subject(value):
    return decode_mime_header(value or "")
