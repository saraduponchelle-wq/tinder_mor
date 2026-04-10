import discord
from discord import app_commands
import asyncpg
import os

from src.start import ProfileModal, StartView
from src.nsfw_check import check_nsfw
from test import test

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_NO = str(os.getenv("NO"))


# ==========================================================
# MODAL IMÁGENES
# ==========================================================

class ImageModal(discord.ui.Modal, title="Actualizar imágenes"):

    profile_image = discord.ui.TextInput(
        label="Imagen de perfil (URL)",
        placeholder="https://ejemplo.com/foto.png",
        required=False
    )

    banner_image = discord.ui.TextInput(
        label="Banner (URL)",
        placeholder="https://ejemplo.com/banner.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            "⏳ Procesando imágenes...",
            ephemeral=True
        )

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT profile_image, banner_image FROM profiles WHERE user_id=$1",
            interaction.user.id
        )

        new_profile = self.profile_image.value.strip() or row["profile_image"]
        new_banner  = self.banner_image.value.strip()  or row["banner_image"]

        await conn.execute(
            """
            UPDATE profiles
            SET profile_image = $1,
                banner_image  = $2
            WHERE user_id = $3
            """,
            new_profile,
            new_banner,
            interaction.user.id
        )

        await conn.close()

        try:
            url = await test(interaction.client, interaction.user, "default")

            if url and not str(url).startswith("❌"):
                conn2 = await asyncpg.connect(DATABASE_URL)
                await conn2.execute(
                    "UPDATE profiles SET framed_profile_image=$1 WHERE user_id=$2",
                    url,
                    interaction.user.id
                )
                await conn2.close()
            else:
                await interaction.followup.send(
                    url or "❌ Error generando marco.",
                    ephemeral=True
                )
                return

        except Exception as e:
            print(f"⚠️ Error aplicando marco default: {e}")

        await interaction.followup.send(
            "✅ Imágenes actualizadas correctamente.",
            ephemeral=True
        )


# ==========================================================
# SELECTOR DE MARCOS
# ==========================================================

class FrameSelect(discord.ui.Select):

    def __init__(self, frames: list[str]):

        options = [
            discord.SelectOption(
                label="🖼️ Default",
                value="default"
            )
        ]

        options += [
            discord.SelectOption(label=frame, value=frame)
            for frame in frames if frame != "default"
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

        url = await test(interaction.client, interaction.user, selected_frame)

        if not url or str(url).startswith("❌"):
            await interaction.followup.send(
                url or "❌ Error aplicando el marco.",
                ephemeral=True
            )
            return

        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute(
            "UPDATE profiles SET framed_profile_image=$1 WHERE user_id=$2",
            url,
            interaction.user.id
        )
        await conn.close()

        await interaction.followup.send(
            "✅ Marco aplicado correctamente.",
            ephemeral=True
        )


# ==========================================================
# VIEW PRINCIPAL
# ==========================================================

class UpdateView(StartView):

    def __init__(self, *args, frames=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.frames = frames or []

        if self.frames:
            self.add_item(FrameSelect(self.frames))

    @discord.ui.button(
        label="✍️ Nombre y Descripción",
        style=discord.ButtonStyle.green,
        row=2
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
        label="🖼️ Imágenes",
        style=discord.ButtonStyle.blurple,
        row=2
    )
    async def update_images(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(ImageModal())

    @discord.ui.button(
        label="🎨 Cambiar Marco",
        style=discord.ButtonStyle.secondary,
        row=2
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

    # ── Sobreescribir el botón heredado de StartView para que no aparezca ──
    # El botón "Crear Perfil" de StartView no tiene sentido en UpdateView,
    # así que lo redefinimos con el mismo custom_id para que Discord lo ignore.
    @discord.ui.button(label="✍️ Crear Perfil", style=discord.ButtonStyle.green, row=3)
    async def create_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        # En UpdateView este botón no se usa; la lógica está en update_modal
        pass


# ==========================================================
# COMANDO
# ==========================================================

async def update_callback(interaction: discord.Interaction):

    if not await check_nsfw(interaction):
        return

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id=$1",
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

    view.default_name        = row["name"]
    view.default_description = row["description"]

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Actualiza tu perfil",
        description=(
            "Elige qué quieres modificar:\n\n"
            "✍️ **Nombre y Descripción** — cambia tu nombre o bio\n"
            "🖼️ **Imágenes** — actualiza foto de perfil o banner\n"
            "🎨 **Cambiar Marco** — aplica un marco desbloqueado\n\n"
            "Los menús de intereses y tipo de rol también están activos."
        ),
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
