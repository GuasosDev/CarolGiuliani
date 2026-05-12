import re
import bleach
from bs4 import BeautifulSoup, Comment
from html import unescape
ALLOWED_TAGS = [
    # estructura
    'html', 'body',
    'div', 'span',
    'p', 'br', 'hr',

    # formato
    'b', 'strong',
    'i', 'em',
    'u',

    # listas
    'ul', 'ol', 'li',

    # links
    'a',

    # tablas (emails usan esto)
    'table', 'thead', 'tbody', 'tfoot',
    'tr', 'td', 'th',

    # imágenes
    'img',

    # citas
    'blockquote',
]

ALLOWED_ATTRIBUTES = {
    '*': [
        'style',
        'class',
        'align',
    ],

    'a': [
        'href',
        'title',
        'target',
        'rel',
    ],

    'img': [
        'src',
        'alt',
        'width',
        'height',
        'style',
    ],

    'table': [
        'width',
        'border',
        'cellpadding',
        'cellspacing',
        'style',
    ],

    'td': [
        'width',
        'height',
        'colspan',
        'rowspan',
        'style',
        'align',
    ],

    'th': [
        'colspan',
        'rowspan',
        'style',
        'align',
    ],

    'div': ['style'],
    'span': ['style'],
    'p': ['style'],
}

def limpiar_email_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # eliminar comentarios
    for comment in soup.find_all(
        string=lambda text: isinstance(text, Comment)
    ):
        comment.extract()

    # eliminar contenido peligroso
    for tag in soup([
        'script',
        'iframe',
        'object',
        'embed',
        'form',
        'input',
        'button',
    ]):
        tag.decompose()

    # asegurar links seguros
    for a in soup.find_all("a"):
        href = a.get("href")

        if href:
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

        # convertir a string
    content = unescape(str(soup))

    # sanitizar
    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=['http', 'https', 'mailto', 'data'],
        strip=True
    )

    # convertir URLs texto en links
    cleaned = bleach.linkify(
        cleaned,
        skip_tags=['a']
    )

    return cleaned.strip()
        
        