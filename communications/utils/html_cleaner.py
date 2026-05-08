import bleach
from bs4 import BeautifulSoup

ALLOWED_TAGS = [
    'b', 'strong',
    'i', 'em',
    'u',
    'p',
    'br',
    'ul', 'ol', 'li',
    'a',
    'blockquote'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
}

def limpiar_email_html(html):
    """
    Limpia HTML de emails/copiados desde Gmail/ChatGPT/etc.
    """

    if not html:
        return ""

    # Parsear HTML
    soup = BeautifulSoup(html, "html.parser")

    # ❌ eliminar scripts/styles
    for tag in soup(['script', 'style', 'head', 'meta']):
        tag.decompose()

    # ✅ obtener body si existe
    content = soup.body.decode_contents() if soup.body else str(soup)

    # ✅ limpiar atributos basura
    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

    return cleaned