import asyncpg
import os
import asyncio
import discord
from discord import app_commands, Interaction

from src.nsfw_check import check_nsfw

DATABASE_URL = os.getenv("DATABASE_URL")
EMOJI_YES = str(os.getenv("YES"))
EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_NO = str(os.getenv("NO"))


async def set_news_notifications(user_id: int, enable: bool):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE profiles SET news=$1 WHERE user_id=$2",
            enable,
            user_id
        )
    finally:
        await conn.close()


async def get_users_with_news_enabled():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT user_id FROM profiles WHERE news = TRUE"
        )
        return [row["user_id"] for row in rows]
    finally:
        await conn.close()


async def send_blog_to_users(bot: discord.Client, embed: discord.Embed, author: discord.User):
    user_ids = await get_users_with_news_enabled()

    for i, user_id in enumerate(user_ids, start=1):
        try:
            user = await bot.fetch_user(user_id)
            await user.send(embed=embed)
            await user.send(f"💬 Si estás interesado, escríbele a {author.mention}")

        except discord.HTTPException as e:
            if e.code == 50007:
                print(f"[WARN] No se pudo enviar a {user_id}: {e}")
            elif e.status == 429:
                retry_after = int(e.response.headers.get("Retry-After", 1))
                await asyncio.sleep(retry_after)
                await user.send(embed=embed)
            else:
                print(f"[ERROR] No se pudo enviar a {user_id}: {e}")
        except Exception as e:
            print(f"[ERROR] No se pudo enviar a {user_id}: {e}")

        if i % 10 == 0:
            await asyncio.sleep(1)


async def news_callback(interaction: Interaction, activar: bool):

    if not await check_nsfw(interaction):
        return

    await set_news_notifications(interaction.user.id, activar)
    estado = f"activadas {EMOJI_YES}" if activar else f"desactivadas {EMOJI_NO}"
    await interaction.response.send_message(
        f"{EMOJI_GOLDNOTI} Tus notificaciones de blogs han sido {estado}", ephemeral=True
    )


news = app_commands.Command(
    name="news",
    description="Activa o desactiva las notificaciones de blogs",
    callback=news_callback
)
