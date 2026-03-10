import discord
from discord import app_commands
import asyncpg
import os
from src.start import ProfileModal, StartView

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_NO = str(os.getenv("NO"))


class ImageModal(discord.ui.Modal, title="Actualizar imágenes"):

    profile_image = discord.ui.TextInput(
        label="Imagen de perfil (URL)",
        placeholder="https://cdn.discordapp.com/...",
        required=False
    )

    banner_image = discord.ui.TextInput(
        label="Banner (URL)",
        placeholder="https://cdn.discordapp.com/...",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT profile_image, banner_image FROM profiles WHERE user_id=$1",
            interaction.user.id
        )

        current_profile = row["profile_image"]
        current_banner = row["banner_image"]

        new_profile = self.profile_image.value.strip()
        new_banner = self.banner_image.value.strip()

        # Si el campo está vacío, mantener el anterior
        if not new_profile:
            new_profile = current_profile

        if not new_banner:
            new_banner = current_banner

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
            "✅ Imágenes actualizadas correctamente.",
            ephemeral=True
        )


class UpdateView(StartView):

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


async def update_callback(interaction: discord.Interaction):

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id = $1",
        interaction.user.id
    )

    await conn.close()

    if not row:
        await interaction.response.send_message(
            f"{EMOJI_NO} No tienes un perfil creado. Usa `/start` para crearlo.",
            ephemeral=True
        )
        return

    view = UpdateView(
        default_interests=row["interests"],
        default_lines=row["lines"]
    )

    view.default_name = row["name"]
    view.default_description = row["description"]

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Actualiza tu perfil Tinder Discord",
        description="Puedes modificar tu perfil o tus imágenes.",
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