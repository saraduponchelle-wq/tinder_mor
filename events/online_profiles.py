import discord
import asyncio
import asyncpg
import os
from discord.ext import tasks

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

DATABASE_URL = os.getenv("DATABASE_URL")
PROFILE_CHANNEL_ID = int(os.getenv("PROFILE_CHANNEL_ID"))


# ==========================================================
# LIKE BUTTON VIEW
# ==========================================================

class LikeView(discord.ui.View):

    def __init__(self, bot, profile_data):
        super().__init__(timeout=None)

        self.bot = bot
        self.profile_data = profile_data

    @discord.ui.button(label="❤️ Like", style=discord.ButtonStyle.success)
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button):

        target_id = self.profile_data["user_id"]
        author_id = interaction.user.id

        # ------------------------------------------------
        # NO DAR LIKE A UNO MISMO
        # ------------------------------------------------

        if author_id == target_id:
            await interaction.response.send_message(
                "❌ No puedes darte like a ti mismo.",
                ephemeral=True
            )
            return

        # ------------------------------------------------
        # COMPROBAR PERFIL
        # ------------------------------------------------

        conn = await asyncpg.connect(DATABASE_URL)

        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id=$1",
            author_id
        )

        await conn.close()

        if not row:
            await interaction.response.send_message(
                "❌ Necesitas crear un perfil primero.",
                ephemeral=True
            )
            return

        # ------------------------------------------------
        # COMPROBAR BLOQUEOS
        # ------------------------------------------------

        liker_profile = dict(row)

        if target_id in (liker_profile.get("block") or []):
            await interaction.response.send_message(
                "🚫 Has bloqueado a este usuario.",
                ephemeral=True
            )
            return

        # ------------------------------------------------
        # AÑADIR MATCH / LIKE
        # ------------------------------------------------

        already_match = await is_mutual_match(author_id, target_id)

        await add_match(author_id, target_id)
        await add_like(target_id)

        user1 = interaction.user
        user2 = await self.bot.fetch_user(target_id)

        profile1 = await get_full_profile(user1.id)
        profile2 = await get_full_profile(user2.id)

        # ------------------------------------------------
        # CASO 1: YA ERA MATCH → COUCOU
        # ------------------------------------------------

        if already_match:

            await send_coucou(user2, user1)
            await add_popularity(target_id)

        # ------------------------------------------------
        # CASO 2: NUEVO MATCH
        # ------------------------------------------------

        elif await is_mutual_match(author_id, target_id):

            await send_match(user1, profile2, user2)
            await send_match(user2, profile1, user1)

            await add_match_stat(user1.id, user2.id)

        # ------------------------------------------------
        # CASO 3: LIKE NORMAL
        # ------------------------------------------------

        else:

            embed = create_profile_embed(profile1, user1)
            embed.title = "💌 A alguien le ha gustado tu perfil"

            try:
                await user2.send(
                    embed=embed,
                    view=LikeBackView(author_id, profile1, user1)
                )
            except Exception as e:
                print(f"⚠️ No se pudo enviar DM: {e}")

        await interaction.response.send_message(
            "❤️ Like enviado.",
            ephemeral=True
        )


# ==========================================================
# ONLINE PROFILE SYSTEM
# ==========================================================

class OnlineProfiles:

    def __init__(self, bot):
        self.bot = bot
        self.update_online_profiles.start()

    # ------------------------------------------------
    # RESET ACTIVE STATUS
    # ------------------------------------------------

    async def reset_active(self, conn):

        await conn.execute(
            "UPDATE profiles SET active = FALSE"
        )

    # ------------------------------------------------
    # UPDATE ACTIVE USERS
    # ------------------------------------------------

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
    # ------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------

    @tasks.loop(minutes=5)
    async def update_online_profiles(self):

        print("🔄 Actualizando perfiles online...")

        channel = self.bot.get_channel(PROFILE_CHANNEL_ID)

        if not channel:
            print("❌ Canal no encontrado")
            return

        conn = await asyncpg.connect(DATABASE_URL)

        # 1️⃣ RESET
        await self.reset_active(conn)

        # 2️⃣ UPDATE
        await self.update_active_users(conn)

        # 3️⃣ LIMPIAR CANAL
        try:
            await channel.purge()
        except Exception as e:
            print(f"⚠️ Error borrando canal: {e}")

        # 4️⃣ OBTENER PERFILES ACTIVOS
        rows = await conn.fetch(
            """
            SELECT *
            FROM profiles
            WHERE active = TRUE
            ORDER BY popularity DESC
            """
        )

        for row in rows:

            profile = dict(row)

            try:
                user = await self.bot.fetch_user(profile["user_id"])
            except:
                continue

            embed = create_profile_embed(profile, user)

            view = LikeView(self.bot, profile)

            try:

                await channel.send(
                    embed=embed,
                    view=view
                )

                await asyncio.sleep(1)

            except discord.DiscordServerError:

                print("⚠️ Error 503, reintentando...")
                await asyncio.sleep(3)

                try:
                    await channel.send(embed=embed, view=view)
                except Exception as e:
                    print(f"❌ Error enviando perfil: {e}")

        await conn.close()

    # ------------------------------------------------
    # START LOOP
    # ------------------------------------------------

    @update_online_profiles.before_loop
    async def before_loop(self):

        await self.bot.wait_until_ready()