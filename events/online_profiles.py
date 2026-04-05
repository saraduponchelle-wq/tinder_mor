import discord
import asyncio
import asyncpg
import os
from discord.ext import tasks

from src.blog_viewer import BlogViewer
from src.server_db import get_all_servers
from embed.create_profile import create_profile_embed
from src.tinder_logic import (
    get_full_profile,
    add_like,
    add_match,
    add_match_stat,
    add_popularity,
    is_mutual_match,
    send_match,
    send_coucou,
    LikeBackView
)

EMOJI_BOTON_HEART = discord.PartialEmoji.from_str("<a:heart:1477738562433581338>")
EMOJI_BOTON_BROKENHEART = discord.PartialEmoji.from_str("<:brokenheart:1477739060423299202>")

DATABASE_URL = os.getenv("DATABASE_URL")


# ==========================================================
# VISTA: NOTIFICACIÓN AL AUTOR DEL PERFIL (recibe el like)
# ==========================================================
# Esta vista se envía por DM al dueño del perfil cuando alguien
# le da like desde el canal online. Tiene 2 variantes:
#   - already_match=True  → botón "Me interesa" (ya son match)
#   - already_match=False → botón "Hacer Match"

class ProfileOwnerNotifView(discord.ui.View):
    """
    Vista que recibe el DUEÑO del perfil cuando alguien
    le da like desde el canal de online.
    """

    def __init__(self, liker: discord.User, liker_profile: dict, already_match: bool):
        super().__init__(timeout=604800)  # 7 días
        self.liker = liker
        self.liker_profile = liker_profile
        self.already_match = already_match

    # ----------------------------------------------------------
    # BOTÓN PRINCIPAL: "Hacer Match" o "Me interesa"
    # ----------------------------------------------------------
    @discord.ui.button(label="💞 Hacer Match", style=discord.ButtonStyle.success)
    async def action_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        owner = interaction.user
        liker = self.liker

        owner_profile = await get_full_profile(owner.id)
        liker_profile = await get_full_profile(liker.id)

        if self.already_match:
            # Ya eran match → solo notificar al liker que el owner está interesado
            await add_popularity(liker.id)

            try:
                embed = create_profile_embed(owner_profile, owner)
                embed.title = "💬 Tu amig@ está interesad@ en tu blog"

                await liker.send(
                    content=f"💬 {owner.mention} está interesad@ en ti, ¡ya podéis hablar!",
                    embed=embed
                )
            except Exception as e:
                print(f"⚠️ No se pudo notificar al liker: {e}")

            await interaction.response.edit_message(
                content="💬 Notificación enviada.",
                view=None
            )

        else:
            # No eran match → hacer match ahora
            await add_match(owner.id, liker.id)

            await send_match(owner, liker_profile, liker)
            await send_match(liker, owner_profile, owner)
            await add_match_stat(owner.id, liker.id)

            await interaction.response.edit_message(
                content="💞 ¡Match realizado!",
                view=None
            )

    # ----------------------------------------------------------
    # BLOGS
    # ----------------------------------------------------------
    @discord.ui.button(label="📖 Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = create_profile_embed(self.liker_profile, self.liker)
        viewer = BlogViewer(self.liker, embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )

    # ----------------------------------------------------------
    # BLOQUEAR
    # ----------------------------------------------------------
    @discord.ui.button(label="🚫 Bloquear", style=discord.ButtonStyle.secondary)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):

        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute(
            "UPDATE profiles SET block = array_append(block, $1) WHERE user_id = $2",
            self.liker.id,
            interaction.user.id
        )
        await conn.close()

        await interaction.response.edit_message(
            content="🚫 Usuario bloqueado.",
            view=None
        )

    async def on_timeout(self):
        pass  # no hacer nada al expirar


# ==========================================================
# VISTA: NOTIFICACIÓN AL LIKER (ya son match, recibe interés)
# ==========================================================
# Se envía al que dio el like cuando el dueño del perfil
# (con quien ya hay match) pulsa "Me interesa".

