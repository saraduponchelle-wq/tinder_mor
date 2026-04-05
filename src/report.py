# src/report.py

import discord
import asyncpg
import os

from embed.create_profile import create_profile_embed

DATABASE_URL = os.getenv("DATABASE_URL")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID"))

EMOJI_YES = str(os.getenv("YES"))
EMOJI_NO = str(os.getenv("NO"))


async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


# ==========================================================
# DB HELPERS
# ==========================================================

async def is_banned(user_id: int) -> bool:
    conn = await get_connection()
    row = await conn.fetchrow("SELECT user_id FROM ban WHERE user_id = $1", user_id)
    await conn.close()
    return row is not None


async def ban_user(user_id: int, motivo: str):
    conn = await get_connection()

    # Insertar en tabla ban
    await conn.execute(
        """
        INSERT INTO ban (user_id, motivo)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET motivo = $2
        """,
        user_id, motivo
    )

    # Borrar perfil
    await conn.execute("DELETE FROM profiles WHERE user_id = $1", user_id)

    await conn.close()


# ==========================================================
# MODAL: motivo del reporte (lo abre el usuario en /tinder)
# ==========================================================

class ReportModal(discord.ui.Modal, title="Reportar usuario"):

    motivo_input = discord.ui.TextInput(
        label="Motivo del reporte",
        style=discord.TextStyle.paragraph,
        placeholder="Describe qué ocurrió...",
        required=True,
        max_length=1000
    )

    def __init__(self, reported_user_id: int, profile_data: dict, discord_user: discord.User):
        super().__init__()
        self.reported_user_id = reported_user_id
        self.profile_data = profile_data
        self.discord_user = discord_user

    async def on_submit(self, interaction: discord.Interaction):

        motivo = self.motivo_input.value.strip()

        report_channel = interaction.client.get_channel(REPORT_CHANNEL_ID)

        if not report_channel:
            await interaction.response.send_message(
                f"{EMOJI_NO} Error interno: canal de reportes no encontrado.",
                ephemeral=True
            )
            return

        # Embed del perfil reportado
        embed = create_profile_embed(self.profile_data, self.discord_user, show_discord=True)
        embed.title = f"🚨 Reporte — {self.profile_data.get('name', 'Usuario')}"
        embed.color = discord.Color.red()

        embed.add_field(
            name="📋 Motivo del reporte",
            value=motivo,
            inline=False
        )
        embed.add_field(
            name="👤 Reportado por",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)",
            inline=False
        )
        embed.set_footer(text=f"ID usuario reportado: {self.reported_user_id}")

        view = ReviewReportView(
            reported_user_id=self.reported_user_id,
            discord_user=self.discord_user
        )

        await report_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"{EMOJI_YES} Reporte enviado. Los moderadores lo revisarán.",
            ephemeral=True
        )


# ==========================================================
# MODAL: motivo del baneo (lo abre el moderador)
# ==========================================================

class BanModal(discord.ui.Modal, title="Motivo del baneo"):

    motivo_input = discord.ui.TextInput(
        label="Motivo del baneo",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe el motivo oficial del baneo...",
        required=True,
        max_length=1000
    )

    def __init__(self, reported_user_id: int, discord_user: discord.User, report_message: discord.Message):
        super().__init__()
        self.reported_user_id = reported_user_id
        self.discord_user = discord_user
        self.report_message = report_message

    async def on_submit(self, interaction: discord.Interaction):

        motivo = self.motivo_input.value.strip()

        # Verificar que no esté ya baneado
        if await is_banned(self.reported_user_id):
            await interaction.response.send_message(
                "⚠️ Este usuario ya estaba baneado.",
                ephemeral=True
            )
            return

        # Banear y borrar perfil
        await ban_user(self.reported_user_id, motivo)

        # Notificar al usuario baneado por DM
        try:
            await self.discord_user.send(
                f"🚫 Has sido **baneado** del sistema.\n\n"
                f"**Motivo:** {motivo}\n\n"
                f"Si crees que es un error, contacta con un administrador."
            )
        except Exception as e:
            print(f"[WARN] No se pudo notificar al baneado {self.reported_user_id}: {e}")

        # Editar el mensaje del reporte para marcar como resuelto
        try:
            original_embed = self.report_message.embeds[0] if self.report_message.embeds else None

            if original_embed:
                original_embed.color = discord.Color.dark_red()
                original_embed.add_field(
                    name="✅ Resuelto",
                    value=f"Baneado por {interaction.user.mention}\n**Motivo:** {motivo}",
                    inline=False
                )
                await self.report_message.edit(embed=original_embed, view=None)
        except Exception as e:
            print(f"[WARN] No se pudo editar el mensaje del reporte: {e}")

        await interaction.response.send_message(
            f"🚫 Usuario `{self.reported_user_id}` baneado correctamente.",
            ephemeral=True
        )


# ==========================================================
# VIEW: botones de revisión del reporte (para moderadores)
# ==========================================================

class ReviewReportView(discord.ui.View):

    def __init__(self, reported_user_id: int, discord_user: discord.User):
        super().__init__(timeout=None)
        self.reported_user_id = reported_user_id
        self.discord_user = discord_user

    # 🔴 BANEAR
    @discord.ui.button(label="🚫 Banear", style=discord.ButtonStyle.danger)
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(
            BanModal(
                reported_user_id=self.reported_user_id,
                discord_user=self.discord_user,
                report_message=interaction.message
            )
        )

    # 🟢 SIN PROBLEMA
    @discord.ui.button(label="✅ Sin problema", style=discord.ButtonStyle.success)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        try:
            original_embed = interaction.message.embeds[0] if interaction.message.embeds else None

            if original_embed:
                original_embed.color = discord.Color.green()
                original_embed.add_field(
                    name="✅ Resuelto",
                    value=f"Revisado por {interaction.user.mention} — sin infracción.",
                    inline=False
                )
                await interaction.message.edit(embed=original_embed, view=None)
        except Exception as e:
            print(f"[WARN] No se pudo editar el mensaje del reporte: {e}")

        await interaction.response.send_message(
            "✅ Reporte descartado.",
            ephemeral=True
        )
