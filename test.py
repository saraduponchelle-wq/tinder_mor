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

    return img.crop((left, top, left + min_dim, top + min_dim))


# =========================
# DESCARGAR IMAGEN
# =========================
async def download_image(url, fallback_url):
    async with aiohttp.ClientSession() as session:

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
        except:
            pass

        # fallback
        async with session.get(fallback_url) as resp:
            return await resp.read()


# =========================
# FUNCIÓN PRINCIPAL
# =========================
async def test(bot: discord.Client, user: discord.User, frame_name="princess"):

    # =========================
    # OBTENER IMAGEN
    # =========================
    profile = await get_full_profile(user.id)

    avatar_url = profile.get("profile_image")
    if not avatar_url or avatar_url == "nothing":
        avatar_url = user.display_avatar.url

    avatar_bytes = await download_image(avatar_url, user.display_avatar.url)

    # =========================
    # DETECTAR GIF
    # =========================
    try:
        img_test = Image.open(io.BytesIO(avatar_bytes))
        is_gif = getattr(img_test, "is_animated", False)
        img_test.verify()
    except UnidentifiedImageError:
        print("❌ Imagen inválida, usando avatar")
        avatar_bytes = await download_image(user.display_avatar.url, user.display_avatar.url)
        img_test = Image.open(io.BytesIO(avatar_bytes))
        is_gif = getattr(img_test, "is_animated", False)

    avatar = Image.open(io.BytesIO(avatar_bytes))

    # =========================
    # CARGAR MARCO
    # =========================
    frame = Image.open(f"marcos/{frame_name}.png").convert("RGBA")

    # 🔥 reducimos tamaño base
    BASE_SIZE = 512
    frame = frame.resize((BASE_SIZE, BASE_SIZE))

    # 🔥 avatar más pequeño (20% menos)
    AVATAR_SIZE = int(BASE_SIZE * 0.8)
    pos = ((BASE_SIZE - AVATAR_SIZE) // 2, (BASE_SIZE - AVATAR_SIZE) // 2)

    output_buffer = io.BytesIO()

    # =========================
    # GIF
    # =========================
    if is_gif:

        frames = []
        durations = []

        for frame_gif in ImageSequence.Iterator(avatar):

            frame_gif = frame_gif.convert("RGBA")

            frame_gif = crop_to_square(frame_gif)
            frame_gif = frame_gif.resize((AVATAR_SIZE, AVATAR_SIZE))

            # máscara circular
            mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)

            frame_gif.putalpha(mask)

            final = Image.new("RGBA", (BASE_SIZE, BASE_SIZE))
            final.paste(frame_gif, pos, frame_gif)
            final.paste(frame, (0, 0), frame)

            frames.append(final)

            durations.append(frame_gif.info.get("duration", 80))

            # 🔥 límite de frames para evitar archivos enormes
            if len(frames) > 20:
                break

        frames[0].save(
            output_buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True
        )

        filename = "profile.gif"

    # =========================
    # PNG → JPG (OPTIMIZADO)
    # =========================
    else:

        avatar = avatar.convert("RGBA")

        avatar = crop_to_square(avatar)
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))

        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)

        avatar.putalpha(mask)

        final = Image.new("RGBA", (BASE_SIZE, BASE_SIZE))
        final.paste(avatar, pos, avatar)
        final.paste(frame, (0, 0), frame)

        # 🔥 convertir a JPG (mucho más ligero)
        final = final.convert("RGB")

        final.save(
            output_buffer,
            format="JPEG",
            quality=85,
            optimize=True
        )

        filename = "profile.jpg"

    output_buffer.seek(0)

    # =========================
    # EXTRA SEGURIDAD (TAMAÑO)
    # =========================
    if output_buffer.getbuffer().nbytes > 7_500_000:
        print("⚠️ Imagen aún pesada, reduciendo más...")

        avatar = avatar.resize((256, 256))
        output_buffer = io.BytesIO()

        avatar.convert("RGB").save(
            output_buffer,
            format="JPEG",
            quality=70,
            optimize=True
        )

        output_buffer.seek(0)
        filename = "profile_small.jpg"

    # =========================
    # SUBIR A DISCORD
    # =========================
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("❌ Canal no encontrado")
        return

    msg = await channel.send(
        file=discord.File(output_buffer, filename=filename)
    )

    url = msg.attachments[0].url
    print("✅ Imagen subida:", url)

    return url