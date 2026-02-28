import discord
from discord import app_commands
import asyncpg
import os

# ========================
# VIEW CON BOTONES
# ========================
class TinderView(discord.ui.View):
    def __init__(self, user_id, profiles, current_index=0):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.profiles = profiles
        self.current_index = current_index

        # Botones
        self.add_item(discord.ui.Button(label="❌ Pass", style=discord.ButtonStyle.red, custom_id=f"pass_{user_id}_{current_index}"))
        self.add_item(discord.ui.Button(label="✅ Match", style=discord.ButtonStyle.green, custom_id=f"match_{user_id}_{current_index}"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo puede usar el usuario que inició
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo puedes interactuar con tu propio tinder.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.red)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] Pass presionado por {interaction.user}")
        await self.next_profile(interaction, passed=True)

    @discord.ui.button(label="✅ Match", style=discord.ButtonStyle.green)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] Match presionado por {interaction.user}")
        await self.next_profile(interaction, passed=False)

    async def next_profile(self, interaction: discord.Interaction, passed: bool):
        # Conexión a DB
        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(DATABASE_URL)

        current_profile = self.profiles[self.current_index]
        target_id = current_profile["user_id"]

        # Si es match, agregamos a la lista de matches del usuario
        if not passed:
            print(f"[DEBUG] Guardando match de {self.user_id} -> {target_id}")
            await conn.execute("""
                UPDATE profiles
                SET matches = array_append(matches, $2)
                WHERE user_id = $1 AND NOT $2 = ANY(matches)
            """, self.user_id, target_id)

            # Revisamos si el target también nos tiene en su matches
            target_row = await conn.fetchrow("SELECT matches FROM profiles WHERE user_id = $1", target_id)
            if target_row and self.user_id in target_row["matches"]:
                print(f"[DEBUG] MATCH MUTUO detectado entre {self.user_id} y {target_id}")
                # Notificar a ambos
                user = interaction.user
                target_user = await interaction.client.fetch_user(target_id)
                try:
                    await user.send(f"💖 ¡Hiciste match con {target_user.name}! Puedes empezar a chatear.")
                    await target_user.send(f"💖 ¡Hiciste match con {user.name}! Puedes empezar a chatear.")
                except Exception as e:
                    print(f"[DEBUG] No se pudo enviar mensaje a alguno: {e}")

        # Pasar al siguiente perfil
        self.current_index += 1
        if self.current_index >= len(self.profiles):
            self.current_index = 0  # reiniciar ciclo
            print("[DEBUG] Reiniciando ciclo de perfiles")

        next_profile = self.profiles[self.current_index]
        embed = discord.Embed(
            title=f"{next_profile['name']} 💘",
            description=next_profile["description"],
            color=discord.Color.pink()
        )
        embed.add_field(name="Intereses", value=", ".join(next_profile["interests"]), inline=False)
        embed.add_field(name="Líneas", value=next_profile["lines"], inline=False)
        embed.set_thumbnail(url=next_profile["avatar"])

        # Reemplazar mensaje con nuevo embed y nuevos botones
        new_view = TinderView(self.user_id, self.profiles, self.current_index)
        try:
            await interaction.response.edit_message(embed=embed, view=new_view)
        except Exception as e:
            print(f"[DEBUG] Error al actualizar embed: {e}")

        await conn.close()


# ========================
# COMANDO SLASH
# ========================
async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user}")

    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)
    print("[DEBUG] Conectado a la DB")

    # Obtenemos todos los perfiles menos el del usuario que ejecuta
    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, avatar, matches
        FROM profiles
        WHERE user_id != $1
    """, interaction.user.id)
    print(f"[DEBUG] {len(rows)} perfiles obtenidos")

    await conn.close()
    print("[DEBUG] Conexión DB cerrada")

    if not rows:
        await interaction.response.send_message("No hay perfiles disponibles.", ephemeral=True)
        return

    # Embed del primer perfil
    first_profile = rows[0]
    embed = discord.Embed(
        title=f"{first_profile['name']} 💘",
        description=first_profile["description"],
        color=discord.Color.pink()
    )
    embed.add_field(name="Intereses", value=", ".join(first_profile["interests"]), inline=False)
    embed.add_field(name="Líneas", value=first_profile["lines"], inline=False)
    embed.set_thumbnail(url=first_profile["avatar"])

    view = TinderView(interaction.user.id, rows, current_index=0)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# Exportable
tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)