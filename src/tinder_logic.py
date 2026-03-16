import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")


async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


async def add_like(target_id: int):

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET likes = COALESCE(likes,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


async def add_popularity(target_id: int):

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET popularity = COALESCE(popularity,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


async def add_match_stat(user1: int, user2: int):

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

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id=$1",
        user_id
    )

    await conn.close()

    return dict(row)


import discord
from embed.create_profile import create_profile_embed


async def send_match(user: discord.User, profile_data: dict, other_user: discord.User):

    embed = create_profile_embed(profile_data, other_user, show_discord=True)

    embed.title = f"❤️ ¡Has hecho match con {profile_data['name']}!"

    await user.send(embed=embed)


async def send_coucou(user: discord.User, other_user: discord.User):

    embed = discord.Embed(
        title="👋 Coucou",
        description=f"{other_user.mention} te saluda.",
        color=discord.Color.pink()
    )

    await user.send(embed=embed)


class LikeBackView(discord.ui.View):
    
    def __init__(self, liker_id: int, profile_data: dict, discord_user: discord.User):
    
        super().__init__(timeout=604800)
    
        self.liker_id = liker_id
        self.profile_data = profile_data
        self.discord_user = discord_user
    
    # ❤️ LIKE BACK
    @discord.ui.button(label="❤️ Like Back", style=discord.ButtonStyle.success)
    async def like_back(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        await add_match(interaction.user.id, self.liker_id)
    
        await interaction.response.edit_message(
            content="❤️ ¡Has devuelto el like!",
            view=None
        )
    
    # ❌ RECHAZAR
    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        await interaction.response.edit_message(
            content="💔 Has rechazado el like.",
            view=None
        )
    
    # 📖 VER BLOGS
    @discord.ui.button(label="📖 Ver Blogs", style=discord.ButtonStyle.secondary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        from src.blog_viewer import BlogViewer
    
        viewer = BlogViewer(self.discord_user)
    
        await viewer.load()
    
        if not viewer.blogs:
    
            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.",
                ephemeral=True
            )
    
            return
    
        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )
    
    # 🚫 BLOQUEAR
    @discord.ui.button(label="🚫 Bloquear", style=discord.ButtonStyle.danger)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        conn = await get_connection()
    
        await conn.execute(
            """
            UPDATE profiles
            SET block = array_append(block, $1)
            WHERE user_id = $2
            """,
            self.liker_id,
            interaction.user.id
        )
    
        await conn.close()
    
        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.",
            view=None
        )