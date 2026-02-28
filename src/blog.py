# src/blog.py
import discord
from discord import app_commands
import asyncio
import os

# ===============================
# Config
# ===============================
BLOG_CHANNEL_ID = int(os.getenv("BLOG_CHANNEL_ID"))

# ===============================
# Modal del blog
# ===============================
class BlogModal(discord.ui.Modal, title="Nuevo Blog"):
    blog_text = discord.ui.TextInput(
        label="Escribe tu blog",
        style=discord.TextStyle.paragraph,
        placeholder="Aquí va tu contenido...",
        required=True,
        max_length=4000
    )

    def __init__(self, author: discord.User):
        super().__init__()
        self.author = author
        self.blog_text_value = None
        self.blog_image_url = None

    async def on_submit(self, interaction: discord.Interaction):
        self.blog_text_value = self.blog_text.value
        print(f"[DEBUG] Texto del blog recibido: {self.blog_text_value}")

        await interaction.response.send_message(
            "📸 Ahora envía la **imagen del blog** en este canal. Solo la siguiente imagen será tomada.",
            ephemeral=True
        )

        # 🔥 Espera la siguiente imagen del mismo usuario
        def check(m: discord.Message):
            correct_user = m.author.id == self.author.id
            has_attachment = bool(m.attachments)
            if has_attachment:
                attachment = m.attachments[0]
                is_image = any(
                    attachment.filename.lower().endswith(ext)
                    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]
                )
            else:
                is_image = False

            print(f"[DEBUG] Mensaje recibido: author={m.author.id}, has_attachment={has_attachment}, is_image={is_image}")
            return correct_user and is_image

        try:
            msg = await interaction.client.wait_for("message", check=check, timeout=300)  # 5 min
            self.blog_image_url = msg.attachments[0].url
            print(f"[DEBUG] Imagen recibida: {self.blog_image_url}")
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado. No se recibió ninguna imagen.", ephemeral=True)
            return

        # Publicar blog
        channel = interaction.guild.get_channel(BLOG_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send("❌ Canal de blogs no encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📖 Blog de {self.author.display_name}",
            description=self.blog_text_value,
            color=discord.Color.blue()
        )
        embed.set_image(url=self.blog_image_url)
        embed.set_footer(text=f"Creado por {self.author}", icon_url=self.author.display_avatar.url)

        await channel.send(content=f"{self.author.mention}", embed=embed)
        await interaction.followup.send("✅ Tu blog ha sido publicado!", ephemeral=True)
        print("[DEBUG] Blog publicado correctamente")

# ===============================
# Comando
# ===============================
async def crearblog_callback(interaction: discord.Interaction):
    print(f"[DEBUG] /blog usado por {interaction.user}")
    modal = BlogModal(interaction.user)
    await interaction.response.send_modal(modal)

# ===============================
# Exportable
# ===============================
blog = app_commands.Command(
    name="blog",
    description="Crea un blog en el canal especial",
    callback=crearblog_callback
)