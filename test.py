import discord
from PIL import Image, ImageDraw, ImageSequence
import aiohttp
import io

CHANNEL_ID = 1483534237838741657

async def test(bot: discord.Client, user: discord.User):

    # Detectar si es GIF
    is_gif = user.display_avatar.is_animated()

    format = "gif" if is_gif else "png"
    avatar_url = user.display_avatar.replace(size=1024, format=format).url

    # Descargar avatar
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    # Cargar marco
    frame_img = Image.open("marcos/princess.png").convert("RGBA")
    frame_img = frame_img.resize((1024, 1024))

    # Crear máscara circular
    mask = Image.new("L", (1024, 1024), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, 1024, 1024), fill=255)

    output_buffer = io.BytesIO()

    # =========================
    # CASO GIF
    # =========================
    if is_gif:

        avatar = Image.open(io.BytesIO(avatar_bytes))

        frames = []

        for frame in ImageSequence.Iterator(avatar):

            frame = frame.convert("RGBA").resize((1024, 1024))

            # aplicar círculo
            frame.putalpha(mask)

            # combinar con marco
            final = Image.new("RGBA", (1024, 1024))
            final.paste(frame, (0, 0), frame)
            final.paste(frame_img, (0, 0), frame_img)

            frames.append(final)

        # guardar GIF
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
        avatar = avatar.resize((1024, 1024))

        avatar.putalpha(mask)

        final = Image.new("RGBA", (1024, 1024))
        final.paste(avatar, (0, 0), avatar)
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