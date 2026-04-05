import discord
from discord import app_commands
import asyncpg
import os
from typing import Optional

from src.blog_viewer import BlogViewer
from embed.create_profile import create_profile_embed
from src.nsfw_check import check_nsfw

DATABASE_URL = os.getenv("DATABASE_URL")

EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))


class ProfileView(discord.ui.View):

    def __init__(self, viewer_id: int, profile_user: discord.User, profile_embed: discord.Embed):
        super().__init__(timeout=300)

        self.viewer_id = viewer_id
        self.profile_user = profile_user
        self.profile_embed = profile_embed

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.viewer_id

    @discord.ui.button(label="Ver Blogs", style=discord.ButtonStyle.secondary)
    async def blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        viewer = BlogViewer(user=self.profile_user, profile_embed=self.profile_embed)
        await viewer.load()

        if not viewer.blogs:
            await interaction.response.send_message(
                "Este usuario no tiene blogs.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            embed=viewer.create_embed(),
            view=viewer
        )


async def show_callback(interaction: discord.Interaction, user: Optional[discord.Member] = None):

    if not await check_nsfw(interaction):
        return

    target = user or interaction.user

    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id = $1",
        target.id
    )

    await conn.close()

    if not row:
        await interaction.response.send_message(
            f"{EMOJI_BROKENHEART} No se encontró un perfil para este usuario.",
            ephemeral=True
        )
        return

    profile_data = dict(row)

    embed = create_profile_embed(
        profile_data=profile_data,
        discord_user=target,
        show_discord=True
    )

    view = ProfileView(
        viewer_id=interaction.user.id,
        profile_user=target,
        profile_embed=embed
    )

    await interaction.response.send_message(
        embed=embed,
        view=view
    )


show = app_commands.Command(
    name="show",
    description="Muestra el perfil de un usuario",
    callback=show_callback
)
