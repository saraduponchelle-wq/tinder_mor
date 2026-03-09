import discord
from discord import app_commands
import asyncpg
import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_INTEREST = str(os.getenv("INTEREST"))
EMOJI_LINES = str(os.getenv("LINES"))
EMOJI_STAR = str(os.getenv("STAR"))
EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))
EMOJI_FIRE = str(os.getenv("FIRE"))


async def show_callback(interaction: discord.Interaction, user: Optional[discord.Member] = None):

    target = user or interaction.user

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id = $1",
        target.id
    )

    await conn.close()

    if not row:
        await interaction.response.send_message(
            f"{EMOJI_BROKENHEART} No se encontró un perfil para este usuario.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Perfil de Tinder",
        color=discord.Color.pink()
    )

    embed.add_field(
        name=f"{EMOJI_FIRE} Nombre",
        value=row["name"],
        inline=False
    )

    embed.add_field(
        name=f"{EMOJI_INTEREST} Intereses",
        value=", ".join(row["interests"]),
        inline=False
    )

    embed.add_field(
        name=f"{EMOJI_LINES} Líneas",
        value=row["lines"],
        inline=False
    )

    embed.add_field(
        name=f"{EMOJI_STAR} Bio",
        value=row["description"],
        inline=False
    )

    profile_image = row.get("profile_image")
    banner_image = row.get("banner_image")

    # Avatar
    if profile_image:
        embed.set_thumbnail(url=profile_image)
    else:
        embed.set_thumbnail(url=target.display_avatar.url)

    # Banner
    if banner_image:
        embed.set_image(url=banner_image)

    await interaction.response.send_message(embed=embed)


show = app_commands.Command(
    name="show",
    description="Muestra el perfil de un usuario",
    callback=show_callback
)