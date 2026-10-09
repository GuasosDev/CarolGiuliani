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
        'max-height',
        'display',
        'margin',
        'padding',
        'border',
        'border-radius',
        'text-decoration',
        'object-fit',
        'vertical-align',
        'line-height',
    ]
)


ALLOWED_TAGS = [
    # estructura
    'html', 'body',
    'div', 'span',
    'p', 'br', 'hr',

    # formato
    'b', 'strong',
    'i', 'em',
    'u',
    'font',
    'center',
    'small',
    'sub',
    'sup',

    # headings
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',

    # code
    'pre', 'code',

    # listas
    'ul', 'ol', 'li',

    # links
    'a',

    # tablas
    'table', 'thead', 'tbody', 'tfoot',
    'tr', 'td', 'th',

    # media
    'img',
    'video',
    'source',

    # embeds
    'iframe',

    # misc
    'blockquote',
    'cite',
    'details',
    'summary',
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
        'srcset',
        'alt',
        'width',
        'height',
        'style',
        'class',
        'loading',
    ],

    'video': [
        'src',
        'controls',
        'autoplay',
        'muted',
        'loop',
        'poster',
        'style',
        'width',
        'height',
    ],

    'source': [
        'src',
        'type',
    ],

    'iframe': [
        'src',
        'width',
        'height',
        'allowfullscreen',
        'frameborder',
        'style',
        'loading',
        'referrerpolicy',
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

    'font': [
        'color',
        'face',
        'size',
        'style',
    ],

    'div': ['style'],
    'span': ['style'],
    'p': ['style'],

    'details': ['open', 'class'],
    'summary': ['style'],
}


SOCIAL_DOMAINS = [
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "facebook.com",
    "twitter.com",
    "x.com",
]


def _strip_embedded_webmail_header(soup):

    container = soup.body if soup.body else soup

    if not container:
        return

    pattern_date = re.compile(
        r"\s+el\s+\d{1,2}-\d{1,2}-\d{4}\b",
        re.I
    )

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


def _collapse_quoted_email_history(soup):
    quote_classes = {
        'gmail_quote',
        'gmail_quote_container',
        'yahoo_quoted',
    }

    def is_quote_container(tag):
        return (
            getattr(tag, 'name', None) in {'div', 'blockquote'}
            and quote_classes.intersection(tag.get('class', []))
        )

    quote_nodes = [
        node for node in soup.find_all(is_quote_container)
        if not any(is_quote_container(parent) for parent in node.parents)
    ]

    for node in quote_nodes:
        details = soup.new_tag('details', attrs={'class': 'email-quoted-history'})
        summary = soup.new_tag('summary')
        summary.string = 'Mostrar mensaje citado'
        details.append(summary)
        node.wrap(details)


def plain_text_to_email_html(text):

    if not text:
        return ""

    from django.utils.html import escape

    t = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    return (
        '<div class="email-plain-body">'
        f'{escape(t).replace(chr(10), "<br>")}'
        '</div>'
    )


def email_html_to_text(html):
    if not html:
        return ""

    soup = BeautifulSoup(str(html), "html.parser")
    quote_classes = {
        'gmail_quote',
        'gmail_quote_container',
        'yahoo_quoted',
    }

    def is_quote_container(tag):
        return (
            getattr(tag, 'name', None) in {'div', 'blockquote'}
            and quote_classes.intersection(tag.get('class', []))
        )

    quote_nodes = [
        node for node in soup.find_all(is_quote_container)
        if not any(is_quote_container(parent) for parent in node.parents)
    ]
    for node in quote_nodes:
        node.decompose()

    return soup.get_text(" ", strip=True)


def limpiar_email_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    _strip_embedded_webmail_header(soup)
    _collapse_quoted_email_history(soup)
     # eliminar css embebido
    for style in soup.find_all("style"):
        style.decompose()
    # eliminar comentarios HTML
    for comment in soup.find_all(
        string=lambda text: isinstance(text, Comment)
    ):
        comment.extract()

    # eliminar scripts peligrosos
    for tag in soup([
        'script',
        'object',
        'embed',
        'form',
        'input',
        'button',
        'select',
        'option',
        'textarea',
        'canvas',
    ]):
        tag.decompose()

    

    # limpiar imágenes
    for img in soup.find_all("img"):
        
        if not hasattr(img, "attrs"):
            continue

        if img.attrs is None:
            continue 
        alt = (img.get("alt") or "").strip().lower()

        # ocultar nombres basura tipo image001.png
        if re.match(
            r"image\d*\.(png|jpg|jpeg|gif|webp)",
            alt
        ):
            img["alt"] = ""

        current_style = img.get("style") or ""

        img["style"] = f"""
            {current_style};
            max-width:100%;
            height:auto;
            object-fit:contain;
            """
        img["loading"] = "lazy"

        src = (img.get("src") or "").lower()
        
        if src.startswith("data:image") and len(src) > 500000:
            img.decompose()
            continue
        # eliminar tracking pixels
        if (
            "tracking" in src
            or "pixel" in src
            or "openrate" in src
        ):
            img.decompose()
            continue

    # links seguros
    for a in soup.find_all("a"):

        href = a.get("href") or ""

        if href:

            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

            current_style = a.get("style") or ""

            # conservar links visibles
            a["style"] = (
                current_style
                + ";word-break:break-word;"
            )

   # iframes seguros
    for iframe in soup.find_all("iframe"):

        src = (iframe.get("src") or "").lower()

        allowed = any(domain in src for domain in [
            "youtube.com",
            "youtu.be",
            "vimeo.com",
        ])

        if not allowed:
            iframe.decompose()
            continue

        iframe["style"] = """
            max-width:100%;
            border:none;
        """

        iframe["loading"] = "lazy"
        iframe["referrerpolicy"] = "no-referrer"


    content = unescape(str(soup))

    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=[
            'http',
            'https',
            'mailto',
            'data',
            'cid',
        ],
        strip=True,
        css_sanitizer=css_sanitizer
    )

    return cleaned.strip()