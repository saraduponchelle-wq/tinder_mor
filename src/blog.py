# src/blog.py

import discord
from discord import app_commands
import asyncio
import os

from src.blog_db import add_blog
from src.blog_notifications import get_users_with_news_ez`nabled
from src.server_db import get_all_servers

BLOG_REVIEW_CHANNEL_ID = int(os.getenv("BLOG_REVIEW_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

EMOJI_NOTI = str(os.getenv("NOTI"))
EMOJI_MES = str(os.getenv("MES"))
EMOJI_YES = str(os.getenv("YES"))
EMOJI_NO = str(os.getenv("NO"))

# ===============================

# ENVIAR BLOG A REVISIÓN

# ===============================

async def post_blog_for_review(
    client: discord.Client,
    author: discord.User,
    blog_text: str,
    image_url: str | None
):

    channel = client.get_channel(BLOG_REVIEW_CHANNEL_ID)

    if not channel:
        print("[ERROR] Canal de revisión no encontrado")
        return

    embed = discord.Embed(
        title=f"{EMOJI_NOTI} Nuevo Blog de {author.display_name}",
        description=blog_text,
        color=discord.Color.red()
    )

    if image_url:
        embed.set_image(url=image_url)

    embed.set_footer(
        text=f"Creado por {author}",
        icon_url=author.display_avatar.url
    )

    msg = await channel.send(
        content=author.mention,
        embed=embed
    )

    await msg.add_reaction("👍")

    print(f"[DEBUG] Blog enviado a revisión {msg.id}")

    def check(reaction, user):

        if reaction.message.id != msg.id:
            return False

        if str(reaction.emoji) != "👍":
            return False

        if user.bot:
            return False

        member = msg.guild.get_member(user.id)

        return any(role.id == ADMIN_ROLE_ID for role in member.roles)

    try:

        reaction, user = await client.wait_for(
            "reaction_add",
            timeout=28800,
            check=check
        )

    except asyncio.TimeoutError:

        print("[DEBUG] Blog expiró sin aprobación")
        return

    print(f"[DEBUG] Blog aprobado por {user}")

    servers = await get_all_servers()

    for server in servers:

        channel_id = server["blog_channel_id"]

        if not channel_id:
            continue

        blog_channel = client.get_channel(channel_id)

        if not blog_channel:
            continue

        try:

            message = await blog_channel.send(
                content=author.mention,
                embed=embed
            )

            if blog_channel.is_news():
                await message.publish()

        except Exception as e:

            print(f"[ERROR] Blog no enviado a {channel_id}: {e}")

    user_ids = await get_users_with_news_enabled()

    for user_id in user_ids:

        try:

            u = await client.fetch_user(user_id)

            await u.send(embed=embed)

            await u.send(
                f"{EMOJI_MES} Si estás interesado, escríbele a {author.mention}"
            )

        except Exception as e:

            print(f"[ERROR] No se pudo enviar DM {user_id}: {e}")

    await add_blog(
        author.id,
        blog_text,
        image_url if image_url else "nothing"
    )

# ===============================

# MODAL TEXTO BLOG

# ===============================

class BlogTextModal(discord.ui.Modal, title="Escribe tu blog"):

```
blog_text_input = discord.ui.TextInput(
    label="Texto del blog",
    style=discord.TextStyle.paragraph,
    placeholder="Escribe tu contenido aquí...",
    required=True,
    max_length=4000
)

def __init__(self, author: discord.User):
    super().__init__()
    self.author = author

async def on_submit(self, interaction: discord.Interaction):

    blog_text = self.blog_text_input.value.strip()

    view = BlogImageButtonView(self.author, blog_text)

    await interaction.response.send_message(
        f"{EMOJI_YES} Texto recibido. ¿Quieres añadir una imagen?",
        view=view,
        ephemeral=True
    )
```

# ===============================

# BOTÓN AÑADIR IMAGEN

# ===============================

class BlogImageButtonView(discord.ui.View):

```
def __init__(self, author: discord.User, blog_text: str):
    super().__init__(timeout=None)
    self.author = author
    self.blog_text = blog_text

@discord.ui.button(
    label="Añadir imagen",
    style=discord.ButtonStyle.primary
)
async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):

    if interaction.user.id != self.author.id:

        await interaction.response.send_message(
            f"{EMOJI_NO} Solo el autor puede usar este botón.",
            ephemeral=True
        )

        return

    await interaction.response.send_modal(
        BlogImageModal(self.author, self.blog_text)
    )
```

# ===============================

# MODAL URL IMAGEN

# ===============================

class BlogImageModal(discord.ui.Modal, title="Añadir URL de la imagen"):

```
image_url_input = discord.ui.TextInput(
    label="URL de la imagen",
    style=discord.TextStyle.short,
    placeholder="https://ejemplo.com/imagen.png",
    required=True,
    max_length=2000
)

def __init__(self, author: discord.User, blog_text: str):
    super().__init__()
    self.author = author
    self.blog_text = blog_text

async def on_submit(self, interaction: discord.Interaction):

    image_url = self.image_url_input.value.strip()

    await interaction.response.send_message(
        f"{EMOJI_YES} Blog enviado para revisión.",
        ephemeral=True
    )

    await post_blog_for_review(
        interaction.client,
        self.author,
        self.blog_text,
        image_url
    )
```

# ===============================

# COMANDO /blog

# ===============================

async def crearblog_callback(interaction: discord.Interaction):

```
print(f"[DEBUG] /blog usado por {interaction.user}")

await interaction.response.send_modal(
    BlogTextModal(interaction.user)
)
```

blog = app_commands.Command(
name="blog",
description="Crea un blog con opción de añadir imagen",
callback=crearblog_callback
)
