import discord
import asyncpg
import os
from discord.ext import tasks

from src.tinder import create_profile_embed

DATABASE_URL = os.getenv("DATABASE_URL")

PROFILE_CHANNEL_ID = int(os.getenv("PROFILE_CHANNEL_ID"))


class OnlineProfiles:

    def __init__(self, bot):
        self.bot = bot
        self.update_online_profiles.start()

    @tasks.loop(minutes=5)
    async def update_online_profiles(self):

        channel = self.bot.get_channel(PROFILE_CHANNEL_ID)

        if not channel:
            return

        # borrar mensajes del canal
        try:
            await channel.purge()
        except:
            return

        guild = channel.guild

        conn = await asyncpg.connect(DATABASE_URL)

        for member in guild.members:

            if member.bot:
                continue

            if member.status == discord.Status.offline:
                continue

            row = await conn.fetchrow(
                "SELECT * FROM profiles WHERE user_id = $1",
                member.id
            )

            if not row:
                continue

            profile = dict(row)

            embed = create_profile_embed(profile, member)

            await channel.send(embed=embed)

        await conn.close()

    @update_online_profiles.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()