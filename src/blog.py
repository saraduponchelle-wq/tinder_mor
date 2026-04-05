import discord
from discord import app_commands
import asyncio
import os
import asyncpg

from src.blog_db import add_blog
from src.blog_notifications import get_users_with_news_enabled
from src.server_db import get_all_servers
from embed.create_profile import create_profile_embed
from src.nsfw_check import check_nsfw

from src.tinder_logic import (
    add_match,
    add_like,
    add_match_stat,
    add_popularity,
    is_mutual_match,
    send_match,
    send_coucou
)

from src.tinder import get_full_profile

DATABASE_URL = os.getenv("DATABASE_URL")

BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

EMOJI_NOTI = str(os.getenv("NOTI"))
EMOJI_MES = str(os.getenv("MES"))
EMOJI_YES = str(os.getenv("YES"))
EMOJI_NO = str(os.getenv("NO"))


async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


class BlogImageButtonView(discord.ui.View):

    def __init__(self, author: discord.User, blog_text: str):
        super().__init__(timeout=None)
        self.author = author
        self.blog_text = blog_text

    @discord.ui.button(
        label="Añadir imagen",
        style=discord.ButtonStyle.primary
    )
    async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"{EMOJI_NO} Solo el autor puede usar este botón.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            BlogImageModal(self.author, self.blog_text)
        )


class BlogImageModal(discord.ui.Modal, title="Añadir URL de la imagen"):

    image_url_input = discord.ui.TextInput(
        label="URL de la imagen",
        style=discord.TextStyle.short,
        placeholder="https://ejemplo.com/imagen.png",
        required=True,
        max_length=2000
    )

    def __init__(self, author: discord.User, blog_text: str):
        super().__init__()
        self.author = author
        self.blog_text = blog_text

    async def on_submit(self, interaction: discord.Interaction):

        image_url = self.image_url_input.value.strip()

        await interaction.response.send_message(
            f"{EMOJI_YES} Blog enviado para revisión.",
            ephemeral=True
        )

        await post_blog_for_review(
            interaction.client,
            self.author,
            self.blog_text,
            image_url
        )


# ==========================================================
# VIEW INTERÉS (DM AL AUTOR)
# ==========================================================

