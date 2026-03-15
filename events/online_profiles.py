import discord
import asyncio
import asyncpg
import os
from discord.ext import tasks

from src.tinder import create_profile_embed

DATABASE_URL = os.getenv("DATABASE_URL")
PROFILE_CHANNEL_ID = int(os.getenv("PROFILE_CHANNEL_ID"))


class OnlineProfiles:
    """
    Sistema que:
    1️⃣ Actualiza qué usuarios están activos
    2️⃣ Muestra los perfiles activos en un canal
    """

    def __init__(self, bot):
        self.bot = bot
        self.update_online_profiles.start()

    # ------------------------------------------------
    # RESET ACTIVE STATUS
    # ------------------------------------------------

    async def reset_active(self, conn):
        """Pone todos los usuarios como offline"""
        await conn.execute("UPDATE profiles SET active = FALSE")

    # ------------------------------------------------
    # UPDATE ACTIVE USERS
    # ------------------------------------------------

    async def update_active_users(self, conn):
        """Marca como activos los usuarios online en cualquier servidor"""

        for guild in self.bot.guilds:

            for member in guild.members:

                if member.bot:
                    continue

                if member.status == discord.Status.offline:
                    continue

                await conn.execute(
                    "UPDATE profiles SET active = TRUE WHERE user_id = $1",
                    member.id
                )

    # ------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------

    @tasks.loop(minutes=5)
    async def update_online_profiles(self):

        print("🔄 Actualizando perfiles online...")

        channel = self.bot.get_channel(PROFILE_CHANNEL_ID)

        if not channel:
            print("❌ Canal de perfiles no encontrado")
            return

        # conexión base de datos
        conn = await asyncpg.connect(DATABASE_URL)

        # ---------------------------------------------
        # 1️⃣ RESET ACTIVE
        # ---------------------------------------------

        await self.reset_active(conn)

        # ---------------------------------------------
        # 2️⃣ UPDATE ACTIVE USERS
        # ---------------------------------------------

        await self.update_active_users(conn)

        # ---------------------------------------------
        # 3️⃣ BORRAR CANAL
        # ---------------------------------------------

        try:
            await channel.purge()
        except Exception as e:
            print(f"⚠️ Error borrando canal: {e}")

        # ---------------------------------------------
        # 4️⃣ MOSTRAR PERFILES ACTIVOS
        # ---------------------------------------------

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

            try:
                await channel.send(embed=embed)

                # evitar rate limit
                await asyncio.sleep(1)

            except discord.DiscordServerError:
                print("⚠️ Error 503 de Discord, reintentando...")
                await asyncio.sleep(3)

                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    print(f"❌ No se pudo enviar perfil: {e}")

        await conn.close()

    # ------------------------------------------------
    # START LOOP
    # ------------------------------------------------

    @update_online_profiles.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()