class LikerNotifView(discord.ui.View):
    """
    Vista que recibe el LIKER cuando el dueño de un perfil
    (con quien ya son match) pulsa "Me interesa".
    """

    def __init__(self, owner: discord.User, owner_profile: dict):
        super().__init__(timeout=604800)
        self.owner = owner
        self.owner_profile = owner_profile

    @discord.ui.button(label="💬 Me interesa también", style=discord.ButtonStyle.success)
    async def interested(self, interaction: discord.Interaction, button: discord.ui.Button):

        await add_popularity(self.owner.id)

        await interaction.response.edit_message(
            content=f"💬 ¡Genial! Ve a hablarle a {self.owner.mention}.",
            view=None
        )

    @discord.ui.button(label="📖 Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = create_profile_embed(self.owner_profile, self.owner)
        viewer = BlogViewer(self.owner, embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )

    @discord.ui.button(label="🚫 Bloquear", style=discord.ButtonStyle.secondary)
    async def block(self, interaction: discord.Interaction, button: discord.ui.Button):

        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute(
            "UPDATE profiles SET block = array_append(block, $1) WHERE user_id = $2",
            self.owner.id,
            interaction.user.id
        )
        await conn.close()

        await interaction.response.edit_message(content="🚫 Usuario bloqueado.", view=None)


# ==========================================================
# LIKE VIEW (botones del canal online)
# ==========================================================

class LikeView(discord.ui.View):

    def __init__(self, bot, profile_data):
        super().__init__(timeout=None)
        self.bot = bot
        self.profile_data = profile_data

    # ----------------------------------------------------------
    # ❤️ LIKE
    # ----------------------------------------------------------
    @discord.ui.button(label="❤️ Like", style=discord.ButtonStyle.success)
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button):

        target_id = self.profile_data["user_id"]
        author_id = interaction.user.id

        # No puedes darte like a ti mismo
        if author_id == target_id:
            await interaction.response.send_message(
                "❌ No puedes darte like a ti mismo.", ephemeral=True
            )
            return

        # El autor necesita tener perfil
        conn = await asyncpg.connect(DATABASE_URL)
        author_row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id = $1", author_id
        )
        await conn.close()

        if not author_row:
            await interaction.response.send_message(
                "❌ Necesitas crear un perfil primero con `/start`.", ephemeral=True
            )
            return

        author_profile = dict(author_row)

        # Verificar bloqueos
        target_profile = await get_full_profile(target_id)

        author_blocked_target = target_id in (author_profile.get("block") or [])
        target_blocked_author = author_id in (target_profile.get("block") or [])

        if author_blocked_target or target_blocked_author:
            await interaction.response.send_message(
                "🚫 No puedes interactuar con este usuario.", ephemeral=True
            )
            return

        user1 = interaction.user                          # el que da like
        user2 = await self.bot.fetch_user(target_id)     # el dueño del perfil

        # Estado actual ANTES de modificar nada
        author_matches = author_profile.get("matches") or []
        target_matches = target_profile.get("matches") or []

        already_match   = (target_id in author_matches) and (author_id in target_matches)
        target_liked_me = author_id in target_matches   # el dueño ya me dio like antes

        await interaction.response.defer(ephemeral=True)

        # ==================================================
        # CASO 1: ya son match → enviar "tu amig@ está interesad@"
        # ==================================================
        if already_match:

            await add_popularity(target_id)

            try:
                embed = create_profile_embed(author_profile, user1)
                embed.title = "💬 Tu amig@ está interesad@ en tu blog"

                # Vista para el dueño: botón "Me interesa" (ya_match=True)
                await user2.send(
                    content=f"💬 {user1.mention} está interesad@ en ti.",
                    embed=embed,
                    view=ProfileOwnerNotifView(user1, author_profile, already_match=True)
                )
            except Exception as e:
                print(f"⚠️ DM fallido (caso ya match): {e}")

            await interaction.followup.send("💬 Interés enviado.", ephemeral=True)

        # ==================================================
        # CASO 2: el dueño ya me dio like → hacer match automático
        # ==================================================
        elif target_liked_me:

            await add_match(author_id, target_id)
            await add_like(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)
            await add_match_stat(user1.id, user2.id)

            await interaction.followup.send("💞 ¡Match!", ephemeral=True)

        # ==================================================
        # CASO 3: like normal (ninguno se había dado like)
        # ==================================================
        else:

            await add_match(author_id, target_id)
            await add_like(target_id)

            profile1 = await get_full_profile(user1.id)

            embed = create_profile_embed(profile1, user1)
            embed.title = "💌 ¡Alguien está interesad@ en tu perfil!"

            # Vista para el dueño: botón "Hacer Match"
            try:
                await user2.send(
                    embed=embed,
                    view=ProfileOwnerNotifView(user1, profile1, already_match=False)
                )
            except Exception as e:
                print(f"⚠️ DM fallido (caso like normal): {e}")

            await interaction.followup.send("❤️ Like enviado.", ephemeral=True)

    # ----------------------------------------------------------
    # 📖 VER BLOGS
    # ----------------------------------------------------------
    @discord.ui.button(label="📖 Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = await self.bot.fetch_user(self.profile_data["user_id"])
        profile_embed = create_profile_embed(self.profile_data, user)

        viewer = BlogViewer(user, profile_embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )

    # ----------------------------------------------------------
    # 🔓 DESBLOQUEAR
    # ----------------------------------------------------------
    @discord.ui.button(label="🔓 Desbloquear", style=discord.ButtonStyle.secondary)
    async def unblock(self, interaction: discord.Interaction, button: discord.ui.Button):

        author_id = interaction.user.id
        target_id = self.profile_data["user_id"]

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT block FROM profiles WHERE user_id = $1", author_id
        )

        if not row:
            await conn.close()
            await interaction.response.send_message(
                "❌ No tienes perfil.", ephemeral=True
            )
            return

        blocked = row["block"] or []

        if target_id not in blocked:
            await conn.close()
            await interaction.response.send_message(
                "ℹ️ Este usuario no está bloqueado.", ephemeral=True
            )
            return

        await conn.execute(
            "UPDATE profiles SET block = array_remove(block, $1) WHERE user_id = $2",
            target_id,
            author_id
        )
        await conn.close()

        await interaction.response.send_message(
            "🔓 Usuario desbloqueado correctamente.", ephemeral=True
        )


