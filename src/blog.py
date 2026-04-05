# src/blog.py

import discord
from discord import app_commands
import asyncio
import os
import asyncpg

from src.blog_db import add_blog
from src.blog_notifications import get_users_with_news_enabled
from src.server_db import get_all_servers
from embed.create_profile import create_profile_embed

from src.tinder_logic import (
    add_match,
    add_like,
    add_match_stat,
    add_popularity,
    send_match,
)

from src.tinder import get_full_profile

DATABASE_URL = os.getenv("DATABASE_URL")

BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

EMOJI_NOTI = str(os.getenv("NOTI"))
EMOJI_MES  = str(os.getenv("MES"))
EMOJI_YES  = str(os.getenv("YES"))
EMOJI_NO   = str(os.getenv("NO"))


async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


# ==========================================================
# BLOG IMAGE BUTTON / MODAL  (sin cambios)
# ==========================================================

class BlogImageButtonView(discord.ui.View):
    def __init__(self, author: discord.User, blog_text: str):
        super().__init__(timeout=None)
        self.author    = author
        self.blog_text = blog_text

    @discord.ui.button(label="Añadir imagen", style=discord.ButtonStyle.primary)
    async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"{EMOJI_NO} Solo el autor puede usar este botón.", ephemeral=True
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
        max_length=2000,
    )

    def __init__(self, author: discord.User, blog_text: str):
        super().__init__()
        self.author    = author
        self.blog_text = blog_text

    async def on_submit(self, interaction: discord.Interaction):
        image_url = self.image_url_input.value.strip()
        await interaction.response.send_message(
            f"{EMOJI_YES} Blog enviado para revisión.", ephemeral=True
        )
        await post_blog_for_review(
            interaction.client, self.author, self.blog_text, image_url
        )


# ==========================================================
# VISTA QUE RECIBE EL DUEÑO DEL BLOG  (Casos 1 y 3)
# ==========================================================

class ProfileOwnerNotifView(discord.ui.View):
    """
    Notificación que llega al DUEÑO del blog cuando alguien
    pulsa "Me interesa".

    Caso 1 (ya son match):
        Botón "Me interesa" → avisa al liker para que vaya a hablarle.

    Caso 3 (like normal):
        Botón "Hacer Match" → match automático, ambos reciben mensaje de match.
    """

    def __init__(
        self,
        liker: discord.User,
        liker_profile: dict,
        owner: discord.User,
        already_matched: bool,
    ):
        super().__init__(timeout=604800)
        self.liker           = liker
        self.liker_profile   = liker_profile
        self.owner           = owner
        self.already_matched = already_matched

        # Etiqueta dinámica según el caso
        if already_matched:
            label  = "💬 Me interesa"
            style  = discord.ButtonStyle.secondary
        else:
            label  = "💞 Hacer Match"
            style  = discord.ButtonStyle.success

        btn = discord.ui.Button(label=label, style=style)
        btn.callback = self._action_callback
        self.add_item(btn)

    async def _action_callback(self, interaction: discord.Interaction):
        # Solo el dueño del blog puede pulsar
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                f"{EMOJI_NO} Este botón no es para ti.", ephemeral=True
            )
            return

        await interaction.response.defer()

        owner_profile = await get_full_profile(self.owner.id)
        liker_profile = await get_full_profile(self.liker.id)

        # ── CASO 1: ya son match → solo avisa al liker ──────────────
        if self.already_matched:
            try:
                await self.liker.send(
                    f"💬 **{self.owner.display_name}** también está interesad@ en ti. "
                    f"¡Ve a hablarle! → {self.owner.mention}"
                )
            except Exception as e:
                print(f"[WARN] No se pudo avisar al liker: {e}")

            await interaction.edit_original_response(
                content="💬 Le hemos avisado para que te escriba.",
                view=None,
                embed=None,
            )

        # ── CASO 3: like normal → hacer match ───────────────────────
        else:
            await add_match(self.owner.id, self.liker.id)
            await add_match_stat(self.owner.id, self.liker.id)

            await send_match(self.owner, liker_profile, self.liker)
            await send_match(self.liker, owner_profile, self.owner)

            await interaction.edit_original_response(
                content="💞 ¡Match! Ambos han sido notificados.",
                view=None,
                embed=None,
            )

    # Botón "Ver Blogs" del liker
    @discord.ui.button(label="📖 Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.blog_viewer import BlogViewer
        embed  = create_profile_embed(self.liker_profile, self.liker)
        viewer = BlogViewer(self.liker, embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(), view=viewer, ephemeral=True
        )

    # Botón "Bloquear"
    @discord.ui.button(label="🚫 Bloquear", style=discord.ButtonStyle.secondary)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = await get_connection()
        await conn.execute(
            "UPDATE profiles SET block = array_append(block, $1) WHERE user_id = $2",
            self.liker.id,
            interaction.user.id,
        )
        await conn.close()
        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.", view=None, embed=None
        )


# ==========================================================
# BOTÓN "ME INTERESA" DEL BLOG  (lo que ve cualquier lector)
# ==========================================================

