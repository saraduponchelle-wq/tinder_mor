import discord
from discord import app_commands
import asyncpg
import os

# ===============================
# EMOJIS NORMALES (TEXTO / EMBEDS)
# ===============================

EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_INTEREST = str(os.getenv("INTEREST"))
EMOJI_LINES = str(os.getenv("LINES"))
EMOJI_STAR = str(os.getenv("STAR"))
EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))

# ===============================
# EMOJIS PARA BOTONES (PERSONALIZADOS)
# ===============================

EMOJI_BOTON_HEART = discord.PartialEmoji.from_str("<a:heart:1477738562433581338>")
EMOJI_BOTON_BROKENHEART = discord.PartialEmoji.from_str("<:brokenheart:1477739060423299202>")


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
# EMBEDS
# ===============================

def create_profile_embed(profile_data: dict, discord_user: discord.User, show_discord=False):

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Perfil de {profile_data['name']}",
        color=discord.Color.pink()
    )

    embed.add_field(
        name=f"{EMOJI_INTEREST} Intereses",
        value=", ".join(profile_data["interests"] or ["Ninguno"]),
        inline=False
    )

    embed.add_field(
        name=f"{EMOJI_LINES} Líneas",
        value=profile_data["lines"] or "Sin líneas",
        inline=False
    )

    embed.add_field(
        name=f"{EMOJI_STAR} Bio",
        value=profile_data["description"] or "Sin descripción",
        inline=False
    )

    embed.set_thumbnail(url=discord_user.display_avatar.url)

    if show_discord:
        embed.add_field(
            name="👤 Usuario de Discord",
            value=discord_user.mention,
            inline=False
        )

    return embed


# ===============================
# ENVIAR MATCH FINAL
# ===============================

async def send_match(user: discord.User, profile_data: dict, other_user: discord.User):
    embed = create_profile_embed(profile_data, other_user, show_discord=True)
    embed.title = f"{EMOJI_HEART} ¡Has hecho match con {profile_data['name']}!"
    await user.send(embed=embed)


# ===============================
# BOTONES LIKE BACK
# ===============================

class TinderView(discord.ui.View):

    def __init__(self, profiles, author_id):
        super().__init__(timeout=900)
        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    # ---------------------------
    # BOTÓN ATRÁS (GRIS)
    # ---------------------------
    @discord.ui.button(
        label="Atrás",
        style=discord.ButtonStyle.secondary
    )
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        # Si está en el primero, vuelve al último
        if self.index == 0:
            self.index = len(self.profiles) - 1
        else:
            self.index -= 1

        await self.update_profile(interaction)

    # ---------------------------
    # PASS
    # ---------------------------
    @discord.ui.button(
        label="Pass",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_BOTON_BROKENHEART
    )
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()
        await self.next_profile(interaction)

    # ---------------------------
    # LIKE
    # ---------------------------
    @discord.ui.button(
        label="Like",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_BOTON_HEART
    )
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        target_id = self.profiles[self.index]["user_id"]
        await add_match(self.author_id, target_id)

        if await is_mutual_match(self.author_id, target_id):

            user1 = await interaction.client.fetch_user(self.author_id)
            user2 = await interaction.client.fetch_user(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)

        else:
            target_user = await interaction.client.fetch_user(target_id)
            liker_user = await interaction.client.fetch_user(self.author_id)

            profile_liker = await get_full_profile(self.author_id)

            embed = create_profile_embed(profile_liker, liker_user, show_discord=False)
            embed.title = f"{EMOJI_GOLDNOTI} A alguien le ha gustado tu perfil"

            try:
                await target_user.send(
                    embed=embed,
                    view=LikeBackView(self.author_id)
                )
            except Exception as e:
                print(f"[ERROR] No se pudo enviar notificación: {e}")

        await self.next_profile(interaction)

    # ---------------------------
    # SIGUIENTE PERFIL
    # ---------------------------
    async def next_profile(self, interaction: discord.Interaction):

        self.index += 1

        if self.index >= len(self.profiles):
            self.index = 0

        await self.update_profile(interaction)

    # ---------------------------
    # ACTUALIZAR EMBED
    # ---------------------------
    async def update_profile(self, interaction: discord.Interaction):

        profile = self.profiles[self.index]
        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user, show_discord=False)

        await interaction.edit_original_response(
            embed=embed,
            view=self
        )


# ===============================
# BOTONES LIKE BACK
# ===============================

class LikeBackView(discord.ui.View):

    def __init__(self, liker_id: int):
        super().__init__(timeout=604800)
        self.liker_id = liker_id

    @discord.ui.button(
        label="Hacer Match",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_BOTON_HEART
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        await add_match(interaction.user.id, self.liker_id)

        user1 = interaction.user
        user2 = await interaction.client.fetch_user(self.liker_id)

        profile1 = await get_full_profile(user1.id)
        profile2 = await get_full_profile(user2.id)

        await send_match(user1, profile2, user2)
        await send_match(user2, profile1, user1)

        await interaction.response.edit_message(
            content=f"{EMOJI_HEART} ¡Match realizado!",
            view=None
        )

    @discord.ui.button(
        label="Rechazar",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_BOTON_BROKENHEART
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.edit_message(
            content=f"{EMOJI_BROKENHEART} Has rechazado el like.",
            view=None
        )


# ===============================
# TINDER VIEW
# ===============================

class TinderView(discord.ui.View):

    def __init__(self, profiles, author_id):
        super().__init__(timeout=900)
        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(
        label="Atrás",
        style=discord.ButtonStyle.secondary
    )
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        if self.index == 0:
            self.index = len(self.profiles) - 1
        else:
            self.index -= 1

        await self.update_profile(interaction)

    @discord.ui.button(
        label="Pass",
        style=discord.ButtonStyle.danger,
        emoji=EMOJI_BOTON_BROKENHEART
    )
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()
        await self.next_profile(interaction)

    @discord.ui.button(
        label="Like",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_BOTON_HEART
    )
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        target_id = self.profiles[self.index]["user_id"]
        await add_match(self.author_id, target_id)

        if await is_mutual_match(self.author_id, target_id):

            user1 = await interaction.client.fetch_user(self.author_id)
            user2 = await interaction.client.fetch_user(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)

        else:
            target_user = await interaction.client.fetch_user(target_id)
            liker_user = await interaction.client.fetch_user(self.author_id)

            profile_liker = await get_full_profile(self.author_id)

            embed = create_profile_embed(profile_liker, liker_user, show_discord=False)
            embed.title = f"{EMOJI_GOLDNOTI} A alguien le ha gustado tu perfil"

            try:
                await target_user.send(
                    embed=embed,
                    view=LikeBackView(self.author_id)
                )
            except Exception as e:
                print(f"[ERROR] No se pudo enviar notificación: {e}")

        await self.next_profile(interaction)

    async def next_profile(self, interaction: discord.Interaction):

        self.index += 1

        if self.index >= len(self.profiles):
            self.index = 0

        await self.update_profile(interaction)

    async def update_profile(self, interaction: discord.Interaction):

        profile = self.profiles[self.index]
        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user, show_discord=False)

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

    user = await interaction.client.fetch_user(first["user_id"])
    embed = create_profile_embed(first, user, show_discord=False)

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral=True
    )


# ===============================
# EXPORTABLE COMMAND
# ===============================

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)