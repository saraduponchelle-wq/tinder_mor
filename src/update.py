import discord
from discord import app_commands
import asyncpg
import os
from src.start import ProfileModal, StartView

async def update_callback(interaction: discord.Interaction):
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id = $1", interaction.user.id)
    await conn.close()

    if not row:
        await interaction.response.send_message(
            "❌ No tienes un perfil creado. Usa `/start` para crearlo.",
            ephemeral=True
        )
        return

    # Abrimos modal con valores pre-llenados
    modal = ProfileModal(
        interests=row["interests"],      # TEXT[]
        lines=row["lines"],
        default_name=row["name"],
        default_description=row["description"]
    )

    await interaction.response.send_modal(modal)


update = app_commands.Command(
    name="update",
    description="Actualiza tu perfil existente",
    callback=update_callback
)