class BlogInterestView(discord.ui.View):

    def __init__(self, liker_id, profile_data, discord_user, already_matched, liked_you):
        super().__init__(timeout=604800)

        self.liker_id = liker_id
        self.profile_data = profile_data
        self.discord_user = discord_user
        self.already_matched = already_matched
        self.liked_you = liked_you

        self.add_item(self.create_action_button())

    def create_action_button(self):

        if self.already_matched:
            label = "❤️ Me interesa"
            style = discord.ButtonStyle.secondary
            custom_id = "like"

        elif self.liked_you:
            label = "💞 Hacer Match"
            style = discord.ButtonStyle.success
            custom_id = "match"

        else:
            label = "❤️ Me interesa"
            style = discord.ButtonStyle.secondary
            custom_id = "like"

        button = discord.ui.Button(label=label, style=style, custom_id=custom_id)

        async def callback(interaction: discord.Interaction):

            user = interaction.user
            other = self.discord_user

            profile1 = await get_full_profile(user.id)
            profile2 = await get_full_profile(other.id)

            if custom_id == "match":

                await add_match(user.id, self.liker_id)

                await send_match(user, profile2, other)
                await send_match(other, profile1, user)

                await add_match_stat(user.id, other.id)

                await interaction.response.send_message("💞 ¡Match!", ephemeral=True)

            else:

                await add_match(user.id, self.liker_id)
                await add_like(self.liker_id)

                try:
                    embed = create_profile_embed(profile1, user)

                    await other.send(
                        content=f"💌 {user.mention} está interesado en ti",
                        embed=embed,
                        view=BlogInterestView(
                            user.id,
                            profile1,
                            user,
                            already_matched=False,
                            liked_you=True
                        )
                    )
                except:
                    pass

                await interaction.response.send_message("❤️ Interés enviado.", ephemeral=True)

        button.callback = callback
        return button

    @discord.ui.button(label="Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        from src.blog_viewer import BlogViewer

        embed = create_profile_embed(self.profile_data, self.discord_user)

        viewer = BlogViewer(self.discord_user, embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message("📭 Este usuario no tiene blogs.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )

    @discord.ui.button(label="🚫 Bloquear", style=discord.ButtonStyle.secondary)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):

        conn = await get_connection()

        await conn.execute(
            "UPDATE profiles SET block = array_append(block, $1) WHERE user_id = $2",
            self.liker_id,
            interaction.user.id
        )

        await conn.close()

        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.",
            view=None
        )


# ==========================================================
# BOTÓN LIKE DEL BLOG
# ==========================================================

class BlogLikeView(discord.ui.View):

    def __init__(self, author: discord.User):
        super().__init__(timeout=None)
        self.author = author

    @discord.ui.button(label="❤️ Me interesa", style=discord.ButtonStyle.success)
    async def like_blog(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.user
        author = self.author

        if user.id == author.id:
            await interaction.response.send_message("❌ No puedes interactuar contigo mismo.", ephemeral=True)
            return

        profile_user = await get_full_profile(user.id)
        profile_author = await get_full_profile(author.id)

        if author.id in (profile_user.get("block") or []) or user.id in (profile_author.get("block") or []):
            await interaction.response.send_message("🚫 Usuario bloqueado.", ephemeral=True)
            return

        author_matches = profile_author.get("matches") or []
        user_matches = profile_user.get("matches") or []

        already_matched = author.id in user_matches and user.id in author_matches
        author_liked_user = user.id in author_matches

        profile1 = await get_full_profile(user.id)
        profile2 = await get_full_profile(author.id)

        embed = create_profile_embed(profile1, user)
        embed.title = "💌 Interés en tu blog"

        if not already_matched and author_liked_user:

            await add_match(user.id, author.id)

            await send_match(user, profile2, author)
            await send_match(author, profile1, user)

            await add_match_stat(user.id, author.id)

            msg = f"💖 {user.mention} hizo match contigo y le encantó tu blog"

            await interaction.response.send_message("💞 ¡Match!", ephemeral=True)

        elif already_matched:

            await add_popularity(author.id)

            msg = f"💖 {user.mention} volvió a interesarse en tu blog"

            await interaction.response.send_message("💬 Ya eran match.", ephemeral=True)

        else:

            await add_match(user.id, author.id)
            await add_like(author.id)

            msg = f"📢 {user.mention} está interesado en tu blog"

            await interaction.response.send_message("❤️ Interés enviado.", ephemeral=True)

        try:
            await author.send(
                content=msg,
                embed=embed,
                view=BlogInterestView(
                    user.id,
                    profile1,
                    user,
                    already_matched,
                    author_liked_user
                )
            )
        except Exception as e:
            print(f"[ERROR] DM blog like: {e}")


# ==========================================================
# PUBLICAR BLOG (REVISIÓN → CANALES +18 → DMs)
# ==========================================================

async def post_blog_for_review(client, author, blog_text, image_url):

    channel = client.get_channel(BLOG_REVIEW_CHANNEL_ID)

    if not channel:
        print("[ERROR] Canal de revisión no encontrado")
        return

    embed = discord.Embed(
        title=f"{EMOJI_NOTI} Nuevo Blog de {author.display_name}",
        description=blog_text,
        color=discord.Color.red()
    )

    if image_url:
        embed.set_image(url=image_url)

    msg = await channel.send(embed=embed)
    await msg.add_reaction("👍")

    def check(reaction, user):
        return reaction.message.id == msg.id and str(reaction.emoji) == "👍"

    try:
        await client.wait_for("reaction_add", timeout=28800, check=check)
    except asyncio.TimeoutError:
        return

    servers = await get_all_servers()

    for server in servers:
        channel_id = server["blog_channel_id"]
        if not channel_id:
            continue

        blog_channel = client.get_channel(channel_id)

        if not blog_channel:
            continue

        # 🔞 Solo publicar si el canal es NSFW
        if not getattr(blog_channel, "nsfw", False):
            print(f"[WARN] Canal {channel_id} no es NSFW, se omite.")
            continue

        view = BlogLikeView(author)

        await blog_channel.send(embed=embed, view=view)

    user_ids = await get_users_with_news_enabled()

    for user_id in user_ids:
        try:
            u = await client.fetch_user(user_id)

            await u.send(
                embed=embed,
                view=BlogLikeView(author)
            )

            await u.send(
                f"{EMOJI_MES} Si estás interesado, escríbele a {author.mention}"
            )

        except Exception as e:
            print(f"[ERROR] No se pudo enviar DM {user_id}: {e}")

    await add_blog(author.id, blog_text, image_url or "nothing")


# ==========================================================
# MODAL TEXTO DEL BLOG
# ==========================================================

class BlogTextModal(discord.ui.Modal, title="Escribe tu blog"):

    blog_text_input = discord.ui.TextInput(
        label="Texto del blog",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe tu contenido aquí...",
        required=True,
        max_length=4000
    )

    def __init__(self, author):
        super().__init__()
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):

        blog_text = self.blog_text_input.value.strip()

        view = BlogImageButtonView(self.author, blog_text)

        await interaction.response.send_message(
            f"{EMOJI_YES} Texto recibido. ¿Quieres añadir una imagen?",
            view=view,
            ephemeral=True
        )


async def crearblog_callback(interaction: discord.Interaction):

    if not await check_nsfw(interaction):
        return

    await interaction.response.send_modal(BlogTextModal(interaction.user))


blog = app_commands.Command(
    name="blog",
    description="Crea un blog",
    callback=crearblog_callback
)
