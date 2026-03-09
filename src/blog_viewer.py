import discord
from src.blog_db import get_blogs

class BlogViewer(discord.ui.View):

    def __init__(self, user, profile_embed):
        super().__init__(timeout=300)

        self.user = user
        self.index = 0
        self.blogs = []
        self.profile_embed = profile_embed


    async def load(self):
        self.blogs = await get_blogs(self.user.id)


    def create_embed(self):

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

        if blog["image"] != "nothing":
            embed.set_image(url=blog["image"])

        embed.set_footer(text=f"{self.index+1}/{len(self.blogs)}")

        return embed


    @discord.ui.button(label="⬅", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.blogs:
            return

        self.index -= 1
        if self.index < 0:
            self.index = len(self.blogs)-1

        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )


    @discord.ui.button(label="➡", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):

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

        await interaction.response.edit_message(
            embed=self.profile_embed,
            view=None
        )