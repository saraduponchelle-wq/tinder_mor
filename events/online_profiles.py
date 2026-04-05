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

EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))

EMOJI_BOTON_HEART = discord.PartialEmoji.from_str("<a:heart:1477738562433581338>")
EMOJI_BOTON_BROKENHEART = discord.PartialEmoji.from_str("<:brokenheart:1477739060423299202>")

DATABASE_URL = os.getenv("DATABASE_URL")


# ==========================================================
# LIKE BUTTON VIEW
# ==========================================================

class LikeView(discord.ui.View):

    def __init__(self, bot, profile_data):
        super().__init__(timeout=None)
        self.bot = bot
        self.profile_data = profile_data

    @discord.ui.button(label="Like", emoji=EMOJI_BOTON_HEART, style=discord.ButtonStyle.success)
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button):

        target_id = self.profile_data["user_id"]
        author_id = interaction.user.id

        if author_id == target_id:
            await interaction.response.send_message("❌ No puedes darte like a ti mismo.", ephemeral=True)
            return

        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id=$1", author_id)
        await conn.close()

        if not row:
            await interaction.response.send_message("❌ Necesitas crear un perfil primero.", ephemeral=True)
            return

        liker_profile = dict(row)

        if target_id in (liker_profile.get("block") or []):
            await interaction.response.send_message("🚫 Has bloqueado a este usuario.", ephemeral=True)
            return

        user1 = interaction.user
        user2 = await self.bot.fetch_user(target_id)

        # ✅ Leer estado ANTES de modificar nada
        author_profile = await get_full_profile(author_id)
        target_profile = await get_full_profile(target_id)

        author_matches = author_profile.get("matches") or []
        target_matches = target_profile.get("matches") or []

        already_matched = target_id in author_matches and author_id in target_matches
        target_liked_you = author_id in target_matches

        # 💬 CASO 1: YA MATCH → COUCOU
        if already_matched:
            await send_coucou(user2, user1)
            await add_popularity(target_id)
            await interaction.response.send_message("💬 Coucou enviado.", ephemeral=True)
            return

        # 💞 CASO 2: MATCH NUEVO
        if target_liked_you:
            await add_match(author_id, target_id)
            await add_like(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)
            await add_match_stat(user1.id, user2.id)

            await interaction.response.send_message("💞 ¡Match!", ephemeral=True)
            return

        # ❤️ CASO 3: LIKE NORMAL
        await add_match(author_id, target_id)
        await add_like(target_id)

        profile1 = await get_full_profile(user1.id)
        embed = create_profile_embed(profile1, user1)
        embed.title = "💌 A alguien le ha gustado tu perfil"

        try:
            await user2.send(
                embed=embed,
                view=LikeBackView(author_id, profile1, user1)
            )
        except Exception as e:
            print(f"⚠️ No se pudo enviar DM: {e}")

        await interaction.response.send_message("❤️ Like enviado.", ephemeral=True)

    @discord.ui.button(label="Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = await self.bot.fetch_user(self.profile_data["user_id"])
        profile_embed = create_profile_embed(self.profile_data, user)

        viewer = BlogViewer(user, profile_embed, self)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message("📭 Este usuario no tiene blogs.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=viewer.create_embed(),
            view=viewer,
            ephemeral=True
        )

    @discord.ui.button(label="Desbloquear", style=discord.ButtonStyle.secondary, emoji="🔓")
    async def unblock(self, interaction: discord.Interaction, button: discord.ui.Button):

        author_id = interaction.user.id
        target_id = self.profile_data["user_id"]

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT block FROM profiles WHERE user_id=$1", author_id
        )

        if not row:
            await conn.close()
            await interaction.response.send_message("❌ No tienes perfil.", ephemeral=True)
            return

        blocked = row["block"] or []

        if target_id not in blocked:
            await conn.close()
            await interaction.response.send_message("ℹ️ Este usuario no está bloqueado.", ephemeral=True)
            return

        await conn.execute(
            "UPDATE profiles SET block = array_remove(block, $1) WHERE user_id = $2",
            target_id, author_id
        )
        await conn.close()

        await interaction.response.send_message("🔓 Usuario desbloqueado correctamente.", ephemeral=True)


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
