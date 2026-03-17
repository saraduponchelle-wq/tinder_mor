import discord
from discord import app_commands
from discord import RawReactionActionEvent
from src.blog_notifications import get_users_with_news_enabled
import os
from src.database import init_db


ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))


class MyBot(discord.Client):
    def __init__(self):

        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        from src.start import start
        from src.update import update
        from src.show import show
        from src.delete import delete
        from src.tinder import tinder
        from src.blog import blog
        from src.blog_notifications import news
        from commands.set_channels import set_blogchannel, set_onlineusers

        self.tree.add_command(blog)
        self.tree.add_command(start)
        self.tree.add_command(update)
        self.tree.add_command(show)
        self.tree.add_command(delete)
        self.tree.add_command(tinder)
        self.tree.add_command(news)
        self.tree.add_command(set_blogchannel)
        self.tree.add_command(set_onlineusers)

        await self.tree.sync()
        print("✅ Slash commands sincronizados")

bot = MyBot()

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if bot.user in message.mentions:
        await message.reply(
            f"💌 Hola {message.author.mention}!\n\n"
            "Si necesitas ayuda usa **/help** para ver todos mis comandos.\n"
            "Quizás tu próximo **match** está más cerca de lo que crees 💖"
        )

    await bot.process_commands(message)

@bot.tree.command(name="help", description="Muestra todos los comandos del bot")
async def help_command(interaction: discord.Interaction):

    embed = discord.Embed(
        title="💖 Ayuda del Bot",
        description="Un pequeño sistema **Tinder dentro de Discord**.",
        color=discord.Color.pink()
    )

    embed.add_field(
        name="👤 Perfiles",
        value=(
            "`/start` → Crear tu perfil\n"
            "`/update` → Editar tu perfil\n"
            "`/show` → Ver tu perfil o el de otro usuario"
        ),
        inline=False
    )

    embed.add_field(
        name="🔥 Matches",
        value=(
            "`/tinder` → Ver perfiles y dar **Like** o **Pass**\n"
            "Si ambos dan like → ¡**Match**! 💖"
        ),
        inline=False
    )

    embed.add_field(
        name="📝 Blogs",
        value=(
            "Puedes escribir pequeños **blogs personales**.\n"
            "Otros usuarios pueden verlos desde tu perfil."
        ),
        inline=False
    )

    embed.add_field(
        name="📰 News",
        value=(
            "Quieres recibir al privado cuando alguien suba un blog.\n"
            "Activa esta opcion y recibiras las busquedasd de rol."
        ),
        inline=False
    )

    embed.set_footer(text="¡Diviértete conociendo gente nueva! 💌")

    await interaction.response.send_message(embed=embed, ephemeral=True)


from events.online_profiles import OnlineProfiles

@bot.event
async def on_ready():
    
    await init_db()
    print(f"🤖 Conectado como {bot.user}")

    if not hasattr(bot, "online_profiles"):
        from events.online_profiles import OnlineProfiles
        bot.online_profiles = OnlineProfiles(bot)

    await bot.change_presence(
        activity=discord.Game("❤️ Buscando matches")
    )

import os

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN no encontrado")

print("✅ Token cargado correctamente")
bot.run(TOKEN)