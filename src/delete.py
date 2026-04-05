import discord
from discord import app_commands
import asyncpg
import os

from src.nsfw_check import check_nsfw

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_YES = str(os.getenv("YES"))
EMOJI_NO = str(os.getenv("NO"))


async def delete_callback(interaction: discord.Interaction, user: discord.User):

    if not await check_nsfw(interaction):
        return

    if interaction.guild is None:
        await interaction.response.send_message(
            f"{EMOJI_NO} Este comando solo puede usarse en un servidor.",
            ephemeral=True
        )
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            f"{EMOJI_NO} Solo los administradores pueden usar este comando.",
            ephemeral=True
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT message_id FROM profiles WHERE user_id = $1",
        user.id
    )

    if not row:
        await conn.close()
        await interaction.response.send_message(
            f"{EMOJI_NO} {user.mention} no tiene un perfil registrado.",
            ephemeral=True
        )
        return

    message_id = row["message_id"]

    if message_id:
        try:
            msg = await interaction.channel.fetch_message(message_id)
            await msg.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    await conn.execute(
        "DELETE FROM profiles WHERE user_id = $1",
        user.id
    )

    await conn.close()

    await interaction.response.send_message(
        f"{EMOJI_YES} Perfil de {user.mention} eliminado correctamente.",
        ephemeral=True
    )


delete = app_commands.Command(
    name="delete",
    description="Elimina el perfil de un usuario (solo admins)",
    callback=delete_callback
)
