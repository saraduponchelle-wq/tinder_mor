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
    conn = await get_connection()

    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, matches
        FROM profiles
        WHERE user_id != $1
    """, exclude_user_id)

    await conn.close()
    return rows


async def add_match(user_id: int, target_id: int):
    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT matches FROM profiles WHERE user_id=$1",
        user_id
    )

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


async def get_full_profile(user_id: int):
    conn = await get_connection()
    row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id=$1", user_id)
    await conn.close()
    return dict(row)


# ===============================
# ENVIAR PERFIL (CONTROL DISCORD)
# ===============================

async def send_profile(
    receiver: discord.User,
    profile_data: dict,
    target_user: discord.User,
    show_discord: bool = False
):
    embed = discord.Embed(
        title=f"💘 Has hecho match con {profile_data['name']}",
        color=discord.Color.pink()
    )

    embed.add_field(
        name="Intereses",
        value=", ".join(profile_data["interests"] or ["Ninguno"]),
        inline=False
    )

    embed.add_field(
        name="Líneas",
        value=profile_data["lines"] or "Sin líneas",
        inline=False
    )

    embed.add_field(
        name="Descripción",
        value=profile_data["description"] or "Sin descripción",
        inline=False
    )

    embed.set_thumbnail(url=target_user.display_avatar.url)

    # Solo mostrar Discord si está permitido
    if show_discord:
        embed.add_field(
            name="👤 Usuario de Discord",
            value=target_user.mention,
            inline=False
        )

    await receiver.send(embed=embed)


# ===============================
# BOTONES PARA ACEPTAR LIKE
# ===============================

class LikeBackView(discord.ui.View):

    def __init__(self, liker_id: int):
        super().__init__(timeout=86400)  # 24 horas
        self.liker_id = liker_id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="❤️ Hacer Match", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        await add_match(interaction.user.id, self.liker_id)

        user1 = interaction.user
        user2 = await interaction.client.fetch_user(self.liker_id)

        profile1 = await get_full_profile(user1.id)
        profile2 = await get_full_profile(user2.id)

        # 🔥 Match aceptado manualmente → SIN mostrar Discord
        await send_profile(user1, profile2, user2, show_discord=False)
        await send_profile(user2, profile1, user1, show_discord=False)

        await interaction.response.edit_message(
            content="💘 ¡Match realizado!",
            view=None
        )

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.edit_message(
            content="❌ Has rechazado el like.",
            view=None
        )


# ===============================
# TINDER VIEW
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
        await interaction.response.defer()
        await self.next_profile(interaction)

    @discord.ui.button(label="❤️ Like", style=discord.ButtonStyle.success)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        target_id = self.profiles[self.index]["user_id"]

        await add_match(self.author_id, target_id)

        if await is_mutual_match(self.author_id, target_id):

            user1 = await interaction.client.fetch_user(self.author_id)
            user2 = await interaction.client.fetch_user(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            # 🔥 Match instantáneo → mostrar Discord
            await send_profile(user1, profile2, user2, show_discord=True)
            await send_profile(user2, profile1, user1, show_discord=True)

        else:
            target_user = await interaction.client.fetch_user(target_id)

            try:
                await target_user.send(
                    "💌 A alguien le ha gustado tu perfil.\n¿Quieres hacer match?",
                    view=LikeBackView(self.author_id)
                )
            except Exception as e:
                print(f"[ERROR] No se pudo enviar notificación: {e}")

        await self.next_profile(interaction)

    async def next_profile(self, interaction: discord.Interaction):

        self.index += 1

        if self.index >= len(self.profiles):
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

        user = await interaction.client.fetch_user(profile["user_id"])
        embed.set_thumbnail(url=user.display_avatar.url)

        await interaction.edit_original_response(
            embed=embed,
            view=self
        )


# ===============================
# COMANDO
# ===============================

async def tinder_callback(interaction: discord.Interaction):

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

    user = await interaction.client.fetch_user(first["user_id"])
    embed.set_thumbnail(url=user.display_avatar.url)

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral=True
    )


# ===============================
# EXPORTABLE
# ===============================

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)