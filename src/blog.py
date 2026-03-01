# src/blog.py
import discord
from discord import app_commands
import os

BLOG_CHANNEL_ID = int(os.getenv("BLOG_CHANNEL_ID"))

# ===============================
# MODAL PARA TEXTO DEL BLOG
# ===============================
class BlogTextModal(discord.ui.Modal, title="Escribe tu blog"):
    blog_text_input = discord.ui.TextInput(
        label="Texto del blog",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe tu contenido aquí...",
        required=True,
        max_length=4000
    )

    def __init__(self, author: discord.User, image_url: str):
        super().__init__()
        self.author = author
        self.image_url = image_url

    async def on_submit(self, interaction: discord.Interaction):
        blog_text = self.blog_text_input.value.strip()
        print(f"[DEBUG] Texto del blog recibido: {blog_text}")

        channel = interaction.guild.get_channel(BLOG_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Canal de blogs no encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📖 Blog de {self.author.display_name}",
            description=blog_text,
            color=discord.Color.blue()
        )
        embed.set_image(url=self.image_url)
        embed.set_footer(text=f"Creado por {self.author}", icon_url=self.author.display_avatar.url)

        await channel.send(content=f"{self.author.mention}", embed=embed)
        await interaction.response.send_message("✅ Tu blog ha sido publicado!", ephemeral=True)


# ===============================
# MODAL PARA LINK DE IMAGEN
# ===============================
class BlogImageModal(discord.ui.Modal, title="Ingresa el link de la imagen del blog"):
    image_url_input = discord.ui.TextInput(
        label="Link de la imagen",
        style=discord.TextStyle.short,
        placeholder="https://ejemplo.com/imagen.png",
        required=True,
        max_length=2000
    )

    def __init__(self, author: discord.User):
        super().__init__()
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        image_url = self.image_url_input.value.strip()
        print(f"[DEBUG] Link recibido: {image_url}")

        # Abrir modal de texto usando `interaction.response.send_modal`
        # 🔹 Esto funciona solo si llamamos desde un **defer** previo
        await interaction.response.send_modal(BlogTextModal(self.author, image_url))


# ===============================
# COMANDO
# ===============================
async def crearblog_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /blog usado por {interaction.user}")
    await interaction.response.send_modal(BlogImageModal(interaction.user))


# ===============================
# EXPORTABLE
# ===============================
blog = app_commands.Command(
    name="blog",
    description="Crea un blog con imagen y texto",
    callback=crearblog_callback
)