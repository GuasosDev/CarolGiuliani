import re
from bs4 import BeautifulSoup

def procesar_contenido_mensaje(content: str):
    """
    Detecta si el contenido es HTML completo y decide cómo renderizarlo.
    
    Retorna:
    {
        "tipo": "text" | "html_clean" | "iframe",
        "contenido": str
    }
    """

    if not content:
        return {"tipo": "text", "contenido": ""}

    content_lower = content.lower()

    # 🔍 Detectar HTML completo
    es_html_completo = bool(
        re.search(r'<!doctype html>|<html|<head|<body', content_lower)
    )

    if not es_html_completo:
        return {
            "tipo": "text",
            "contenido": content
        }

    # 🧹 Intentar limpiar HTML
    try:
        soup = BeautifulSoup(content, "html.parser")

        if soup.body:
            body_content = soup.body.decode_contents()

            # 🔍 detectar si es muy complejo (mucho CSS, scripts, etc)
            tiene_estilos = bool(soup.find("style"))
            tiene_scripts = bool(soup.find("script"))

            if tiene_estilos or tiene_scripts:
                return {
                    "tipo": "iframe",
                    "contenido": content
                }

            return {
                "tipo": "html_clean",
                "contenido": body_content
            }

    except Exception:
        pass

    # fallback seguro
    return {
        "tipo": "iframe",
        "contenido": content
    }