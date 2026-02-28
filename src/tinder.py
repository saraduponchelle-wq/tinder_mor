# src/tinder.py

import discord
from discord import app_commands
import asyncpg
import os

# ===============================
# CONEXIÓN A BASE DE DATOS
# ===============================

async def get_profiles(exclude_user_id: int):
    print(f"[DEBUG] Intentando conectar a la DB...")
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        print("[ERROR] DATABASE_URL no está definida")
        return []

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("[DEBUG] Conexión a DB exitosa")

        rows = await conn.fetch("""
            SELECT user_id, name, interests, lines, description
            FROM profiles
            WHERE user_id != $1
        """, exclude_user_id)

        await conn.close()
        print(f"[DEBUG] {len(rows)} perfiles obtenidos")
        return rows

    except Exception as e:
        print(f"[ERROR] Error conectando a la DB: {e}")
        return []


# ===============================
# VIEW DE TINDER
# ===============================

class TinderView(discord.ui.View):
    def __init__(self, profiles, author_id):
        super().__init__(timeout=300)  # 5 min
        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

        print(f"[DEBUG] View creada con {len(profiles)} perfiles")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        print(f"[DEBUG] interaction_check -> {interaction.user.id}")

        if interaction.user.id != self.author_id:
            print("[DEBUG] Usuario no autorizado a usar estos botones")
            await interaction.response.send_message(
                "❌ No puedes usar estos botones.",
                ephemeral=True
            )
            return False

        return True

    async def on_timeout(self):
        print("[DEBUG] View expiró (timeout)")

    # ===============================
    # BOTÓN PASS
    # ===============================

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.danger)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("[DEBUG] Botón PASS presionado")
        await self.next_profile(interaction)

    # ===============================
    # BOTÓN MATCH
    # ===============================

    @discord.ui.button(label="✅ Match", style=discord.ButtonStyle.success)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("[DEBUG] Botón MATCH presionado")

        current_profile = self.profiles[self.index]
        print(f"[DEBUG] Match a user_id {current_profile['user_id']}")

        # Aquí podrías guardar match en DB si quieres

        await self.next_profile(interaction)

    # ===============================
    # CAMBIAR PERFIL
    # ===============================

    async def next_profile(self, interaction: discord.Interaction):
        print(f"[DEBUG] Perfil actual index: {self.index}")

        self.index += 1

        if self.index >= len(self.profiles):
            print("[DEBUG] Se acabaron perfiles, reiniciando a 0")
            self.index = 0

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

        print(f"[DEBUG] Mostrando perfil {profile['user_id']} en index {self.index}")

        await interaction.response.edit_message(embed=embed, view=self)


# ===============================
# COMANDO /tinder
# ===============================

async def tinder_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /tinder usado por {interaction.user} ({interaction.user.id})")

    await interaction.response.defer(ephemeral=True)
    print("[DEBUG] Interacción defer hecha")

    profiles_raw = await get_profiles(interaction.user.id)

    if not profiles_raw:
        print("[DEBUG] No hay perfiles disponibles")
        await interaction.followup.send(
            "❌ No hay perfiles disponibles.",
            ephemeral=True
        )
        return

    profiles = []
    for row in profiles_raw:
        profiles.append({
            "user_id": row["user_id"],
            "name": row["name"],
            "interests": row["interests"],
            "lines": row["lines"],
            "description": row["description"]
        })

    print(f"[DEBUG] Preparando primer perfil")

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

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral=True
    )

    print("[DEBUG] Primer embed enviado correctamente")


# ===============================
# EXPORTABLE
# ===============================

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)