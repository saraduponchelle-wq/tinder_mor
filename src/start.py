import discord
from discord import app_commands
import asyncpg
import os

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

        super().__init__(
            placeholder="¿Qué te interesa?",
            min_values=1,
            max_values=4,
            options=options
        )
        if default_values:
            self.default_values = default_values

    async def callback(self, interaction: discord.Interaction):
        self.view.interests = self.values
        await interaction.response.defer()


# ========================
# SELECT: Lineas
# ========================
class LinesSelect(discord.ui.Select):
    def __init__(self, default_value=None):
        options = [
            discord.SelectOption(label="Corto"),
            discord.SelectOption(label="Medio"),
            discord.SelectOption(label="Largo"),
            discord.SelectOption(label="Biblias"),
        ]

        super().__init__(
            placeholder="¿Cuánto escribes?",
            min_values=1,
            max_values=1,
            options=options
        )
        if default_value:
            self.default = default_value

    async def callback(self, interaction: discord.Interaction):
        self.view.lines = self.values[0]
        await interaction.response.defer()


# ========================
# MODAL
# ========================
class ProfileModal(discord.ui.Modal, title="Crea tu perfil"):
    def __init__(self, interests, lines, default_name="", default_description=""):
        super().__init__()
        self.interests = interests
        self.lines = lines

        # TextInputs con valores por defecto
        self.name = discord.ui.TextInput(
            label="Nombre",
            max_length=50,
            default=default_name
        )
        self.description = discord.ui.TextInput(
            label="Descripción",
            style=discord.TextStyle.paragraph,
            max_length=500,
            default=default_description
        )

        # Añadir inputs al modal
        self.add_item(self.name)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(DATABASE_URL)

        # Revisar si ya hay un perfil
        row = await conn.fetchrow("SELECT message_id FROM profiles WHERE user_id = $1", interaction.user.id)

        # Borrar embed anterior si existe
        if row and row["message_id"]:
            try:
                msg = await interaction.channel.fetch_message(row["message_id"])
                await msg.delete()
            except:
                pass

        # Crear embed
        embed = discord.Embed(title="💘 Perfil creado", color=discord.Color.pink())
        embed.add_field(name="Name", value=self.name.value, inline=False)
        embed.add_field(name="Que te interesa", value=", ".join(self.interests), inline=False)
        embed.add_field(name="Lineas", value=self.lines, inline=False)
        embed.add_field(name="Descripcion", value=self.description.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Enviar mensaje
        await interaction.response.send_message(embed=embed)
        sent_message = await interaction.original_response()

        # Guardar en DB usando TEXT[] directamente
        await conn.execute("""
            INSERT INTO profiles(user_id, name, interests, lines, description, message_id)
            VALUES($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id)
            DO UPDATE SET name = $2, interests = $3, lines = $4, description = $5, message_id = $6
        """, interaction.user.id, self.name.value, self.interests, self.lines, self.description.value, sent_message.id)

        await conn.close()


# ========================
# VIEW PRINCIPAL
# ========================
class StartView(discord.ui.View):
    def __init__(self, default_interests=None, default_lines=None):
        super().__init__(timeout=180)
        self.interests = default_interests or []
        self.lines = default_lines

        self.add_item(InterestSelect(default_values=self.interests))
        self.add_item(LinesSelect(default_value=self.lines))

    @discord.ui.button(label="Crear Perfil", style=discord.ButtonStyle.green)
    async def create_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.interests or not self.lines:
            await interaction.response.send_message(
                "❌ Debes seleccionar intereses y líneas primero.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            ProfileModal(self.interests, self.lines)
        )


# ========================
# SLASH COMMAND EXPORTABLE
# ========================
async def start_callback(interaction: discord.Interaction):
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id = $1", interaction.user.id)
    await conn.close()

    if row:  # Ya tiene perfil
        await interaction.response.send_message(
            "❌ Ya tienes un perfil creado. Usa `/update` para modificarlo.",
            ephemeral=True
        )
        return

    # Si no tiene perfil, crear el embed con formulario
    embed = discord.Embed(
        title="💘 Crea tu perfil Tinder Discord",
        description="Selecciona tus preferencias y luego pulsa **Crear Perfil**.",
        color=discord.Color.pink()
    )
    await interaction.response.send_message(
        embed=embed,
        view=StartView(),
        ephemeral=True
    )


start = app_commands.Command(
    name="start",
    description="Crea tu perfil de Tinder Discord",
    callback=start_callback
)