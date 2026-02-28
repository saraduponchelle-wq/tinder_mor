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

        bot.tree.add_command(start)
        bot.tree.add_command(update)

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