# ==========================================================
# ONLINE PROFILE SYSTEM
# ==========================================================

class OnlineProfiles:

    def __init__(self, bot):
        self.bot = bot
        self.update_online_profiles.start()

    async def reset_active(self, conn):
        await conn.execute("UPDATE profiles SET active = FALSE")

    async def update_active_users(self, conn):

        rows = await conn.fetch("SELECT user_id FROM profiles")
        active_ids = []

        for row in rows:
            user_id = row["user_id"]

            for guild in self.bot.guilds:
                member = guild.get_member(user_id)

                if member and member.status in (
                    discord.Status.online,
                    discord.Status.idle,
                    discord.Status.dnd
                ):
                    active_ids.append(user_id)
                    break

        if active_ids:
            await conn.execute(
                "UPDATE profiles SET active = TRUE WHERE user_id = ANY($1)",
                active_ids
            )

    @tasks.loop(minutes=5)
    async def update_online_profiles(self):

        try:
            print("🔄 Actualizando perfiles online...")

            conn = await asyncpg.connect(DATABASE_URL)

            await self.reset_active(conn)
            await self.update_active_users(conn)

            rows = await conn.fetch(
                """
                SELECT *
                FROM profiles
                WHERE active = TRUE
                ORDER BY popularity DESC
                """
            )

            print(f"📊 Perfiles activos: {len(rows)}")

            servers = await get_all_servers()

            for server in servers:

                channel_id = server["online_channel_id"]

                if not channel_id:
                    continue

                channel = self.bot.get_channel(channel_id)

                if not channel:
                    continue

                try:
                    await channel.purge(limit=50)
                except Exception as e:
                    print(f"⚠️ No se pudo limpiar canal {channel_id}: {e}")

                for row in rows:

                    profile = dict(row)
                    print(f"➡️ Enviando perfil {profile['user_id']}")

                    try:
                        user = await self.bot.fetch_user(profile["user_id"])
                    except Exception as e:
                        print(f"⚠️ Error obteniendo usuario: {e}")
                        continue

                    embed = create_profile_embed(profile, user)
                    view = LikeView(self.bot, profile)

                    try:
                        message = await channel.send(embed=embed, view=view)

                        if channel.is_news():
                            try:
                                await message.publish()
                            except Exception as e:
                                print(f"⚠️ Error publicando: {e}")

                        await asyncio.sleep(3)

                    except Exception as e:
                        print(f"❌ Error enviando perfil: {e}")

            await conn.close()

        except Exception as e:
            print(f"💥 ERROR EN LOOP: {e}")

    @update_online_profiles.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()