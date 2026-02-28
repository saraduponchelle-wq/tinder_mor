import discord
from discord import app_commands
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def delete_callback(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Solo los administradores pueden usar este comando.",
            ephemeral=True
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT message_id FROM profiles WHERE user_id = $1", user.id)

    if row and row["message_id"]:
        try:
            msg = await interaction.channel.fetch_message(row["message_id"])
            await msg.delete()
        except:
            pass

    await conn.execute("DELETE FROM profiles WHERE user_id = $1", user.id)
    await conn.close()

    await interaction.response.send_message(
        f"✅ Perfil de {user.mention} eliminado correctamente.",
        ephemeral=True
    )

delete = app_commands.Command(
    name="delete",
    description="Elimina el perfil de un usuario (solo admins)",
    callback=delete_callback
)