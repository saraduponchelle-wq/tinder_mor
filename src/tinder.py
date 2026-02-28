import discord
from discord import app_commands
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# ========================
# VIEW DE TINDER
# ========================
class TinderView(discord.ui.View):
    def __init__(self, user_id, profiles):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.profiles = profiles  # lista de dict con perfiles
        self.index = 0
        self.current_profile = None

        # Botones
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="💚 Match", custom_id="tinder_match"))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="❌ Pass", custom_id="tinder_pass"))

    async def update_embed(self, interaction):
        if not self.profiles:
            await interaction.response.edit_message(content="No hay perfiles disponibles", embed=None, view=None)
            return

        # Recorrer hasta encontrar un perfil que no esté en matches del usuario
        start_index = self.index
        while True:
            profile = self.profiles[self.index]
            user_matches = profile.get("matches", [])
            if str(self.user_id) not in user_matches:
                break
            self.index = (self.index + 1) % len(self.profiles)
            if self.index == start_index:
                # Todos los perfiles ya fueron vistos
                break

        self.current_profile = self.profiles[self.index]
        print(f"[DEBUG] Mostrando perfil: {self.current_profile['user_id']}")  # debug

        # Crear embed
        embed = discord.Embed(title=f"{self.current_profile['name']}", color=discord.Color.purple())
        embed.add_field(name="Intereses", value=", ".join(self.current_profile.get("interests", [])), inline=False)
        embed.add_field(name="Lineas", value=self.current_profile.get("lines", ""), inline=False)
        embed.add_field(name="Descripción", value=self.current_profile.get("description", ""), inline=False)
        # Avatar directamente de Discord
        embed.set_thumbnail(url=self.current_profile.get("discord_avatar", "https://i.imgur.com/placeholder.png"))

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💚 Match", style=discord.ButtonStyle.green, custom_id="tinder_match")
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] {interaction.user.id} presionó MATCH")  # debug

        target_id = self.current_profile["user_id"]

        conn = await asyncpg.connect(DATABASE_URL)

        # Añadir target al array de matches del usuario
        await conn.execute("""
            UPDATE profiles
            SET matches = array_append(matches, $2)
            WHERE user_id = $1
        """, interaction.user.id, target_id)

        # Comprobar si hay match mutuo
        target_matches = await conn.fetchval("SELECT matches FROM profiles WHERE user_id = $1", target_id)
        if target_matches and str(interaction.user.id) in target_matches:
            print(f"[DEBUG] ¡MATCH mutuo! {interaction.user.id} <-> {target_id}")  # debug
            user = interaction.client.get_user(interaction.user.id)
            target_user = interaction.client.get_user(target_id)
            if user and target_user:
                await user.send(f"💘 ¡Hiciste match con {target_user.name}!")
                await target_user.send(f"💘 ¡Hiciste match con {user.name}!")

        await conn.close()

        # Pasar al siguiente perfil
        self.index = (self.index + 1) % len(self.profiles)
        await self.update_embed(interaction)

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.red, custom_id="tinder_pass")
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] {interaction.user.id} presionó PASS")  # debug
        self.index = (self.index + 1) % len(self.profiles)
        await self.update_embed(interaction)

# ========================
# COMANDO TINDER
# ========================
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user}")  # debug
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT user_id, name, interests, lines, description, matches FROM profiles WHERE user_id != $1", interaction.user.id)

    profiles = []
    for row in rows:
        profiles.append({
            "user_id": row["user_id"],
            "name": row["name"],
            "interests": row["interests"] or [],
            "lines": row["lines"] or "",
            "description": row["description"] or "",
            "matches": row["matches"] or [],
            "discord_avatar": interaction.client.get_user(row["user_id"]).display_avatar.url if interaction.client.get_user(row["user_id"]) else "https://i.imgur.com/placeholder.png"
        })

    print(f"[DEBUG] {len(profiles)} perfiles obtenidos")  # debug
    await conn.close()

    if not profiles:
        await interaction.response.send_message("No hay perfiles disponibles", ephemeral=True)
        return

    view = TinderView(interaction.user.id, profiles)
    embed = discord.Embed(title=f"{profiles[0]['name']}", color=discord.Color.purple())
    embed.add_field(name="Intereses", value=", ".join(profiles[0]["interests"]), inline=False)
    embed.add_field(name="Lineas", value=profiles[0]["lines"], inline=False)
    embed.add_field(name="Descripción", value=profiles[0]["description"], inline=False)
    embed.set_thumbnail(url=profiles[0]["discord_avatar"])

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# Exportable
tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)