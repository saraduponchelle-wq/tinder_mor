import discord
from discord import app_commands
import asyncpg
import os

from src.blog_viewer import BlogViewer
from embed.create_profile import create_profile_embed


EMOJI_GOLDNOTI = str(os.getenv("GOLDNOTI"))
EMOJI_HEART = str(os.getenv("HEART"))
EMOJI_BROKENHEART = str(os.getenv("BROKENHEART"))

EMOJI_BOTON_HEART = discord.PartialEmoji.from_str("<a:heart:1477738562433581338>")
EMOJI_BOTON_BROKENHEART = discord.PartialEmoji.from_str("<:brokenheart:1477739060423299202>")

from src.tinder_logic import (
    add_like,
    add_match,
    add_match_stat,
    add_popularity,
    is_mutual_match,
    send_match,
    send_coucou,
    LikeBackView
)


# ==========================================================
# DATABASE
# ==========================================================

async def get_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return await asyncpg.connect(DATABASE_URL)


async def get_profiles(exclude_user_id: int):

    conn = await get_connection()
    
    rows = await conn.fetch("""
        SELECT p.*
    
        FROM profiles p
    
        WHERE p.user_id != $1
    
        -- 🚫 bloqueos
        AND NOT ($1 = ANY(p.block))
        AND NOT (p.user_id = ANY(
            SELECT UNNEST(block) FROM profiles WHERE user_id = $1
        ))
    
        ORDER BY
            p.active DESC,  -- 🟢 online primero
    
            -- 🎯 prioridad: tiene al menos 1 categoría en común
            (
                EXISTS (
                    SELECT 1
                    FROM UNNEST(COALESCE(p.lines, ARRAY[]::text[])) AS l
                    WHERE l = ANY(
                        SELECT UNNEST(COALESCE(lines, ARRAY[]::text[]))
                        FROM profiles
                        WHERE user_id = $1
                    )
                )
            ) DESC,
    
            -- 🔥 cantidad de coincidencias (ranking fino)
            (
                SELECT COUNT(*)
                FROM UNNEST(COALESCE(p.lines, ARRAY[]::text[])) AS l
                WHERE l = ANY(
                    SELECT UNNEST(COALESCE(lines, ARRAY[]::text[]))
                    FROM profiles
                    WHERE user_id = $1
                )
            ) DESC,
    
            -- ⭐ popularidad
            p.popularity DESC,
    
            -- extra
            p.matches DESC
    """, exclude_user_id)
    
    await conn.close()
    
    return rows


async def get_full_profile(user_id: int):

    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id=$1",
        user_id
    )

    await conn.close()

    return dict(row)


# ==========================================================
# TINDER VIEW
# ==========================================================

class TinderView(discord.ui.View):

    def __init__(self, profiles, author_id):

        super().__init__(timeout=900)

        self.profiles = profiles
        self.index = 0
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.author_id

    async def update_profile(self, interaction: discord.Interaction):

        profile = self.profiles[self.index]

        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user)

        await interaction.edit_original_response(
            embed=embed,
            view=self
        )

    async def next_profile(self, interaction: discord.Interaction):

        self.index += 1

        if self.index >= len(self.profiles):
            self.index = 0

        await self.update_profile(interaction)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.danger, emoji=EMOJI_BOTON_BROKENHEART)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        await self.next_profile(interaction)

    @discord.ui.button(label="Like", style=discord.ButtonStyle.success, emoji=EMOJI_BOTON_HEART)
    async def like_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()

            profile = self.profiles[self.index]

            target_id = profile["user_id"]
            author_id = interaction.user.id

            # ❌ evitar like a sí mismo
            if target_id == author_id:
                await interaction.followup.send("❌ No puedes darte like.", ephemeral=True)
                return

            # comprobar si ya era match
            already_match = await is_mutual_match(author_id, target_id)

            # registrar like
            await add_match(author_id, target_id)
            await add_like(target_id)

            user1 = interaction.user
            user2 = await interaction.client.fetch_user(target_id)

            profile1 = await get_full_profile(user1.id)
            profile2 = await get_full_profile(user2.id)

            # =========================
            # CASO 1: ya era match
            # =========================
            if already_match:

                await send_coucou(user2, user1)
                await add_popularity(target_id)

            # =========================
            # CASO 2: nuevo match
            # =========================
            elif await is_mutual_match(author_id, target_id):

                await send_match(user1, profile2, user2)
                await send_match(user2, profile1, user1)

                await add_match_stat(user1.id, user2.id)

            # =========================
            # CASO 3: like normal
            # =========================
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

            await interaction.followup.send("❤️ Like enviado.", ephemeral=True)

            # 👉 pasar al siguiente perfil
            await self.next_profile(interaction)

    @discord.ui.button(label="Atrás", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        if self.index == 0:
            self.index = len(self.profiles) - 1
        else:
            self.index -= 1

        await self.update_profile(interaction)

    @discord.ui.button(label="Blogs", style=discord.ButtonStyle.primary)
    async def view_blogs(self, interaction: discord.Interaction, button: discord.ui.Button):

        profile = self.profiles[self.index]

        user = await interaction.client.fetch_user(profile["user_id"])

        embed = create_profile_embed(profile, user)

        viewer = BlogViewer(user, embed, self)

        await viewer.load()

        if not viewer.blogs:

            await interaction.response.send_message(
                "📭 Este usuario no tiene blogs.",
                ephemeral=True
            )

            return

        await interaction.response.edit_message(
            embed=viewer.create_embed(),
            view=viewer
        )


# ==========================================================
# COMMAND
# ==========================================================

async def tinder_callback(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    rows = await get_profiles(interaction.user.id)

    if not rows:
        await interaction.followup.send(
            "❌ No hay perfiles disponibles.",
            ephemeral=True
        )
        return

    profiles = [dict(row) for row in rows]

    first = profiles[0]

    user = await interaction.client.fetch_user(first["user_id"])

    embed = create_profile_embed(first, user)

    view = TinderView(profiles, interaction.user.id)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral=True
    )


tinder = app_commands.Command(
    name="tinder",
    description="Muestra perfiles estilo Tinder",
    callback=tinder_callback
)