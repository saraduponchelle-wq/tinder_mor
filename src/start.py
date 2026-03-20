import discord
from discord import app_commands
import asyncpg
import os

from embed.create_profile import create_profile_embed
from test import test  # ✅ usamos tu generador real

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_NO = str(os.getenv("NO"))
EMOJI_INTEREST = str(os.getenv("INTEREST"))
EMOJI_LINES = str(os.getenv("LINES"))
EMOJI_STAR = str(os.getenv("STAR"))
EMOJI_FIRE = str(os.getenv("FIRE"))


# ========================
# SELECT: Intereses
# ========================
class InterestSelect(discord.ui.Select):
    def __init__(self, default_values=None):
        options = [
            discord.SelectOption(label="Mujeres"),
            discord.SelectOption(label="Hombres"),
            discord.SelectOption(label="Femboys"),
            discord.SelectOption(label="Futas"),
        ]
        super().__init__(placeholder="¿Qué te interesa?", min_values=1, max_values=4, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.interests = self.values
        await interaction.response.defer()


# ========================
# SELECT: Lineas
# ========================
class LinesSelect(discord.ui.Select):
    def __init__(self, default_values=None):
        options = [
            discord.SelectOption(label="Lemon"),
            discord.SelectOption(label="Romance"),
            discord.SelectOption(label="BL"),
            discord.SelectOption(label="GL"),
            discord.SelectOption(label="Fantasia"),
            discord.SelectOption(label="Aventura"),
            discord.SelectOption(label="Battle"),
        ]

        super().__init__(
            placeholder="¿Tipo de Rol?",
            min_values=1,
            max_values=7,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.lines = self.values
        await interaction.response.defer()


# ========================
# MODAL
# ========================
class ProfileModal(discord.ui.Modal, title="Crea tu perfil"):

        def __init__(self, interests, lines, default_name="", default_description=""):
            super().__init__()

            self.interests = interests
            self.lines = lines

            self.name = discord.ui.TextInput(
                label="Nombre",
                max_length=50,
                default=default_name  # ✅ añadido
            )

            self.description = discord.ui.TextInput(
                label="Descripción",
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=default_description  # ✅ añadido
            )

            self.add_item(self.name)
            self.add_item(self.description)

        async def on_submit(self, interaction: discord.Interaction):

            await interaction.response.send_message("⏳ Creando perfil...", ephemeral=True)

            conn = await asyncpg.connect(DATABASE_URL)

            # eliminar perfil anterior (embed viejo)
            row = await conn.fetchrow(
                "SELECT message_id FROM profiles WHERE user_id = $1",
                interaction.user.id
            )

            if row and row["message_id"]:
                try:
                    msg = await interaction.channel.fetch_message(row["message_id"])
                    await msg.delete()
                except:
                    pass

            # =========================
            # 🔥 APLICAR MARCO DEFAULT
            # =========================
            framed_url = None

            row_full = await conn.fetchrow(
                "SELECT framed_profile_image FROM profiles WHERE user_id=$1",
                interaction.user.id
            )

            if row_full and row_full["framed_profile_image"]:
                framed_url = row_full["framed_profile_image"]
            else:
                framed_url = await test(interaction.client, interaction.user, "default")

            # =========================
            # GUARDAR EN DB
            # =========================
            await conn.execute("""
                INSERT INTO profiles(user_id, name, interests, lines, description, framed_profile_image)
                VALUES($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id)
                DO UPDATE SET name=$2, interests=$3, lines=$4, description=$5, framed_profile_image=$6
            """,
                interaction.user.id,
                self.name.value,
                self.interests,
                self.lines,
                self.description.value,
                framed_url
            )

            # =========================
            # CREAR EMBED (TU SISTEMA)
            # =========================
            profile_data = {
                "user_id": interaction.user.id,
                "name": self.name.value,
                "interests": self.interests,
                "lines": self.lines,
                "description": self.description.value,
                "framed_profile_image": framed_url
            }

            embed = create_profile_embed(profile_data, interaction.user)

            await interaction.followup.send(embed=embed)
            message = await interaction.original_response()

            await conn.execute(
                "UPDATE profiles SET message_id=$1 WHERE user_id=$2",
                message.id,
                interaction.user.id
            )

            await conn.close()


# ========================
# VIEW
# ========================
class StartView(discord.ui.View):
    def __init__(self, default_interests=None, default_lines=None):
        super().__init__(timeout=180)

        self.interests = default_interests or []
        self.lines = default_lines or []

        self.add_item(InterestSelect(default_values=self.interests))
        self.add_item(LinesSelect(default_values=self.lines))

    @discord.ui.button(label="Crear Perfil", style=discord.ButtonStyle.green)
    async def create_profile(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.interests or not self.lines:
            await interaction.response.send_message(
                f"{EMOJI_NO} Debes seleccionar intereses y líneas primero.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            ProfileModal(self.interests, self.lines)
        )


# ========================
# COMMAND
# ========================
async def start_callback(interaction: discord.Interaction):

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id = $1",
        interaction.user.id
    )

    await conn.close()

    if row:
        await interaction.response.send_message(
            f"{EMOJI_NO} Ya tienes un perfil. Usa `/update`.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Crea tu perfil",
        description="Selecciona intereses y líneas, luego pulsa el botón.",
        color=discord.Color.pink()
    )

    await interaction.response.send_message(
        embed=embed,
        view=StartView(),
        ephemeral=True
    )


start = app_commands.Command(
    name="start",
    description="Crear perfil",
    callback=start_callback
)