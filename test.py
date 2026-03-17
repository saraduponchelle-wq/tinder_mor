import discord
from PIL import Image, ImageDraw, ImageSequence, UnidentifiedImageError
import aiohttp
import io

from src.tinder import get_full_profile

CHANNEL_ID = 1483534237838741657


# =========================
# RECORTAR A CUADRADO
# =========================
def crop_to_square(img: Image.Image) -> Image.Image:
    width, height = img.size
    min_dim = min(width, height)

    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    right = left + min_dim
    bottom = top + min_dim

    return img.crop((left, top, right, bottom))


# =========================
# FUNCIÓN PRINCIPAL
# =========================
async def test(bot: discord.Client, user: discord.User, frame_name="princess"):

    # =========================
    # OBTENER IMAGEN DESDE DB
    # =========================
    profile = await get_full_profile(user.id)

    avatar_url = profile.get("profile_image")

    if not avatar_url or avatar_url == "nothing":
        avatar_url = user.display_avatar.url

    # =========================
    # DESCARGAR IMAGEN
    # =========================
    async with aiohttp.ClientSession() as session:

        async with session.get(avatar_url) as resp:

            if resp.status != 200:
                print(f"❌ Error descargando ({resp.status}), usando avatar")

                async with session.get(user.display_avatar.url) as resp2:
                    avatar_bytes = await resp2.read()
            else:
                avatar_bytes = await resp.read()

    # =========================
    # VALIDAR + DETECTAR GIF
    # =========================
    try:
        img_test = Image.open(io.BytesIO(avatar_bytes))
        is_gif = getattr(img_test, "is_animated", False)
        img_test.verify()
    except UnidentifiedImageError:
        print("❌ Imagen inválida, fallback")

        async with aiohttp.ClientSession() as session:
            async with session.get(user.display_avatar.url) as resp:
                avatar_bytes = await resp.read()

        img_test = Image.open(io.BytesIO(avatar_bytes))
        is_gif = getattr(img_test, "is_animated", False)

    # ⚠️ REABRIR imagen (verify la rompe)
    avatar = Image.open(io.BytesIO(avatar_bytes))

    # =========================
    # CARGAR MARCO
    # =========================
    frame_path = f"marcos/{frame_name}.png"
    frame_img = Image.open(frame_path).convert("RGBA")
    frame_img = frame_img.resize((1024, 1024))

    output_buffer = io.BytesIO()

    size = 819
    pos = ((1024 - size) // 2, (1024 - size) // 2)

    # =========================
    # CASO GIF
    # =========================
    if is_gif:

        frames = []
        durations = []

        for frame in ImageSequence.Iterator(avatar):

            frame = frame.convert("RGBA")

            # recorte cuadrado
            frame = crop_to_square(frame)

            # resize
            frame = frame.resize((size, size))

            # máscara circular
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            frame.putalpha(mask)

            final = Image.new("RGBA", (1024, 1024))
            final.paste(frame, pos, frame)
            final.paste(frame_img, (0, 0), frame_img)

            frames.append(final)

            durations.append(frame.info.get("duration", 80))

        frames[0].save(
            output_buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
            optimize=False
        )

        filename = "profile.gif"

    # =========================
    # CASO PNG
    # =========================
    else:

        avatar = avatar.convert("RGBA")

        avatar = crop_to_square(avatar)
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