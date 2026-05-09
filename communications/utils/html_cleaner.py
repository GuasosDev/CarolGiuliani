import re
import bleach
from bs4 import BeautifulSoup, Comment

ALLOWED_TAGS = [
    'b', 'strong',
    'i', 'em',
    'u',
    'p',
    'br',
    'ul', 'ol', 'li',
    'a',
    'blockquote',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
}

def limpiar_email_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Eliminar comentarios
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Eliminar tags peligrosos
    for tag in soup(['script', 'style', 'head', 'meta']):
        tag.decompose()

    # Configurar links
    for a in soup.find_all("a"):
        href = a.get("href")

        if href:
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

    # Obtener HTML limpio
    content = str(soup)

    # Sanitizar
    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True
    )

    # Opcional: limpiar espacios excesivos
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)

    return cleaned.strip()