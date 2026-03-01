# src/blog.py
import discord
from discord import app_commands
import os

BLOG_CHANNEL_ID = int(os.getenv("BLOG_CHANNEL_ID"))

# Modal para el texto del blog
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
        print(f"[DEBUG] Texto recibido: {blog_text}")

        # Enviar mensaje con botón para añadir imagen
        view = BlogImageButtonView(self.author, blog_text)
        await interaction.response.send_message(
            "✅ Texto recibido. ¿Quieres añadir una imagen a tu blog?",
            view=view,
            ephemeral=True
        )


# Vista con botón para añadir imagen
class BlogImageButtonView(discord.ui.View):
    def __init__(self, author: discord.User, blog_text: str):
        super().__init__(timeout=None)
        self.author = author
        self.blog_text = blog_text

    @discord.ui.button(label="Añadir imagen", style=discord.ButtonStyle.primary)
    async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Solo el autor puede usar este botón.", ephemeral=True)
            return
        await interaction.response.send_modal(BlogImageModal(self.author, self.blog_text))


# Modal para el URL de la imagen
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

        channel = interaction.guild.get_channel(BLOG_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Canal de blogs no encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📖 Blog de {self.author.display_name}",
            description=self.blog_text,
            color=discord.Color.blue()
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Creado por {self.author}", icon_url=self.author.display_avatar.url)

        await channel.send(content=f"{self.author.mention}", embed=embed)
        await interaction.response.send_message("✅ Tu blog ha sido publicado con imagen!", ephemeral=True)


# Comando
async def crearblog_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /blog usado por {interaction.user}")
    await interaction.response.send_modal(BlogTextModal(interaction.user))


blog = app_commands.Command(
    name="blog",
    description="Crea un blog con opción de añadir imagen",
    callback=crearblog_callback
)