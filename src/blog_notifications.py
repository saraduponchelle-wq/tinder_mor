import asyncpg
import os
import asyncio
import discord
from discord import app_commands, Interaction

DATABASE_URL = os.getenv("DATABASE_URL")
EMOJI_YES = str(os.getenv("YES"))
EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_NO = str(os.getenv("NO"))

# ===============================
# DB HELPERS
# ===============================

async def set_news_notifications(user_id: int, enable: bool):
    """Activa o desactiva las notificaciones de blogs para un usuario"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "UPDATE profiles SET news=$1 WHERE user_id=$2",
            enable,
            user_id
        )
        print(f"[DEBUG] Noticias para {user_id} actualizadas a {enable}")
    finally:
        await conn.close()


async def get_users_with_news_enabled():
    """Devuelve lista de user_ids que tienen news=True"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT user_id FROM profiles WHERE news = TRUE"
        )
        return [row["user_id"] for row in rows]
    finally:
        await conn.close()


# ===============================
# ENVÍO DE MENSAJES SEGURO
# ===============================

async def send_blog_to_users(bot: discord.Client, embed: discord.Embed, author: discord.User):
    """
    Envía el embed del blog a todos los usuarios con news=True
    de manera segura, evitando rate limits.
    """
    user_ids = await get_users_with_news_enabled()
    print(f"[DEBUG] Preparando para enviar blog a {len(user_ids)} usuarios")

    for i, user_id in enumerate(user_ids, start=1):
        try:
            user = await bot.fetch_user(user_id)
            await user.send(embed=embed)
            await user.send(f"💬 Si estás interesado, escríbele a {author.mention}")

        except discord.HTTPException as e:
            if e.code == 50007:  # Cannot send messages to this user
                print(f"[WARN] No se pudo enviar a {user_id}: {e}")
            elif e.status == 429:  # Rate limited
                retry_after = int(e.response.headers.get("Retry-After", 1))
                print(f"[WARN] Rate limit alcanzado, esperando {retry_after}s...")
                await asyncio.sleep(retry_after)
                await user.send(embed=embed)
            else:
                print(f"[ERROR] No se pudo enviar a {user_id}: {e}")
        except Exception as e:
            print(f"[ERROR] No se pudo enviar a {user_id}: {e}")

        # Pausa cada 10 mensajes para no saturar la API
        if i % 10 == 0:
            await asyncio.sleep(1)


# =====================================
# Slash command para que el usuario pueda activar/desactivar
# =====================================
async def news_callback(interaction: Interaction, activar: bool):
    """Comando /news para activar/desactivar notificaciones"""
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