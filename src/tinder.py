import discord
from discord import app_commands
import asyncpg
import os
from src.blog_viewer import BlogViewer


# ==========================================================
# EMOJIS
# ==========================================================

EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_INTEREST = str(os.getenv("INTEREST"))
EMOJI_LINES = str(os.getenv("LINES"))
EMOJI_STAR = str(os.getenv("STAR"))
EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))

LIKES_STAT = str(os.getenv("LIKES_STAT"))
MATCHES_STAT = str(os.getenv("MATCHES_STAT"))
POPULARITY_STAT = str(os.getenv("POPULARITY_STAT"))

EMOJI_BOTON_HEART = discord.PartialEmoji.from_str("<a:heart:1477738562433581338>")
EMOJI_BOTON_BROKENHEART = discord.PartialEmoji.from_str("<:brokenheart:1477739060423299202>")


# ===============================
# STATS HELPERS
# ===============================

async def add_like(target_id: int):
    """Primer like recibido"""
    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET likes = COALESCE(likes,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


async def add_match_stat(user1: int, user2: int):
    """Añade match a ambos"""

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET matches_nb = COALESCE(matches_nb,0) + 1 WHERE user_id=$1",
        user1
    )

    await conn.execute(
        "UPDATE profiles SET matches_nb = COALESCE(matches_nb,0) + 1 WHERE user_id=$1",
        user2
    )

    await conn.close()



async def add_popularity(target_id: int):
    """Extras: likes repetidos o coucou"""
    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET popularity = COALESCE(popularity,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


# ==========================================================
# DATABASE HELPERS
# ==========================================================

async def get_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return await asyncpg.connect(DATABASE_URL)


async def get_profiles(exclude_user_id: int):

    conn = await get_connection()

    rows = await conn.fetch("""
        SELECT user_id, name, interests, lines, description, matches,
           profile_image, banner_image,
           likes, matches_nb, popularity, active
        FROM profiles
        WHERE user_id != $1
        AND NOT ($1 = ANY(block))
        AND NOT (user_id = ANY(
            SELECT UNNEST(block) FROM profiles WHERE user_id = $1
        ))
        ORDER BY active DESC, popularity DESC, matches DESC
    """, exclude_user_id)

    await conn.close()
    return rows


async def block_user(user_id: int, target_id: int):

    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT block FROM profiles WHERE user_id=$1",
        user_id
    )

    blocks = row["block"] or []

    if target_id not in blocks:
        blocks.append(target_id)

        await conn.execute(
            "UPDATE profiles SET block=$1 WHERE user_id=$2",
            blocks,
            user_id
        )

    await conn.close()


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


# ==========================================================
# EMBEDS
# ==========================================================

def create_profile_embed(profile_data: dict, discord_user: discord.User, show_discord=False):

    status = "🟢" if profile_data.get("active") else "🔴"

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Perfil de {profile_data['name']} {status}",
        color=discord.Color.pink()
    )

    # -------------------------
    # INTERESES
    # -------------------------

    embed.add_field(
        name=f"{EMOJI_INTEREST} Intereses",
        value=", ".join(profile_data.get("interests") or ["Ninguno"]),
        inline=False
    )

    # -------------------------
    # LÍNEAS
    # -------------------------

    embed.add_field(
        name=f"{EMOJI_LINES} Líneas",
        value=profile_data.get("lines") or "Sin líneas",
        inline=False
    )

    # -------------------------
    # BIO
    # -------------------------

    embed.add_field(
        name=f"{EMOJI_STAR} Bio",
        value=profile_data.get("description") or "Sin descripción",
        inline=False
    )

    # -------------------------
    # IMÁGENES
    # -------------------------

    profile_image = profile_data.get("profile_image")
    banner_image = profile_data.get("banner_image")

    if profile_image:
        embed.set_thumbnail(url=profile_image)
    else:
        embed.set_thumbnail(url=discord_user.display_avatar.url)

    if banner_image:
        embed.set_image(url=banner_image)

    # -------------------------
    # DISCORD USER
    # -------------------------

    if show_discord:
        embed.add_field(
            name="👤 Usuario de Discord",
            value=discord_user.mention,
            inline=False
        )

    # -------------------------
    # STATS
    # -------------------------

    likes = profile_data.get("likes", 0)
    matches = profile_data.get("matches_nb", 0)
    popularity = profile_data.get("popularity", 0)

    total_popularity = likes + matches + popularity

    embed.add_field(
        name=f"{POPULARITY_STAT} Popularity",
        value=total_popularity,
        inline=True
    )

    embed.add_field(
        name=f"{LIKES_STAT} Likes",
        value=likes,
        inline=True
    )

    embed.add_field(
        name=f"{MATCHES_STAT} Matches",
        value=matches,
        inline=True
    )

    return embed


# ==========================================================
# VIEWS
# ==========================================================

