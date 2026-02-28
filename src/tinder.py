import discord
from discord import app_commands
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# ========================
# VIEW CON BOTONES
# ========================
class TinderView(discord.ui.View):
    def __init__(self, profiles, current_index, user_id):
        super().__init__(timeout=None)
        self.profiles = profiles
        self.index = current_index
        self.user_id = user_id

        # Botones únicos
        self.add_item(discord.ui.Button(label="❌ Pass", style=discord.ButtonStyle.red, custom_id=f"pass_{user_id}_{self.index}"))
        self.add_item(discord.ui.Button(label="✅ Match", style=discord.ButtonStyle.green, custom_id=f"match_{user_id}_{self.index}"))

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.red, disabled=True)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # placeholder, se maneja con custom_id en on_interaction

    @discord.ui.button(label="✅ Match", style=discord.ButtonStyle.green, disabled=True)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # placeholder, se maneja con custom_id en on_interaction


# ========================
# COMANDO /TINDER
# ========================
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user.name}")

    conn = await asyncpg.connect(DATABASE_URL)
    print("[DEBUG] Conectado a la DB")

    # Obtener todos los perfiles excepto el del usuario
    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, array_remove(matches, NULL) AS matches
        FROM profiles
        WHERE user_id != $1
        ORDER BY user_id
    """, interaction.user.id)
    print(f"[DEBUG] {len(rows)} perfiles obtenidos")

    if not rows:
        await interaction.response.send_message("No hay otros perfiles disponibles.", ephemeral=True)
        await conn.close()
        return

    # Encontrar el primer perfil al que no le has dado match
    selected_profile = None
    for idx, profile in enumerate(rows):
        matches = profile["matches"] or []
        if interaction.user.id not in matches:
            selected_profile = (idx, profile)
            break

    if not selected_profile:
        # Si todos ya los viste, reiniciamos
        selected_profile = (0, rows[0])

    idx, profile = selected_profile

    # Obtener objeto de Discord para avatar
    try:
        user_obj = await interaction.client.fetch_user(profile["user_id"])
        avatar_url = user_obj.display_avatar.url
    except Exception:
        avatar_url = None

    # Crear embed
    embed = discord.Embed(
        title=f"💘 {profile['name']}",
        color=discord.Color.pink()
    )
    embed.add_field(name="Intereses", value=", ".join(profile["interests"]), inline=False)
    embed.add_field(name="Lineas", value=profile["lines"], inline=False)
    embed.add_field(name="Descripción", value=profile["description"], inline=False)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    # Crear la vista con botones
    view = TinderView(rows, idx, interaction.user.id)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    print("[DEBUG] Mensaje enviado al usuario")
    await conn.close()
    print("[DEBUG] Conexión DB cerrada")


# ========================
# COMANDO EXPORTABLE
# ========================
tinder = app_commands.Command(
    name="tinder",
    description="Revisa perfiles como en Tinder",
    callback=tinder_callback
)