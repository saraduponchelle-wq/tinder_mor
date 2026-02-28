import discord
from discord import app_commands
import asyncpg
import os

# ========================
# VIEW CON BOTONES
# ========================
class TinderView(discord.ui.View):
    def __init__(self, profiles, current_index=0, user_id=None):
        super().__init__(timeout=None)
        self.profiles = profiles
        self.current_index = current_index
        self.user_id = user_id  # Usuario que usa /tinder
        self.add_buttons()

    def add_buttons(self):
        # Obtenemos el perfil actual
        profile = self.profiles[self.current_index]
        profile_user_id = profile["user_id"]

        # Limpiamos botones antiguos
        self.clear_items()

        # ❌ Pass
        self.add_item(discord.ui.Button(
            label="❌ Pass",
            style=discord.ButtonStyle.red,
            custom_id=f"pass_{profile_user_id}_{self.user_id}"
        ))

        # ✅ Match
        self.add_item(discord.ui.Button(
            label="✅ Match",
            style=discord.ButtonStyle.green,
            custom_id=f"match_{profile_user_id}_{self.user_id}"
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo el usuario que abrió el /tinder puede usar los botones
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No puedes usar estos botones.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="dummy", style=discord.ButtonStyle.secondary, disabled=True)
    async def dummy(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # Esto es solo para evitar errores de discord.py si View queda vacía

    async def handle_action(self, interaction: discord.Interaction, action: str):
        profile = self.profiles[self.current_index]
        profile_user_id = profile["user_id"]

        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(DATABASE_URL)
        print(f"[DEBUG] Usuario {self.user_id} presionó {action} en perfil {profile_user_id}")

        # --- MATCH ---
        if action == "match":
            # Obtenemos lista de matches actual del usuario
            row = await conn.fetchrow("SELECT matches FROM profiles WHERE user_id=$1", self.user_id)
            user_matches = row["matches"] or []

            if profile_user_id not in user_matches:
                user_matches.append(profile_user_id)
                await conn.execute("UPDATE profiles SET matches=$1 WHERE user_id=$2", user_matches, self.user_id)

            # Comprobar si el otro usuario también hizo match
            other_row = await conn.fetchrow("SELECT matches FROM profiles WHERE user_id=$1", profile_user_id)
            other_matches = other_row["matches"] or []

            if self.user_id in other_matches:
                # Match mutuo
                try:
                    user = await interaction.client.fetch_user(self.user_id)
                    other = await interaction.client.fetch_user(profile_user_id)
                    await user.send(f"💖 ¡Hiciste match con {other.display_name}! Puedes iniciar una conversación.")
                    await other.send(f"💖 ¡Hiciste match con {user.display_name}! Puedes iniciar una conversación.")
                    print(f"[DEBUG] Match mutuo entre {self.user_id} y {profile_user_id}")
                except Exception as e:
                    print(f"[ERROR] No se pudo enviar DM: {e}")

        # --- PASS ---
        # No hacemos nada especial, solo pasar al siguiente perfil

        await conn.close()

        # Pasar al siguiente perfil
        self.current_index += 1
        if self.current_index >= len(self.profiles):
            self.current_index = 0  # Reiniciar ciclo

        self.add_buttons()

        # Actualizar embed
        embed = discord.Embed(
            title=f"💘 Perfil de {profile['name']}",
            color=discord.Color.pink()
        )
        embed.add_field(name="Intereses", value=", ".join(profile["interests"]), inline=False)
        embed.add_field(name="Lineas", value=profile["lines"], inline=False)
        embed.add_field(name="Descripcion", value=profile["description"], inline=False)
        embed.set_thumbnail(url=profile.get("avatar") or interaction.client.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=self)
        print(f"[DEBUG] Embed actualizado al perfil index {self.current_index}")


# ========================
# CALLBACK DEL COMANDO
# ========================
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user.name} ({interaction.user.id})")
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)

    # Traemos todos los perfiles menos el del usuario que usa el comando
    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description
        FROM profiles
        WHERE user_id != $1
        ORDER BY user_id
    """, interaction.user.id)

    await conn.close()
    if not rows:
        await interaction.response.send_message("❌ No hay perfiles disponibles.", ephemeral=True)
        return

    # Convertimos a lista de dicts
    profiles = []
    for row in rows:
        profiles.append({
            "user_id": row["user_id"],
            "name": row["name"],
            "interests": row["interests"] or [],
            "lines": row["lines"],
            "description": row["description"],
            "avatar": None  # Podríamos agregar avatar si lo guardamos en DB
        })

    print(f"[DEBUG] {len(profiles)} perfiles obtenidos")

    # Primer perfil
    view = TinderView(profiles, user_id=interaction.user.id)

    first_profile = profiles[0]
    embed = discord.Embed(
        title=f"💘 Perfil de {first_profile['name']}",
        color=discord.Color.pink()
    )
    embed.add_field(name="Intereses", value=", ".join(first_profile["interests"]), inline=False)
    embed.add_field(name="Lineas", value=first_profile["lines"], inline=False)
    embed.add_field(name="Descripcion", value=first_profile["description"], inline=False)
    embed.set_thumbnail(url=first_profile.get("avatar") or interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    print(f"[DEBUG] Primer embed enviado")


# ========================
# EXPORTABLE
# ========================
tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)