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
    'div',
    'span'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
}

def limpiar_email_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Eliminar comentarios HTML raros de Google
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Eliminar tags innecesarios/peligrosos
    for tag in soup(['script', 'style', 'head', 'meta']):
        tag.decompose()

    # Convertir DIV en bloques separados
    for div in soup.find_all("div"):
        div.append("\n\n")

    # Saltos visibles
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Separación entre párrafos
    for p in soup.find_all("p"):
        p.append("\n\n")

    # Mejorar listas
    for li in soup.find_all("li"):
        li.insert_before("• ")
        li.append("\n")

    # Mantener links clickeables
    for a in soup.find_all("a"):
        href = a.get("href")

        if href:
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

    content = soup.body.decode_contents() if soup.body else str(soup)

    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True
    )

    # Limpiar espacios y saltos excesivos
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
    cleaned = cleaned.strip()

    return cleaned