import discord
from discord import app_commands
import asyncpg
import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")

async def show_callback(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id = $1", target.id)
    await conn.close()

    if not row:
        await interaction.response.send_message(
            "❌ No se encontró un perfil para este usuario.",
            ephemeral=True
        )
        return

    embed = discord.Embed(title="💘 Perfil de Discord Tinder", color=discord.Color.pink())
    embed.add_field(name="Nombre", value=row["name"], inline=False)
    embed.add_field(name="Que te interesa", value=", ".join(row["interests"]), inline=False)
    embed.add_field(name="Lineas", value=row["lines"], inline=False)
    embed.add_field(name="Descripcion", value=row["description"], inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)

    await interaction.response.send_message(embed=embed)

# Registramos el comando correctamente con type hints
show = app_commands.Command(
    name="show",
    description="Muestra el perfil de un usuario",
    callback=show_callback
)