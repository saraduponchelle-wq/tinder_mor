"""
src/image_validator.py
Validación de URLs de imagen para formularios del bot.
"""

import re

# Dominios de CDN de Discord aceptados
DISCORD_DOMAINS = (
    "cdn.discordapp.com",
    "media.discordapp.net",
    "images-ext-1.discordapp.net",
    "images-ext-2.discordapp.net",
    "attachments.discordapp.net",
)

# Extensiones de imagen válidas
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def is_valid_image_url(url: str) -> tuple[bool, str]:
    """
    Comprueba si la URL es un enlace válido de imagen o GIF de Discord.

    Devuelve (True, "") si es válida,
    o (False, "mensaje de error") si no lo es.
    """

    url = url.strip()

    if not url:
        return False, "❌ El campo está vacío."

    # Debe empezar por https://
    if not url.startswith("https://"):
        return False, (
            "❌ La URL debe empezar por `https://`.\n"
            "Copia el enlace directamente desde Discord."
        )

    # Debe ser de un dominio de Discord
    is_discord = any(domain in url for domain in DISCORD_DOMAINS)
    if not is_discord:
        return False, (
            "❌ Solo se aceptan imágenes **de Discord**.\n"
            "Sube la imagen a cualquier canal y copia el enlace con "
            "*clic derecho → Copiar enlace de medios*."
        )

    # Debe terminar en una extensión de imagen válida (ignorando query params)
    path = url.split("?")[0].lower()
    if not any(path.endswith(ext) for ext in VALID_EXTENSIONS):
        return False, (
            "❌ El enlace no apunta a una imagen válida.\n"
            f"Extensiones aceptadas: `{', '.join(VALID_EXTENSIONS)}`\n"
            "Asegúrate de copiar el **enlace directo** al archivo, no la página."
        )

    return True, ""
