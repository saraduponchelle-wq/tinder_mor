import discord
from discord import app_commands
import asyncpg
import os

from embed.create_profile import create_profile_embed
from test import test
from src.report import is_banned

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
            discord.SelectOption(label="Mujeres",  emoji="👩"),
            discord.SelectOption(label="Hombres",  emoji="👨"),
            discord.SelectOption(label="Femboys",  emoji="🌸"),
            discord.SelectOption(label="Futas",    emoji="💜"),
        ]

        super().__init__(
            placeholder="❤️ ¿Qué te interesa?",
            min_values=1,
            max_values=4,
            options=options
        )

        if default_values:
            for option in self.options:
                if option.label in default_values:
                    option.default = True

    async def callback(self, interaction: discord.Interaction):
        self.view.interests = self.values
        self.view.step_done.add("interests")
        await interaction.response.edit_message(
            embed=self.view.build_embed(),
            view=self.view
        )


# ========================
# SELECT: Lineas
# ========================
class LinesSelect(discord.ui.Select):
    def __init__(self, default_values=None):
        options = [
            discord.SelectOption(label="Lemon",    emoji="🍋"),
            discord.SelectOption(label="Romance",  emoji="💖"),
            discord.SelectOption(label="BL",       emoji="💙"),
            discord.SelectOption(label="GL",       emoji="💗"),
            discord.SelectOption(label="Fantasia", emoji="🧝"),
            discord.SelectOption(label="Aventura", emoji="⚔️"),
            discord.SelectOption(label="Battle",   emoji="🔥"),
        ]

        super().__init__(
            placeholder="🎭 ¿Tipo de Rol?",
            min_values=1,
            max_values=7,
            options=options
        )

        if default_values:
            for option in self.options:
                if option.label in default_values:
                    option.default = True

    async def callback(self, interaction: discord.Interaction):
        self.view.lines = self.values
        self.view.step_done.add("lines")
        await interaction.response.edit_message(
            embed=self.view.build_embed(),
            view=self.view
        )


# ========================
# MODAL
# ========================
class ProfileModal(discord.ui.Modal, title="✨ Cuéntanos sobre ti"):

    def __init__(self, interests, lines, default_name="", default_description=""):
        super().__init__()

        self.interests = interests
        self.lines = lines

        self.name = discord.ui.TextInput(
            label="¿Cómo quieres que te llamen?",
            placeholder="Tu nombre o apodo en el servidor...",
            max_length=50,
            default=default_name
        )

        self.description = discord.ui.TextInput(
            label="Descripción (cuéntate un poco)",
            style=discord.TextStyle.paragraph,
            placeholder="¿Quién eres? ¿Qué buscas? ¿Algo especial sobre ti? 💬",
            max_length=500,
            default=default_description
        )

        self.add_item(self.name)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            "⏳ Creando tu perfil, un momento...",
            ephemeral=True
        )

        conn = await asyncpg.connect(DATABASE_URL)

        # ── Comprobar si ya existe un perfil ──────────────────────
        existing = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id=$1",
            interaction.user.id
        )

        # Eliminar embed anterior si existe
        if existing and existing.get("message_id"):
            try:
                msg = await interaction.channel.fetch_message(existing["message_id"])
                await msg.delete()
            except Exception:
                pass

        # ── Guardar datos de texto ─────────────────────────────────
        await conn.execute("""
            INSERT INTO profiles(user_id, name, interests, lines, description)
            VALUES($1, $2, $3, $4, $5)
            ON CONFLICT (user_id)
            DO UPDATE SET name=$2, interests=$3, lines=$4, description=$5
        """,
            interaction.user.id,
            self.name.value,
            self.interests,
            self.lines,
            self.description.value
        )

        # ── Marco: solo regenerar si NO tiene uno ya ───────────────
        # Esto evita resetear el marco personalizado al editar texto
        existing_frame = existing["framed_profile_image"] if existing else None

        framed_url = existing_frame  # conservar el que ya tiene

        if not framed_url:
            try:
                framed_url = await test(interaction.client, interaction.user, "default")

                if framed_url and not str(framed_url).startswith("❌"):
                    await conn.execute(
                        "UPDATE profiles SET framed_profile_image=$1 WHERE user_id=$2",
                        framed_url,
                        interaction.user.id
                    )
                else:
                    framed_url = None
            except Exception as e:
                print(f"⚠️ Error aplicando marco: {e}")
                framed_url = None

        # ── Leer perfil completo para el embed (incluye stats) ─────
        full_row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id=$1",
            interaction.user.id
        )

        await conn.close()

        profile_data = dict(full_row)

        embed = create_profile_embed(profile_data, interaction.user)

        await interaction.followup.send(embed=embed)
        message = await interaction.original_response()

        # Guardar message_id del nuevo embed
        conn2 = await asyncpg.connect(DATABASE_URL)
        await conn2.execute(
            "UPDATE profiles SET message_id=$1 WHERE user_id=$2",
            message.id,
            interaction.user.id
        )
        await conn2.close()


