import discord
from discord import app_commands

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

        self.tree.add_command(start)
        self.tree.add_command(update)
        self.tree.add_command(show)
        self.tree.add_command(delete)

        await self.tree.sync()
        print("✅ Slash commands sincronizados")

bot = MyBot()



@bot.event
async def on_ready():
    print(f"🤖 Conectado como {bot.user}")



import os


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN no encontrado")

print("✅ Token cargado correctamente")
bot.run(TOKEN)