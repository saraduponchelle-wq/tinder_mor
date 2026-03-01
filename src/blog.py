# src/blog.py
import discord
from discord import app_commands
import os
import asyncio

BLOG_CHANNEL_ID = int(os.getenv("BLOG_CHANNEL_ID"))

# ===============================
# MODAL
# ===============================
class BlogLinkModal(discord.ui.Modal, title="Nuevo Blog"):
    image_url_input = discord.ui.TextInput(
        label="Ingresa el link de la imagen de tu blog",
        placeholder="https://ejemplo.com/imagen.png",
        required=True,
        style=discord.TextStyle.short,
        max_length=2000
    )

    def __init__(self, author: discord.User):
        super().__init__()
        self.author = author
        self.image_url = None

    async def on_submit(self, interaction: discord.Interaction):
        self.image_url = self.image_url_input.value.strip()
        print(f"[DEBUG] Link recibido: {self.image_url}")

        # Publicar en el canal de blogs
        channel = interaction.guild.get_channel(BLOG_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message("❌ Canal de blogs no encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📖 Blog de {self.author.display_name}",
            description=f"¡Nuevo blog de {self.author.mention}!",
            color=discord.Color.blue()
        )
        embed.set_image(url=self.image_url)
        embed.set_footer(text=f"Creado por {self.author}", icon_url=self.author.display_avatar.url)

        await channel.send(content=f"{self.author.mention}", embed=embed)
        await interaction.response.send_message("✅ Tu blog ha sido publicado!", ephemeral=True)

# ===============================
# COMANDO
# ===============================
async def crearblog_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /blog usado por {interaction.user}")
    modal = BlogLinkModal(interaction.user)
    await interaction.response.send_modal(modal)

# ===============================
# EXPORTABLE
# ===============================
blog = app_commands.Command(
    name="blog",
    description="Crea un blog con un link de imagen",
    callback=crearblog_callback
)