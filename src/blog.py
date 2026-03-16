# src/blog.py
import discord
from discord import app_commands
import asyncio
import os
from src.blog_db import add_blog

BLOG_CHANNEL_ID = int(os.getenv("BLOG_CHANNEL_ID"))
BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
EMOJI_NOTI = str(os.getenv("NOTI"))
EMOJI_MES = str(os.getenv("MES"))
EMOJI_YES = str(os.getenv("YES"))
EMOJI_NO = str(os.getenv("NO"))

from src.blog_notifications import get_users_with_news_enabled


# ===============================
# Función para enviar blog a revisión
# ===============================
async def post_blog_for_review(client: discord.Client, author: discord.User, blog_text: str, image_url: str | None):
                """Publica el blog en el canal de revisión y espera aprobación de admin"""
                channel = client.get_channel(BLOG_REVIEW_CHANNEL_ID)
                if not channel:
                    print("[ERROR] Canal de revisión de blogs no encontrado")
                    return

                embed = discord.Embed(
                    title=f"**{EMOJI_NOTI} Nuevo Blog de {author.display_name}**\n⚬─────────────✧─────────────⚬",
                    description=blog_text,
                    color=discord.Color.red()
                )
                if image_url:
                    embed.set_image(url=image_url)
                embed.set_footer(text=f"Creado por {author}", icon_url=author.display_avatar.url)

                # 🔹 Enviamos el mensaje de revisión
                msg = await channel.send(content=f"{author.mention}", embed=embed)
                await msg.add_reaction("👍")

                print(f"[DEBUG] Blog {msg.id} enviado a revisión")

                # 🔹 CHECK CORREGIDO (MUY IMPORTANTE)
                def check(reaction, user):
                    return (
                        reaction.message.id == msg.id and  # ✅ SOLO ESTE MENSAJE
                        str(reaction.emoji) == "👍" and
                        user.id != client.user.id and
                        any(role.id == ADMIN_ROLE_ID for role in user.roles)
                    )

                try:
                    reaction, user = await client.wait_for(
                        "reaction_add",
                        timeout=28800,  # 8 horas
                        check=check
                    )
                    print(f"[DEBUG] Blog {msg.id} aprobado por {user}")
                except asyncio.TimeoutError:
                    print(f"[DEBUG] Blog {msg.id} expiró sin aprobación")
                    return

                # 🔹 Solo este blog se enviará
                user_ids = await get_users_with_news_enabled()
                print(f"[DEBUG] Enviando blog {msg.id} a {len(user_ids)} usuarios")

                for user_id in user_ids:
                    try:
                        u = await client.fetch_user(user_id)
                        await u.send(embed=embed)
                        await u.send(f"{EMOJI_MES} Si estás interesado, escríbele a {author.mention}")
                    except Exception as e:
                        print(f"[ERROR] No se pudo enviar a {user_id}: {e}")

# ===============================
# Modal de texto del blog
# ===============================
class BlogTextModal(discord.ui.Modal, title="Escribe tu blog"):
    blog_text_input = discord.ui.TextInput(
        label="Texto del blog",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe tu contenido aquí...",
        required=True,
        max_length=4000
    )

    def __init__(self, author: discord.User):
        super().__init__()
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        blog_text = self.blog_text_input.value.strip()
        print(f"[DEBUG] Texto del blog recibido: {blog_text}")

        # Preguntar si quiere añadir imagen
        view = BlogImageButtonView(self.author, blog_text)
        await interaction.response.send_message(
            f"{EMOJI_YES} Texto recibido. ¿Quieres añadir una imagen a tu blog?",
            view=view,
            ephemeral=True
        )

# ===============================
# Vista con botón para añadir imagen
# ===============================
class BlogImageButtonView(discord.ui.View):
    def __init__(self, author: discord.User, blog_text: str):
        super().__init__(timeout=None)
        self.author = author
        self.blog_text = blog_text

    @discord.ui.button(label="Añadir imagen", style=discord.ButtonStyle.primary)
    async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(f"{EMOJI_NO} Solo el autor puede usar este botón.", ephemeral=True)
            return

        # Abrir modal para pegar URL de la imagen
        await interaction.response.send_modal(BlogImageModal(self.author, self.blog_text))

# ===============================
# Modal para URL de imagen
# ===============================
class BlogImageModal(discord.ui.Modal, title="Añadir URL de la imagen"):
    image_url_input = discord.ui.TextInput(
        label="URL de la imagen",
        style=discord.TextStyle.short,
        placeholder="https://ejemplo.com/imagen.png",
        required=True,
        max_length=2000
    )

    def __init__(self, author: discord.User, blog_text: str):
        super().__init__()
        self.author = author
        self.blog_text = blog_text

    async def on_submit(self, interaction: discord.Interaction):
        image_url = self.image_url_input.value.strip()
        print(f"[DEBUG] URL de imagen recibido: {image_url}")

        # Publicar en canal principal
        channel = interaction.guild.get_channel(BLOG_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(f"{EMOJI_NO} Canal de blogs no encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title="**" + EMOJI_NOTI + " Nuevo Blog de " + self.author.display_name + "**\n" + "⚬─────────────✧─────────────⚬",
            description=self.blog_text,
            color=discord.Color.red()
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Creado por {self.author}", icon_url=self.author.display_avatar.url)

        message = await channel.send(
            content=f"{self.author.mention}",
            embed=embed
        )

        # autopublicar si es canal de anuncios
        if isinstance(channel, discord.TextChannel) and channel.is_news():
            try:
                await message.publish()
            except Exception as e:
                print(f"[ERROR] No se pudo autopublicar: {e}")

        await add_blog(
            self.author.id,
            self.blog_text,
            image_url if image_url else "nothing"
        )

        await interaction.response.send_message(
            f"{EMOJI_YES} Tu blog ha sido publicado y guardado en tu perfil!",
            ephemeral=True
        )

        await post_blog_for_review(
            interaction.client,
            self.author,
            self.blog_text,
            image_url
        )

# ===============================
# Comando /blog
# ===============================
async def crearblog_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /blog usado por {interaction.user}")
    await interaction.response.send_modal(BlogTextModal(interaction.user))

blog = app_commands.Command(
    name="blog",
    description="Crea un blog con opción de añadir imagen",
    callback=crearblog_callback
)