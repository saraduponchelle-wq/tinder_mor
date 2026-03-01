import discord
from discord import app_commands
from discord import RawReactionActionEvent
from src.blog_notifications import get_users_with_news_enabled
import os

ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
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
        
        bot.tree.add_command(blog)
        self.tree.add_command(start)
        self.tree.add_command(update)
        self.tree.add_command(show)
        self.tree.add_command(delete)
        self.tree.add_command(tinder)
        self.tree.add_command(news)

        await self.tree.sync()
        print("✅ Slash commands sincronizados")

bot = MyBot()


@bot.event
async def on_raw_reaction_add(payload: RawReactionActionEvent):
    # Solo nos interesa 👍 en el canal de revisión
    if payload.channel_id != BLOG_REVIEW_CHANNEL_ID or str(payload.emoji) != "👍":
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or ADMIN_ROLE_ID not in [role.id for role in member.roles]:
        return  # no es admin

    channel = guild.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)

    # Obtener embed y autor
    if not msg.embeds:
        return
    embed = msg.embeds[0]

    # Buscar autor a partir del embed footer
    author_name = embed.footer.text.replace("Creado por ", "")
    blog_text = embed.description
    image_url = embed.image.url if embed.image else None

    # Enviar mensaje a todos los usuarios con news=True
    user_ids = await get_users_with_news_enabled()
    print(f"[DEBUG] Enviando blog a {len(user_ids)} usuarios")

    for user_id in user_ids:
        user = await bot.fetch_user(user_id)
        try:
            await user.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] No se pudo enviar a {user_id}: {e}")

@bot.event
async def on_ready():
    print(f"🤖 Conectado como {bot.user}")



import os


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN no encontrado")

print("✅ Token cargado correctamente")
bot.run(TOKEN)