class BlogLikeView(discord.ui.View):
    """
    Vista adjunta al embed del blog en el canal o en DM.
    Quien pulsa "Me interesa" es el LIKER.
    El OWNER es el autor del blog.
    """

    def __init__(self, author: discord.User):
        super().__init__(timeout=None)
        self.author = author

    @discord.ui.button(label="❤️ Me interesa", style=discord.ButtonStyle.success)
    async def like_blog(self, interaction: discord.Interaction, button: discord.ui.Button):

        liker = interaction.user
        owner = self.author

        # No puedes interactuar contigo mismo
        if liker.id == owner.id:
            await interaction.response.send_message(
                "❌ No puedes interactuar contigo mismo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        liker_profile = await get_full_profile(liker.id)
        owner_profile = await get_full_profile(owner.id)

        if liker_profile is None or owner_profile is None:
            await interaction.followup.send(
                "❌ Uno de los dos no tiene perfil.", ephemeral=True
            )
            return

        # Bloqueos
        if owner.id in (liker_profile.get("block") or []) or \
           liker.id in (owner_profile.get("block") or []):
            await interaction.followup.send("🚫 Usuario bloqueado.", ephemeral=True)
            return

        liker_matches = liker_profile.get("matches") or []
        owner_matches = owner_profile.get("matches") or []

        already_matched  = owner.id in liker_matches and liker.id in owner_matches
        owner_liked_liker = liker.id in owner_matches   # el dueño ya le dio like antes

        embed_liker = create_profile_embed(liker_profile, liker)

        # ── CASO 2: el dueño ya le dio like → match automático ──────
        if not already_matched and owner_liked_liker:

            await add_match(liker.id, owner.id)
            await add_match_stat(liker.id, owner.id)

            await send_match(liker, owner_profile, owner)
            await send_match(owner, liker_profile, liker)

            await interaction.followup.send("💞 ¡Match!", ephemeral=True)
            return

        # ── CASO 1: ya son match → notifica al dueño ────────────────
        if already_matched:

            await add_popularity(owner.id)

            try:
                await owner.send(
                    content=f"💖 Tu amig@ **{liker.display_name}** está interesad@ en tu blog",
                    embed=embed_liker,
                    view=ProfileOwnerNotifView(
                        liker=liker,
                        liker_profile=liker_profile,
                        owner=owner,
                        already_matched=True,
                    ),
                )
            except Exception as e:
                print(f"[WARN] DM caso 1 fallido: {e}")

            await interaction.followup.send(
                "💬 Ya eran match. ¡Le hemos avisado!", ephemeral=True
            )
            return

        # ── CASO 3: like normal → registrar y notificar al dueño ────
        await add_match(liker.id, owner.id)
        await add_like(owner.id)

        try:
            await owner.send(
                content=f"📢 Alguien está interesad@ en tu blog",
                embed=embed_liker,
                view=ProfileOwnerNotifView(
                    liker=liker,
                    liker_profile=liker_profile,
                    owner=owner,
                    already_matched=False,
                ),
            )
        except Exception as e:
            print(f"[WARN] DM caso 3 fallido: {e}")

        await interaction.followup.send("❤️ Interés enviado.", ephemeral=True)


# ==========================================================
# PUBLICACIÓN Y REVISIÓN DEL BLOG  (sin cambios de lógica)
# ==========================================================

async def post_blog_for_review(client, author, blog_text, image_url):

    channel = client.get_channel(BLOG_REVIEW_CHANNEL_ID)
    if not channel:
        print("[ERROR] Canal de revisión no encontrado")
        return

    embed = discord.Embed(
        title=f"{EMOJI_NOTI} Nuevo Blog de {author.display_name}",
        description=blog_text,
        color=discord.Color.red(),
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

    # Publicar en canales de servidores
    servers = await get_all_servers()
    for server in servers:
        channel_id = server["blog_channel_id"]
        if not channel_id:
            continue
        blog_channel = client.get_channel(channel_id)
        if blog_channel:
            await blog_channel.send(embed=embed, view=BlogLikeView(author))

    # Enviar a usuarios con news activado
    user_ids = await get_users_with_news_enabled()
    for user_id in user_ids:
        try:
            u = await client.fetch_user(user_id)
            await u.send(embed=embed, view=BlogLikeView(author))
            await u.send(f"{EMOJI_MES} Si estás interesado, escríbele a {author.mention}")
        except Exception as e:
            print(f"[ERROR] No se pudo enviar DM {user_id}: {e}")

    await add_blog(author.id, blog_text, image_url or "nothing")


# ==========================================================
# MODAL DE TEXTO Y COMANDO  (sin cambios)
# ==========================================================

class BlogTextModal(discord.ui.Modal, title="Escribe tu blog"):
    blog_text_input = discord.ui.TextInput(
        label="Texto del blog",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe tu contenido aquí...",
        required=True,
        max_length=4000,
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
            ephemeral=True,
        )


async def crearblog_callback(interaction: discord.Interaction):
    await interaction.response.send_modal(BlogTextModal(interaction.user))


blog = app_commands.Command(
    name="blog",
    description="Crea un blog",
    callback=crearblog_callback,
)