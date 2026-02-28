import discord
from discord import app_commands
import asyncpg
import os
from src.start import ProfileModal, StartView

class UpdateView(StartView):
    """Versión de StartView para update, con botón para modal"""

    @discord.ui.button(label="Actualizar Nombre y Descripción", style=discord.ButtonStyle.green)
    async def update_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Abrir modal con valores actuales
        modal = ProfileModal(
            interests=self.interests,
            lines=self.lines,
            default_name=getattr(self, "default_name", ""),
            default_description=getattr(self, "default_description", "")
        )
        await interaction.response.send_modal(modal)


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

    # Crear view pre-llenada con intereses y líneas actuales
    view = UpdateView(default_interests=row["interests"], default_lines=row["lines"])
    view.default_name = row["name"]
    view.default_description = row["description"]

    embed = discord.Embed(
        title="💘 Actualiza tu perfil Tinder Discord",
        description="Modifica tus preferencias y pulsa **Actualizar Nombre y Descripción** si quieres cambiar texto.",
        color=discord.Color.pink()
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


update = app_commands.Command(
    name="update",
    description="Actualiza tu perfil existente (nombre, descripción, intereses, líneas)",
    callback=update_callback
)