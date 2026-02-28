import discord
from discord import app_commands
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# ========================
# VIEW PARA EL TINDER
# ========================
class TinderView(discord.ui.View):
    def __init__(self, user_id, profiles):
        super().__init__(timeout=None)
        self.user_id = user_id  # quien está usando tinder
        self.profiles = profiles  # lista de perfiles de DB
        self.index = 0  # índice del perfil actual

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo puede interactuar el usuario que abrió el comando
        return interaction.user.id == self.user_id

    async def show_profile(self, interaction: discord.Interaction):
        # Mostrar perfil actual
        if not self.profiles:
            await interaction.response.send_message("No hay perfiles disponibles.", ephemeral=True)
            return

        profile = self.profiles[self.index]
        embed = discord.Embed(
            title=f"💘 Perfil de {profile['name']}",
            description=profile["description"],
            color=discord.Color.pink()
        )
        embed.add_field(name="Que te interesa", value=", ".join(profile["interests"]), inline=False)
        embed.add_field(name="Lineas", value=profile["lines"], inline=False)
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{profile['user_id']}/{profile['avatar']}.png")

        # Envía el embed con los botones
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💚 Match", style=discord.ButtonStyle.green, custom_id="tinder_match")
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = self.profiles[self.index]
        print(f"[DEBUG] {interaction.user} presionó MATCH sobre {profile['name']} ({profile['user_id']})")

        # Conectar DB
        conn = await asyncpg.connect(DATABASE_URL)

        # Actualizar matches del usuario actual
        await conn.execute("""
            UPDATE profiles
            SET matches = array_append(matches, $1)
            WHERE user_id = $2 AND NOT $1 = ANY(matches)
        """, profile['user_id'], self.user_id)

        # Revisar si hay match mutuo
        other_matches = await conn.fetchval("SELECT matches FROM profiles WHERE user_id = $1", profile['user_id'])
        if other_matches and self.user_id in other_matches:
            # Match mutuo!
            print(f"[DEBUG] ¡MATCH mutuo! {interaction.user.id} <-> {profile['user_id']}")
            try:
                user = await interaction.client.fetch_user(self.user_id)
                other = await interaction.client.fetch_user(profile['user_id'])
                await user.send(f"¡Hiciste MATCH con {profile['name']}! Puedes iniciar conversación.")
                await other.send(f"¡Hiciste MATCH con {interaction.user.name}! Puedes iniciar conversación.")
            except Exception as e:
                print(f"[DEBUG] Error al notificar match: {e}")

        await conn.close()

        # Pasar al siguiente perfil
        self.index = (self.index + 1) % len(self.profiles)
        print(f"[DEBUG] Mostrando siguiente perfil, índice {self.index}")
        await self.show_profile(interaction)

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.red, custom_id="tinder_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = self.profiles[self.index]
        print(f"[DEBUG] {interaction.user} presionó PASS sobre {profile['name']} ({profile['user_id']})")

        # Pasar al siguiente perfil
        self.index = (self.index + 1) % len(self.profiles)
        print(f"[DEBUG] Mostrando siguiente perfil, índice {self.index}")
        await self.show_profile(interaction)

# ========================
# SLASH COMMAND
# ========================
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user}")

    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, array_remove(matches, NULL) AS matches,
               encode(avatar::bytea, 'hex') AS avatar
        FROM profiles
        WHERE user_id != $1
        ORDER BY user_id
    """, interaction.user.id)
    await conn.close()

    print(f"[DEBUG] Conectado a la DB")
    print(f"[DEBUG] {len(rows)} perfiles obtenidos")

    if not rows:
        await interaction.response.send_message("No hay perfiles disponibles.", ephemeral=True)
        return

    # Inicializar la vista de tinder
    view = TinderView(interaction.user.id, rows)
    profile = rows[0]

    embed = discord.Embed(
        title=f"💘 Perfil de {profile['name']}",
        description=profile["description"],
        color=discord.Color.pink()
    )
    embed.add_field(name="Que te interesa", value=", ".join(profile["interests"]), inline=False)
    embed.add_field(name="Lineas", value=profile["lines"], inline=False)
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{profile['user_id']}/{profile['avatar']}.png")

    print(f"[DEBUG] Conexión DB cerrada")

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Comando exportable
tinder = app_commands.Command(
    name="tinder",
    description="Explora perfiles como en Tinder",
    callback=tinder_callback
)