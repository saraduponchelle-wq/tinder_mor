import discord

EMOJI_NO = __import__("os").getenv("NO")


def is_nsfw_channel(channel) -> bool:
    """Devuelve True si el canal es marcado como NSFW en Discord."""
    if isinstance(channel, discord.DMChannel):
        return False
    return getattr(channel, "nsfw", False)


async def check_nsfw(interaction: discord.Interaction) -> bool:
    """
    Verifica que el comando se use en un canal +18.
    Si no lo es, envía un mensaje de error ephemeral y retorna False.
    Usar al inicio de cada callback:

        if not await check_nsfw(interaction):
            return
    """
    if not is_nsfw_channel(interaction.channel):
        await interaction.response.send_message(
            f"{EMOJI_NO} Este comando solo puede usarse en canales **+18** (NSFW).\n"
            "Pide a un administrador que marque el canal como NSFW.",
            ephemeral=True
        )
        return False
    return True
