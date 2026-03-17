import discord
from PIL import Image, ImageDraw, ImageSequence
import aiohttp
import io

from src.tinder import get_full_profile

CHANNEL_ID = 1483534237838741657

async def test(bot: discord.Client, user: discord.User):

    # =========================
    # OBTENER IMAGEN DESDE DB
    # =========================
    profile = await get_full_profile(user.id)

    avatar_url = profile["profile_image"]

    if not avatar_url or avatar_url == "nothing":
        avatar_url = user.display_avatar.url

    is_gif = avatar_url.endswith(".gif")

    # =========================
    # DESCARGAR IMAGEN
    # =========================
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    # =========================
    # CARGAR MARCO
    # =========================
    frame_img = Image.open("marcos/princess.png").convert("RGBA")
    frame_img = frame_img.resize((1024, 1024))

    output_buffer = io.BytesIO()

    size = 819
    pos = ((1024 - size) // 2, (1024 - size) // 2)

    # =========================
    # CASO GIF
    # =========================
    if is_gif:

        avatar = Image.open(io.BytesIO(avatar_bytes))
        frames = []

        for frame in ImageSequence.Iterator(avatar):

            frame = frame.convert("RGBA").resize((size, size))

            # máscara circular
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            frame.putalpha(mask)

            final = Image.new("RGBA", (1024, 1024))
            final.paste(frame, pos, frame)
            final.paste(frame_img, (0, 0), frame_img)

            frames.append(final)

        frames[0].save(
            output_buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=avatar.info.get("duration", 80),
            loop=0,
            disposal=2
        )

        filename = "profile.gif"

    # =========================
    # CASO PNG
    # =========================
    else:

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((size, size))

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        avatar.putalpha(mask)

        final = Image.new("RGBA", (1024, 1024))
        final.paste(avatar, pos, avatar)
        final.paste(frame_img, (0, 0), frame_img)

        final.save(output_buffer, format="PNG")
        filename = "profile.png"

    output_buffer.seek(0)

    # =========================
    # SUBIR A DISCORD
    # =========================
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("❌ Canal no encontrado")
        return

    msg = await channel.send(file=discord.File(output_buffer, filename=filename))

    print("✅ Imagen subida:", msg.attachments[0].url)

    return msg.attachments[0].url