import discord
from discord import app_commands
from src.server_db import set_blog_channel, set_online_channel


# ===============================
# /set_blogchannel
# ===============================

@app_commands.command(
    name="set_blogchannel",
    description="Configura el canal donde se publicarán los blogs"
)
@app_commands.checks.has_permissions(administrator=True)

async def set_blogchannel(interaction: discord.Interaction, channel: discord.TextChannel):

    await interaction.response.defer(ephemeral=True)

    try:

        await set_blog_channel(
            interaction.guild.id,
            channel.id,
            interaction.guild.name
        )

        await interaction.followup.send(
            f"✅ Canal de blogs configurado: {channel.mention}"
        )

    except Exception as e:

        print("ERROR set_blogchannel:", e)

        await interaction.followup.send(
            "❌ Error guardando el canal."
        )


# ===============================
# /set_onlineusers
# ===============================

@app_commands.command(
    name="set_onlineusers",
    description="Configura el canal donde se mostrarán los usuarios online"
)
@app_commands.checks.has_permissions(administrator=True)

async def set_onlineusers(interaction: discord.Interaction, channel: discord.TextChannel):

    await interaction.response.defer(ephemeral=True)

    try:

        await set_online_channel(
            interaction.guild.id,
            channel.id,
            interaction.guild.name
        )

        await interaction.followup.send(
            f"✅ Canal de usuarios online configurado: {channel.mention}"
        )

    except Exception as e:

        print("ERROR set_onlineusers:", e)

        await interaction.followup.send(
            "❌ Error guardando el canal."
        )


# ===============================
# ERROR SI NO ES ADMIN
# ===============================

@set_blogchannel.error
@set_onlineusers.error
async def admin_error(interaction, error):

    if isinstance(error, app_commands.MissingPermissions):

        await interaction.response.send_message(
            "❌ Solo administradores pueden usar este comando.",
            ephemeral=True
        )