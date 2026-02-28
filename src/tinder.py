import discord
from discord import app_commands
import asyncpg
import os

class TinderView(discord.ui.View):
    def __init__(self, user_id, profiles):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.profiles = profiles
        self.index = 0  # Índice del perfil actual

        # Botones
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="💚 Match", custom_id="match"))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="❌ Pass", custom_id="pass"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo el usuario que inició puede interactuar
        return interaction.user.id == self.user_id

    @discord.ui.button(label="💚 Match", style=discord.ButtonStyle.green, custom_id="match")
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] {interaction.user} presionó MATCH")
        await interaction.response.send_message("Debug: MATCH presionado", ephemeral=True)

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.red, custom_id="pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] {interaction.user} presionó PASS")
        await interaction.response.send_message("Debug: PASS presionado", ephemeral=True)

async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user}")

    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)
    print("[DEBUG] Conectado a la DB")

    try:
        # Traer todos los perfiles excepto el del usuario
        rows = await conn.fetch("SELECT * FROM profiles WHERE user_id != $1", interaction.user.id)
        print(f"[DEBUG] {len(rows)} perfiles obtenidos")
    except Exception as e:
        print("[ERROR] Fallo al obtener perfiles:", e)
        rows = []
    finally:
        await conn.close()
        print("[DEBUG] Conexión DB cerrada")

    if not rows:
        await interaction.response.send_message("❌ No hay perfiles disponibles.", ephemeral=True)
        return

    # Mostrar el primer perfil
    profile = rows[0]
    embed = discord.Embed(
        title=f"💘 Perfil: {profile['name']}",
        description=f"Que te interesa: {', '.join(profile['interests'])}\nLineas: {profile['lines']}\nDescripcion: {profile['description']}",
        color=discord.Color.pink()
    )

    view = TinderView(interaction.user.id, rows)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles de otros usuarios",
    callback=tinder_callback
)