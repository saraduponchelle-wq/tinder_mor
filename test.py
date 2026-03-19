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

        async with session.get(fallback_url) as resp:
            return await resp.read()


# =========================
# FUNCIÓN PRINCIPAL
# =========================
async def test(bot: discord.Client, user: discord.User, frame_name="princess"):

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

    BASE_SIZE = 512
    frame = frame.resize((BASE_SIZE, BASE_SIZE))

    # 🔥 ligeramente más pequeño para evitar peso alto
    AVATAR_SIZE = int(BASE_SIZE * 0.75)

    pos = ((BASE_SIZE - AVATAR_SIZE) // 2, (BASE_SIZE - AVATAR_SIZE) // 2)

    output_buffer = io.BytesIO()

    # =========================
    # GIF
    # =========================
    if is_gif:

        frames = []
        durations = []

        for i, frame_gif in enumerate(ImageSequence.Iterator(avatar)):

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

            # duración real por frame
            duration = frame_gif.info.get("duration", avatar.info.get("duration", 80))
            durations.append(duration)

            # 🔥 protección contra GIFs enormes
            if len(frames) > 200:
                print("❌ Demasiados frames")
                return "❌ El GIF tiene demasiados frames."

        try:
            frames[0].save(
                output_buffer,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=avatar.info.get("loop", 0),
                disposal=2,
                optimize=True  # 🔥 CLAVE PARA NO EXPLOTAR EL PESO
            )

            filename = "profile.gif"

        except Exception as e:
            print("❌ Error creando GIF:", e)
            return "❌ El GIF es demasiado grande para procesar."

    # =========================
    # PNG / JPG
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
    # CONTROL DE TAMAÑO REAL
    # =========================
    size_bytes = output_buffer.getbuffer().nbytes
    print(f"📦 Tamaño final: {size_bytes / 1024:.2f} KB")

    if size_bytes > 20_000_000:
        print("❌ GIF demasiado grande tras procesado")
        return "❌ El GIF es demasiado grande (máx 20MB)."

    # =========================
    # SUBIR A DISCORD
    # =========================
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("❌ Canal no encontrado")
        return

    try:
        msg = await channel.send(
            file=discord.File(output_buffer, filename=filename)
        )

    except discord.HTTPException as e:
        print(f"❌ Error subiendo imagen: {e}")

        if e.status == 413:
            return "❌ El archivo supera el límite de Discord."

        return "❌ Error subiendo la imagen."

    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return "❌ Error inesperado al subir la imagen."


    url = msg.attachments[0].url
    print("✅ Imagen subida:", url)

    return url