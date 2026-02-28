# src/tinder.py

import discord
from discord import app_commands
import asyncpg
import os

# ===============================
# DB HELPERS
# ===============================

async def get_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return await asyncpg.connect(DATABASE_URL)

async def get_profiles(exclude_user_id: int):
    print("[DEBUG] Cargando perfiles...")
    conn = await get_connection()

    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, matches
        FROM profiles
        WHERE user_id != $1
    """, exclude_user_id)

    await conn.close()
    print(f"[DEBUG] {len(rows)} perfiles encontrados")
    return rows

async def add_match(user_id: int, target_id: int):
    print(f"[DEBUG] Guardando match {user_id} -> {target_id}")
    conn = await get_connection()

    row = await conn.fetchrow("SELECT matches FROM profiles WHERE user_id=$1", user_id)
    matches = row["matches"] or []

    if target_id not in matches:
        matches.append(target_id)
        await conn.execute(
            "UPDATE profiles SET matches=$1 WHERE user_id=$2",
            matches,
            user_id
        )

    await conn.close()

async def is_mutual_match(user_id: int, target_id: int):
    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT matches FROM profiles WHERE user_id=$1",
        target_id
    )

    await conn.close()

    if not row:
        return False

    matches = row["matches"] or []
    return user_id in matches


# ===============================
# VIEW
# ===============================

class TinderView(discord.ui.View):
    def __init__(self, profiles, author_id):
        super().__init__(timeout=60)
        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.danger)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("[DEBUG] PASS presionado")
        await self.next_profile(interaction)

    @discord.ui.button(label="✅ Match", style=discord.ButtonStyle.success)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("[DEBUG] MATCH presionado")

        profile = self.profiles[self.index]
        target_id = profile["user_id"]

        await add_match(self.author_id, target_id)

        mutual = await is_mutual_match(self.author_id, target_id)

        if mutual:
            print("[DEBUG] MATCH MUTUO DETECTADO")

            user1 = await interaction.client.fetch_user(self.author_id)
            user2 = await interaction.client.fetch_user(target_id)

            try:
                await user1.send(
                    f"💖 ¡Hiciste match con {user2.mention}! ¡Es hora de hablar!"
                )
                await user2.send(
                    f"💖 ¡Hiciste match con {user1.mention}! ¡Es hora de hablar!"
                )
                print("[DEBUG] DMs enviadas correctamente")
            except Exception as e:
                print(f"[ERROR] No se pudo enviar DM: {e}")

        await self.next_profile(interaction)

    async def next_profile(self, interaction: discord.Interaction):
        self.index += 1

        if self.index >= len(self.profiles):
            self.index = 0
            print("[DEBUG] Reiniciando perfiles")

        profile = self.profiles[self.index]

        embed = discord.Embed(
            title=f"💘 Perfil de {profile['name']}",
            color=discord.Color.pink()
        )

        embed.add_field(
            name="Intereses",
            value=", ".join(profile["interests"] or ["Ninguno"]),
            inline=False
        )

        embed.add_field(
            name="Líneas",
            value=profile["lines"] or "Sin líneas",
            inline=False
        )

        embed.add_field(
            name="Descripción",
            value=profile["description"] or "Sin descripción",
            inline=False
        )

        # 🔥 Avatar real
        user = await interaction.client.fetch_user(profile["user_id"])
        embed.set_thumbnail(url=user.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=self)


# ===============================
# COMANDO
# ===============================

async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user}")

    await interaction.response.defer(ephemeral=True)

    rows = await get_profiles(interaction.user.id)

    if not rows:
        await interaction.followup.send(
            "❌ No hay perfiles disponibles.",
            ephemeral=True
        )
        return

    profiles = [dict(row) for row in rows]

    first = profiles[0]

    embed = discord.Embed(
        title=f"💘 Perfil de {first['name']}",
        color=discord.Color.pink()
    )

    embed.add_field(
        name="Intereses",
        value=", ".join(first["interests"] or ["Ninguno"]),
        inline=False
    )

    embed.add_field(
        name="Líneas",
        value=first["lines"] or "Sin líneas",
        inline=False
    )

    embed.add_field(
        name="Descripción",
        value=first["description"] or "Sin descripción",
        inline=False
    )

    # 🔥 Avatar real
    user = await interaction.client.fetch_user(first["user_id"])
    embed.set_thumbnail(url=user.display_avatar.url)

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ===============================
# EXPORTABLE
# ===============================

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)