class BlockView(discord.ui.View):

    def __init__(self, target_id: int):
        super().__init__(timeout=604800)
        self.target_id = target_id

    @discord.ui.button(label="Bloquear", style=discord.ButtonStyle.danger)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):

        await block_user(interaction.user.id, self.target_id)

        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.",
            view=None
        )


class MatchView(discord.ui.View):

    def __init__(self, profile_data, discord_user):
        super().__init__(timeout=604800)
        self.profile_data = profile_data
        self.discord_user = discord_user

    @discord.ui.button(label="Blogs", style=discord.ButtonStyle.primary)
    async def blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = create_profile_embed(
            self.profile_data,
            self.discord_user,
            show_discord=True
        )

        viewer = BlogViewer(self.discord_user, embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "Este usuario no tiene blogs.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            embed=viewer.create_embed(),
            view=viewer
        )

    @discord.ui.button(label="Bloquear", style=discord.ButtonStyle.danger)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):

        await block_user(interaction.user.id, self.discord_user.id)

        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.",
            view=None
        )


class LikeBackView(discord.ui.View):

    def __init__(self, liker_id: int, profile_data: dict, discord_user: discord.User):

        super().__init__(timeout=604800)

        self.liker_id = liker_id
        self.profile_data = profile_data
        self.discord_user = discord_user

    @discord.ui.button(
        label="Hacer Match",
        style=discord.ButtonStyle.success,
        emoji=EMOJI_BOTON_HEART
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        await add_match(interaction.user.id, self.liker_id)
        await add_like(self.liker_id)
        await add_match_stat(interaction.user.id, self.liker_id)

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


# ==========================================================
# MENSAJES
# ==========================================================

async def send_match(user: discord.User, profile_data: dict, other_user: discord.User):

    embed = create_profile_embed(profile_data, other_user, show_discord=True)

    embed.title = f"{EMOJI_HEART} ¡Has hecho match con {profile_data['name']}!"

    await user.send(
        embed=embed,
        view=MatchView(profile_data, other_user)
    )


async def send_coucou(user: discord.User, other_user: discord.User):

    embed = discord.Embed(
        title="👋 Coucou",
        description=f"{other_user.mention} te hace un pequeño coucou.",
        color=discord.Color.pink()
    )

    await user.send(
        embed=embed,
        view=BlockView(other_user.id)
    )


# ==========================================================
# TINDER VIEW
# ==========================================================

class TinderView(discord.ui.View):

    def __init__(self, profiles, author_id):

        super().__init__(timeout=900)

        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    async def next_profile(self, interaction: discord.Interaction):

        self.index += 1

        if self.index >= len(self.profiles):
            self.index = 0

        await self.update_profile(interaction)

    async def update_profile(self, interaction: discord.Interaction):

        profile = self.profiles[self.index]

        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user)

        await interaction.edit_original_response(
            embed=embed,
            view=self
        )

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.danger, emoji=EMOJI_BOTON_BROKENHEART)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()
        await self.next_profile(interaction)

    @discord.ui.button(label="Like", style=discord.ButtonStyle.success, emoji=EMOJI_BOTON_HEART)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        target_id = self.profiles[self.index]["user_id"]

        already_match = await is_mutual_match(self.author_id, target_id)

        await add_match(self.author_id, target_id)
        await add_like(target_id)

        user1 = await interaction.client.fetch_user(self.author_id)
        user2 = await interaction.client.fetch_user(target_id)

        profile1 = await get_full_profile(user1.id)
        profile2 = await get_full_profile(user2.id)

        if already_match:
            await send_coucou(user2, user1)
            await add_popularity(target_id)


        elif await is_mutual_match(self.author_id, target_id):

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)
            await add_match_stat(user1.id, user2.id)

        else:

            embed = create_profile_embed(profile1, user1)
            embed.title = f"{EMOJI_GOLDNOTI} A alguien le ha gustado tu perfil"

            try:
                await user2.send(
                    embed=embed,
                    view=LikeBackView(self.author_id, profile1, user1)
                )
            except Exception as e:
                print(f"[ERROR] No se pudo enviar notificación: {e}")

        await self.next_profile(interaction)

    @discord.ui.button(label="Atrás", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        if self.index == 0:
            self.index = len(self.profiles) - 1
        else:
            self.index -= 1

        await self.update_profile(interaction)

    @discord.ui.button(label="Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        profile = self.profiles[self.index]
        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user)

        viewer = BlogViewer(user, embed, self)
        await viewer.load()

        # SI NO TIENE BLOGS
        if not viewer.blogs:

            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.",
                ephemeral=True
            )

            return

        # SI TIENE BLOGS
        await interaction.response.edit_message(
            embed=viewer.create_embed(),
            view=viewer
        )




# ==========================================================
# COMANDO
# ==========================================================

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

    embed = create_profile_embed(first, user)

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral=True
    )


# ==========================================================
# EXPORTABLE COMMAND
# ==========================================================

tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)
