# src/tinder.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncpg
import uuid

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------
# CONFIG DB
DB_CONFIG = {
    "user": "postgres",
    "password": "password",
    "database": "mydb",
    "host": "localhost",
}

# ------------------------------
# FUNCIONES DE BASE DE DATOS
async def get_profiles(exclude_user_id):
    print(f"[DEBUG] Conectando a DB para {exclude_user_id}")
    conn = await asyncpg.connect(**DB_CONFIG)
    rows = await conn.fetch("""
        SELECT id, username, discrim
        FROM users
        WHERE id != $1
    """, exclude_user_id)
    await conn.close()
    print(f"[DEBUG] {len(rows)} perfiles obtenidos")
    return rows

async def add_match(user_id, target_id):
    conn = await asyncpg.connect(**DB_CONFIG)
    # añade target_id a la lista de matches de user_id
    await conn.execute("""
        INSERT INTO matches (user_id, match_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, user_id, target_id)
    await conn.close()
    print(f"[DEBUG] {user_id} puso match a {target_id}")

# ------------------------------
# VISTA CON BOTONES
class TinderView(discord.ui.View):
    def __init__(self, profiles, user_id):
        super().__init__(timeout=None)
        self.profiles = profiles
        self.index = 0
        self.user_id = user_id
        self.update_buttons()

    def update_buttons(self):
        # Limpiamos botones antiguos
        self.clear_items()
        # Generamos custom_id únicos
        pass_id = f"pass_{uuid.uuid4()}"
        match_id = f"match_{uuid.uuid4()}"
        # Añadimos botones
        self.add_item(discord.ui.Button(label="Pass", style=discord.ButtonStyle.danger, custom_id=pass_id))
        self.add_item(discord.ui.Button(label="Match", style=discord.ButtonStyle.success, custom_id=match_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo el usuario que ejecutó el comando puede usar los botones
        return interaction.user.id == self.user_id

    async def on_timeout(self):
        print("[DEBUG] View timeout")

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.danger)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] {interaction.user} presionó PASS")
        await self.next_profile(interaction)

    @discord.ui.button(label="Match", style=discord.ButtonStyle.success)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = self.profiles[self.index]
        print(f"[DEBUG] {interaction.user} presionó MATCH -> {profile['username']}#{profile['discrim']}")
        await add_match(self.user_id, profile['id'])
        await self.next_profile(interaction)

    async def next_profile(self, interaction: discord.Interaction):
        self.index += 1
        if self.index >= len(self.profiles):
            self.index = 0  # volvemos al inicio
            print("[DEBUG] Se acabaron perfiles, volvemos a empezar")
        profile = self.profiles[self.index]
        embed = discord.Embed(
            title=f"{profile['username']}#{profile['discrim']}",
            description="Perfil de prueba",
            color=discord.Color.blue()
        )
        print(f"[DEBUG] Mostrando perfil {profile['username']}#{profile['discrim']}")
        await interaction.response.edit_message(embed=embed, view=self)

# ------------------------------
# CALLBACK DEL COMANDO
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user} ({interaction.user.id})")
    profiles = await get_profiles(interaction.user.id)
    if not profiles:
        await interaction.response.send_message("No hay otros perfiles disponibles.", ephemeral=True)
        return

    first_profile = profiles[0]
    embed = discord.Embed(
        title=f"{first_profile['username']}#{first_profile['discrim']}",
        description="Primer perfil",
        color=discord.Color.blue()
    )
    view = TinderView(profiles, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    print("[DEBUG] Primer embed enviado")

# ------------------------------
# EXPORTABLE
tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)