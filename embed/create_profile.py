import discord
import os

EMOJI_INTEREST = str(os.getenv("INTEREST"))
EMOJI_LINES = str(os.getenv("LINES"))
EMOJI_STAR = str(os.getenv("STAR"))
EMOJI_HEART = str(os.getenv("HEART"))

LIKES_STAT = str(os.getenv("LIKES_STAT"))
MATCHES_STAT = str(os.getenv("MATCHES_STAT"))
POPULARITY_STAT = str(os.getenv("POPULARITY_STAT"))


def create_profile_embed(profile_data: dict, discord_user: discord.User, show_discord: bool = False):

    status = "🟢" if profile_data.get("active") else "🔴"

    embed = discord.Embed(
        title=f"{EMOJI_HEART} {profile_data['name']} {status}",
        color=discord.Color.pink()
    )

    # ---------------- INTERESES ----------------

    embed.add_field(
        name=f"{EMOJI_INTEREST} Intereses",
        value=", ".join(profile_data.get("interests") or ["Ninguno"]),
        inline=False
    )

    # ---------------- LÍNEAS ----------------

    embed.add_field(
        name=f"{EMOJI_LINES} Líneas",
        value=profile_data.get("lines") or "Sin líneas",
        inline=False
    )

    # ---------------- BIO ----------------

    embed.add_field(
        name=f"{EMOJI_STAR} Bio",
        value=profile_data.get("description") or "Sin descripción",
        inline=False
    )

    # ==========================================================
    # 🔥 IMAGEN INTELIGENTE (CON MARCO)
    # ==========================================================

    framed_image = profile_data.get("framed_profile_image")
    profile_image = profile_data.get("profile_image")
    banner_image = profile_data.get("banner_image")

    # prioridad: marco > normal > avatar
    if framed_image:
        embed.set_thumbnail(url=framed_image)
    elif profile_image:
        embed.set_thumbnail(url=profile_image)
    else:
        embed.set_thumbnail(url=discord_user.display_avatar.url)

    if banner_image:
        embed.set_image(url=banner_image)

    # ---------------- DISCORD USER ----------------

    if show_discord:
        embed.add_field(
            name="👤 Usuario de Discord",
            value=discord_user.mention,
            inline=False
        )

    # ---------------- STATS ----------------

    likes = profile_data.get("likes", 0)
    matches = profile_data.get("matches_nb", 0)
    popularity_extra = profile_data.get("popularity", 0)

    total_popularity = likes + matches + popularity_extra

    embed.add_field(
        name=f"{POPULARITY_STAT} Popularity",
        value=total_popularity,
        inline=True
    )

    embed.add_field(
        name=f"{LIKES_STAT} Likes",
        value=likes,
        inline=True
    )

    embed.add_field(
        name=f"{MATCHES_STAT} Matches",
        value=matches,
        inline=True
    )

    return embed