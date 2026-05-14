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

def _strip_embedded_webmail_header(soup):
    """
    Elimina el primer bloque que parece cabecera de visor webmail (no el cuerpo del correo).
    Patrón típico: texto "De … el dd-mm-aaaa" junto con enlaces "Detalles" y "Texto".
    """
    container = soup.body if soup.body else soup
    if not container:
        return
    pattern_date = re.compile(r"\s+el\s+\d{1,2}-\d{1,2}-\d{4}\b", re.I)
    pattern_de = re.compile(r"\bDe\s+\S", re.I)

    def is_chrome_block(node):
        if not hasattr(node, "get_text"):
            return False
        t = node.get_text(" ", strip=True)[:500]
        if not t:
            return False
        return (
            pattern_de.search(t)
            and pattern_date.search(t)
            and "Detalles" in t
            and "Texto" in t
        )

    for child in list(container.children):
        if is_chrome_block(child):
            child.decompose()
            return

    first_div = container.find("div", recursive=False)
    if first_div:
        for sub in list(first_div.children):
            if is_chrome_block(sub):
                sub.decompose()
                return


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

    # Quitar bloque UI incrustado de algunos webmails (ej. "De X el dd-mm-aaaa" + Detalles/Texto)
    _strip_embedded_webmail_header(soup)

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
        
        