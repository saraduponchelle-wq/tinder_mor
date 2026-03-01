# src/blog_notifications.py
import asyncpg
import os
from discord import app_commands, Interaction

DATABASE_URL = os.getenv("DATABASE_URL")


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


# =====================================
# Slash command para que el usuario pueda activar/desactivar
# =====================================
async def news_callback(interaction: Interaction, activar: bool):
    """Comando /news para activar/desactivar notificaciones"""
    await set_news_notifications(interaction.user.id, activar)
    estado = "activadas ✅" if activar else "desactivadas ❌"
    await interaction.response.send_message(
        f"📢 Tus notificaciones de blogs han sido {estado}", ephemeral=True
    )


news = app_commands.Command(
    name="news",
    description="Activa o desactiva las notificaciones de blogs",
    callback=news_callback
)