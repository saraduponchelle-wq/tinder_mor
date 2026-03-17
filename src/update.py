import discord
from discord import app_commands
import asyncpg
import os

from src.start import ProfileModal, StartView
from test import test  # 🔥 usamos tu generador

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_NO = str(os.getenv("NO"))


# ==========================================================
# MODAL IMÁGENES
# ==========================================================

class ImageModal(discord.ui.Modal, title="Actualizar imágenes"):

    profile_image = discord.ui.TextInput(
        label="Imagen de perfil (URL)",
        required=False
    )

    banner_image = discord.ui.TextInput(
        label="Banner (URL)",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT profile_image, banner_image FROM profiles WHERE user_id=$1",
            interaction.user.id
        )

        new_profile = self.profile_image.value.strip() or row["profile_image"]
        new_banner = self.banner_image.value.strip() or row["banner_image"]

        await conn.execute(
            """
            UPDATE profiles
            SET profile_image = $1,
                banner_image = $2
            WHERE user_id = $3
            """,
            new_profile,
            new_banner,
            interaction.user.id
        )

        await conn.close()

        await interaction.response.send_message(
            "✅ Imágenes actualizadas.",
            ephemeral=True
        )


# ==========================================================
# SELECTOR DE MARCOS
# ==========================================================

class FrameSelect(discord.ui.Select):

    def __init__(self, frames: list[str]):

        options = [
            discord.SelectOption(label=frame, value=frame)
            for frame in frames
        ]

        super().__init__(
            placeholder="Selecciona un marco",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        selected_frame = self.values[0]

        await interaction.response.send_message(
            f"⏳ Aplicando marco `{selected_frame}`...",
            ephemeral=True
        )

        # 🔥 generar imagen con marco
        url = await test(interaction.client, interaction.user)

        # 🔥 guardar en DB
        conn = await asyncpg.connect(DATABASE_URL)

        await conn.execute(
            """
            UPDATE profiles
            SET framed_profile_image = $1
            WHERE user_id = $2
            """,
            url,
            interaction.user.id
        )

        await conn.close()

        await interaction.followup.send(
            f"✅ Marco aplicado correctamente:\n{url}",
            ephemeral=True
        )


# ==========================================================
# VIEW PRINCIPAL
# ==========================================================

class UpdateView(StartView):

    def __init__(self, *args, frames=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.frames = frames or []

        # 🔥 añadir selector si tiene marcos
        if self.frames:
            self.add_item(FrameSelect(self.frames))

    @discord.ui.button(
        label="Actualizar Nombre y Descripción",
        style=discord.ButtonStyle.green
    )
    async def update_modal(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = ProfileModal(
            interests=self.interests,
            lines=self.lines,
            default_name=getattr(self, "default_name", ""),
            default_description=getattr(self, "default_description", "")
        )

        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Actualizar Imágenes",
        style=discord.ButtonStyle.blurple
    )
    async def update_images(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(ImageModal())

    @discord.ui.button(
        label="🎨 Cambiar Marco",
        style=discord.ButtonStyle.secondary
    )
    async def change_frame(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.frames:
            await interaction.response.send_message(
                "❌ No tienes marcos desbloqueados.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Selecciona un marco del menú desplegable 👇",
            view=self,
            ephemeral=True
        )


# ==========================================================
# COMANDO
# ==========================================================

async def update_callback(interaction: discord.Interaction):

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id = $1",
        interaction.user.id
    )

    await conn.close()

    if not row:
        await interaction.response.send_message(
            f"{EMOJI_NO} No tienes perfil. Usa `/start`.",
            ephemeral=True
        )
        return

    frames = row.get("frames") or []

    view = UpdateView(
        default_interests=row["interests"],
        default_lines=row["lines"],
        frames=frames
    )

    view.default_name = row["name"]
    view.default_description = row["description"]

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Actualiza tu perfil",
        description="Puedes modificar tu perfil, imágenes o marcos.",
        color=discord.Color.pink()
    )

    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )


update = app_commands.Command(
    name="update",
    description="Actualiza tu perfil existente",
    callback=update_callback
)