import discord
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

        # Botones dinámicos con custom_id único
        self.pass_button = discord.ui.Button(
            label="❌ Pass", style=discord.ButtonStyle.red, custom_id=f"pass_{user_id}_{self.index}"
        )
        self.match_button = discord.ui.Button(
            label="✅ Match", style=discord.ButtonStyle.green, custom_id=f"match_{user_id}_{self.index}"
        )

        self.add_item(self.pass_button)
        self.add_item(self.match_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Permitir solo al usuario que ejecutó el comando
        return interaction.user.id == self.user_id

    async def on_interaction(self, interaction: discord.Interaction):
        print(f"[DEBUG] Botón presionado: {interaction.data['custom_id']} por {interaction.user.name}")

        conn = await asyncpg.connect(DATABASE_URL)
        print("[DEBUG] Conectado a la DB en on_interaction")

        action, user_id_str, profile_idx_str = interaction.data["custom_id"].split("_")
        profile_idx = int(profile_idx_str)
        profile = self.profiles[profile_idx]
        print(f"[DEBUG] Acción: {action}, Perfil: {profile['name']}")

        if action == "match":
            # Añadir match al usuario
            matches = profile.get("matches") or []
            if interaction.user.id not in matches:
                matches.append(interaction.user.id)
                await conn.execute(
                    "UPDATE profiles SET matches = $1 WHERE user_id = $2",
                    matches,
                    profile["user_id"]
                )
                print(f"[DEBUG] Match agregado a {profile['name']}")

                # Revisar si hay match mutuo
                row = await conn.fetchrow(
                    "SELECT matches FROM profiles WHERE user_id = $1",
                    interaction.user.id
                )
                user_matches = row["matches"] or []
                if profile["user_id"] in user_matches:
                    print(f"[DEBUG] MATCH MUTUO entre {interaction.user.name} y {profile['name']}")
                    # Enviar mensaje a ambos usuarios
                    user_obj = await interaction.client.fetch_user(interaction.user.id)
                    other_obj = await interaction.client.fetch_user(profile["user_id"])
                    try:
                        await user_obj.send(f"💖 ¡Hiciste match con {profile['name']}!")
                        await other_obj.send(f"💖 ¡Hiciste match con {user_obj.name}!")
                    except:
                        print("[DEBUG] No se pudo enviar DM")

        elif action == "pass":
            print(f"[DEBUG] Usuario {interaction.user.name} hizo pass en {profile['name']}")

        # Pasar al siguiente perfil
        next_idx = (profile_idx + 1) % len(self.profiles)
        next_profile = self.profiles[next_idx]

        try:
            user_obj = await interaction.client.fetch_user(next_profile["user_id"])
            avatar_url = user_obj.display_avatar.url
        except Exception:
            avatar_url = None

        embed = discord.Embed(
            title=f"💘 {next_profile['name']}",
            color=discord.Color.pink()
        )
        embed.add_field(name="Intereses", value=", ".join(next_profile["interests"]), inline=False)
        embed.add_field(name="Lineas", value=next_profile["lines"], inline=False)
        embed.add_field(name="Descripción", value=next_profile["description"], inline=False)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # Actualizar embed y botones con nuevo perfil
        self.clear_items()
        self.index = next_idx
        self.add_item(discord.ui.Button(
            label="❌ Pass", style=discord.ButtonStyle.red, custom_id=f"pass_{self.user_id}_{self.index}"
        ))
        self.add_item(discord.ui.Button(
            label="✅ Match", style=discord.ButtonStyle.green, custom_id=f"match_{self.user_id}_{self.index}"
        ))

        await interaction.response.edit_message(embed=embed, view=self)
        print(f"[DEBUG] Embed actualizado a {next_profile['name']}")
        await conn.close()
        print("[DEBUG] Conexión DB cerrada en on_interaction")


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

    # Mostrar el primer perfil
    idx, profile = 0, rows[0]

    try:
        user_obj = await interaction.client.fetch_user(profile["user_id"])
        avatar_url = user_obj.display_avatar.url
    except Exception:
        avatar_url = None

    embed = discord.Embed(
        title=f"💘 {profile['name']}",
        color=discord.Color.pink()
    )
    embed.add_field(name="Intereses", value=", ".join(profile["interests"]), inline=False)
    embed.add_field(name="Lineas", value=profile["lines"], inline=False)
    embed.add_field(name="Descripción", value=profile["description"], inline=False)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    view = TinderView(rows, idx, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    print("[DEBUG] Mensaje enviado al usuario")
    await conn.close()
    print("[DEBUG] Conexión DB cerrada")


from discord import app_commands

tinder = app_commands.Command(
    name="tinder",
    description="Explora perfiles y haz match",
    callback=tinder_callback
)