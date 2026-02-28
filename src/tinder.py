import discord
from discord import app_commands
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

class TinderView(discord.ui.View):
    def __init__(self, profiles, current_user_id):
        super().__init__(timeout=None)
        self.profiles = profiles
        self.index = 0
        self.current_user_id = current_user_id

    async def send_next(self, interaction):
        # Ciclo hasta encontrar perfil válido
        while True:
            profile = self.profiles[self.index]
            self.index = (self.index + 1) % len(self.profiles)
            if str(profile["user_id"]) != str(self.current_user_id) and \
               str(profile["user_id"]) not in profile.get("already_seen", []):
                self.current_profile = profile
                break

        embed = discord.Embed(title=f"💘 {self.current_profile['name']}",
                              description=self.current_profile['description'],
                              color=discord.Color.pink())
        embed.add_field(name="Que te interesa", value=", ".join(self.current_profile["interests"]), inline=False)
        embed.add_field(name="Lineas", value=self.current_profile["lines"], inline=False)
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{self.current_profile['user_id']}/avatar.png")

        if hasattr(interaction, "response"):
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.send(embed=embed, view=self)

    @discord.ui.button(emoji="🟩", style=discord.ButtonStyle.green)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = await asyncpg.connect(DATABASE_URL)

        # Añadir a matches del usuario
        await conn.execute("""
            UPDATE profiles
            SET matches = array_append(matches, $1)
            WHERE user_id = $2
        """, str(self.current_profile["user_id"]), str(self.current_user_id))

        # Comprobar si match mutuo
        other = await conn.fetchrow("SELECT matches FROM profiles WHERE user_id = $1", self.current_profile["user_id"])
        if str(self.current_user_id) in other["matches"]:
            # Match mutuo
            user = interaction.user
            other_user = interaction.client.get_user(int(self.current_profile["user_id"]))
            try:
                await user.send(f"💘 ¡Has hecho match con {other_user.name}!")
                await other_user.send(f"💘 ¡Has hecho match con {user.name}!")
            except:
                pass

        await conn.close()
        await self.send_next(interaction)

    @discord.ui.button(emoji="🟥", style=discord.ButtonStyle.red)
    async def pass_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_next(interaction)


async def tinder_callback(interaction: discord.Interaction):
    conn = await asyncpg.connect(DATABASE_URL)
    profiles = await conn.fetch("SELECT * FROM profiles")
    await conn.close()

    view = TinderView(profiles, interaction.user.id)
    await view.send_next(interaction)

tinder = app_commands.Command(
    name="tinder",
    description="Descubre perfiles y haz match",
    callback=tinder_callback
)