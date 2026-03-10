import discord
from src.blog_db import get_blogs

class BlogViewer(discord.ui.View):
    """
    Vista para mostrar blogs de un usuario.
    Funciona tanto para el comando show como para Tinder.
    """

    def __init__(self, user: discord.User, profile_embed: discord.Embed, tinder_view: discord.ui.View = None):
        super().__init__(timeout=300)  # Timeout de 5 minutos
        self.user = user
        self.index = 0
        self.blogs = []
        self.profile_embed = profile_embed
        self.tinder_view = tinder_view  # Si se pasa, se restaurará al volver

    async def load(self):
        """Carga los blogs desde la base de datos."""
        self.blogs = await get_blogs(self.user.id)

    def create_embed(self) -> discord.Embed:
        """Crea el embed del blog actual."""
        if not self.blogs:
            embed = discord.Embed(
                title="Blogs",
                description="Este usuario no tiene blogs publicados.",
                color=discord.Color.red()
            )
            return embed

        blog = self.blogs[self.index]

        embed = discord.Embed(
            title=f"Blog de {self.user.display_name}",
            description=blog["text"],
            color=discord.Color.red()
        )

        if blog.get("image") and blog["image"] != "nothing":
            embed.set_image(url=blog["image"])

        embed.set_footer(text=f"{self.index+1}/{len(self.blogs)}")

        return embed

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mostrar blog anterior."""
        if not self.blogs:
            return

        self.index -= 1
        if self.index < 0:
            self.index = len(self.blogs) - 1

        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )

    @discord.ui.button(label="➡", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mostrar blog siguiente."""
        if not self.blogs:
            return

        self.index += 1
        if self.index >= len(self.blogs):
            self.index = 0

        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )

    @discord.ui.button(label="Volver al perfil", style=discord.ButtonStyle.primary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Regresar al perfil. Si es Tinder, restaura la TinderView; si no, None."""
        await interaction.response.edit_message(
            embed=self.profile_embed,
            view=self.tinder_view  # None si es show, TinderView si viene de tinder
        )