# ========================
# VIEW DE CREACIÓN (tutorial paso a paso)
# ========================
class StartView(discord.ui.View):

    def __init__(self, default_interests=None, default_lines=None):
        super().__init__(timeout=300)

        self.interests = default_interests or []
        self.lines     = default_lines or []
        self.step_done: set = set()

        # Pre-marcar pasos si venimos de /update
        if self.interests:
            self.step_done.add("interests")
        if self.lines:
            self.step_done.add("lines")

        self.add_item(InterestSelect(default_values=self.interests))
        self.add_item(LinesSelect(default_values=self.lines))

    # ── Embed dinámico con checklist de pasos ─────────────────────
    def build_embed(self) -> discord.Embed:

        steps = {
            "interests": ("❤️ Intereses",    "interests" in self.step_done),
            "lines":     ("🎭 Tipo de Rol",   "lines"     in self.step_done),
            "profile":   ("✍️ Nombre y Bio",  False),   # se completa en el modal
        }

        lines = []
        for key, (label, done) in steps.items():
            icon = "✅" if done else "⬜"
            lines.append(f"{icon} **{label}**")

        desc = (
            "Completa los **3 pasos** para crear tu perfil.\n"
            "Usa los menús de abajo y pulsa **Crear Perfil** cuando estés listo.\n\n"
            + "\n".join(lines)
        )

        embed = discord.Embed(
            title="💖 Crea tu perfil",
            description=desc,
            color=discord.Color.pink()
        )

        embed.add_field(
            name="💡 Consejos",
            value=(
                "• Puedes elegir **varios** intereses y tipos de rol.\n"
                "• Tu bio puede tener hasta **500 caracteres**.\n"
                "• Después podrás añadir foto, banner y marcos con `/update`."
            ),
            inline=False
        )

        embed.set_footer(text="⏳ Tienes 5 minutos para completar el formulario.")

        return embed

    @discord.ui.button(label="✍️ Crear Perfil", style=discord.ButtonStyle.green, row=2)
    async def create_profile(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.interests:
            await interaction.response.send_message(
                f"{EMOJI_NO} Selecciona al menos un **interés** antes de continuar.",
                ephemeral=True
            )
            return

        if not self.lines:
            await interaction.response.send_message(
                f"{EMOJI_NO} Selecciona al menos un **tipo de rol** antes de continuar.",
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

    # Verificar ban
    if await is_banned(interaction.user.id):
        await interaction.response.send_message(
            f"{EMOJI_NO} Has sido baneado del sistema y no puedes crear un perfil.",
            ephemeral=True
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id=$1",
        interaction.user.id
    )

    await conn.close()

    if row:
        await interaction.response.send_message(
            f"{EMOJI_NO} Ya tienes un perfil. Usa `/update` para editarlo.",
            ephemeral=True
        )
        return

    view = StartView()

    await interaction.response.send_message(
        embed=view.build_embed(),
        view=view,
        ephemeral=True
    )


start = app_commands.Command(
    name="start",
    description="Crea tu perfil de rol",
    callback=start_callback
)
