import re
import bleach
from bs4 import BeautifulSoup, Comment
from html import unescape
from bleach.css_sanitizer import CSSSanitizer

css_sanitizer = CSSSanitizer(
    allowed_css_properties=[
        'color',
        'background-color',
        'font-size',
        'font-family',
        'font-weight',
        'text-align',
        'width',
        'height',
        'max-width',
        'min-width',
        'display',
        'margin',
        'padding',
        'border',
        'border-radius',
        'text-decoration',
        # agregar
        'max-height',
        'object-fit',
        'vertical-align',
    ]
)
ALLOWED_TAGS = [
    # estructura
    'html', 'body', 'style',
    'div', 'span',
    'p', 'br', 'hr',

    # formato
    'b', 'strong',
    'i', 'em',
    'u',
    'font',
    'center',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'pre', 'code',
    'small', 'sub', 'sup',

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
    'cite',

    'details',
    'summary',
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
    'srcset',
    'alt',
    'width',
    'height',
    'style',
    'class',
    'loading',
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

    'h1': ['style', 'class'],
    'h2': ['style', 'class'],
    'h3': ['style', 'class'],
    'h4': ['style', 'class'],
    'h5': ['style', 'class'],
    'h6': ['style', 'class'],
    'pre': ['style', 'class'],
    'code': ['style', 'class'],
    'font': ['color', 'face', 'size', 'style'],

    'div': ['style'],
    'span': ['style'],
    'p': ['style'],
    'details': ['open'],
    'summary': ['style'],
}


def plain_text_to_email_html(text):
    """Convierte cuerpo solo texto a HTML seguro para mostrar en el visor."""
    if not text:
        return ""
    from django.utils.html import escape

    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return f'<div class="email-plain-body">{escape(t).replace(chr(10), "<br>")}</div>'


def limpiar_email_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Quitar bloque UI incrustado
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
        'select',
        'option',
        'textarea',
        'nav',
        'svg',
        'canvas',
        'video',
        'audio',
    ]):
        tag.decompose()

    # limpiar imágenes problemáticas
    for img in soup.find_all("img"):

        alt = img.get("alt", "").strip().lower()

        # evitar mostrar "image.png"
        if re.match(r"image\d*\.(png|jpg|jpeg|gif|webp)", alt):
            img["alt"] = ""

        # quitar tamaños fijos
        img.attrs.pop("width", None)
        img.attrs.pop("height", None)

        current_style = img.get("style", "")

        safe_style = """
        max-width:100%;
        height:auto;
        object-fit:contain;
        vertical-align:middle;
        """

        img["style"] = f"{current_style};{safe_style}"

        src = img.get("src", "")

        # eliminar tracking pixels
        if "tracking" in src or "pixel" in src:
            img.decompose()

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
        protocols=['http', 'https', 'mailto', 'data', 'cid'],
        strip=True,
        css_sanitizer=css_sanitizer
    )

    return cleaned.strip()
        
        