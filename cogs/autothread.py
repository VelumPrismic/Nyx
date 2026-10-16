import discord
from discord.ext import commands
from discord import app_commands
from db import get_all_autothread, upsert_autothread, delete_autothread

DARK_COLOR = 0x2b2d31


class AutoThread(commands.Cog):
    """Automatically create threads for new messages in configured channels."""

    def __init__(self, bot):
        self.bot = bot
        self.config = {}

    async def cog_load(self):
        self.config = await get_all_autothread()

    autothread = app_commands.Group(name="autothread", description="Manage auto-threading")

    @autothread.command(name="add")
    @app_commands.describe(channel="The channel to enable auto-threading in")
    async def add(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Automatically create a thread for every new message in a channel."""
        config_id = str(channel.id)
        await upsert_autothread(config_id, str(interaction.guild_id))
        self.config[config_id] = {
            "channel_id": channel.id,
            "guild_id": interaction.guild_id,
        }

        embed = discord.Embed(
            description=f"Auto-threading enabled in {channel.mention}",
            color=DARK_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @autothread.command(name="remove")
    @app_commands.describe(channel="The channel to disable auto-threading in")
    async def remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Disable auto-threading for a channel."""
        config_id = str(channel.id)
        if config_id not in self.config:
            return await interaction.response.send_message("Auto-threading is not enabled in that channel.", ephemeral=True)

        await delete_autothread(config_id)
        del self.config[config_id]

        embed = discord.Embed(
            description=f"Auto-threading disabled in {channel.mention}",
            color=DARK_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @autothread.command(name="list")
    async def list_channels(self, interaction: discord.Interaction):
        """List all channels with auto-threading enabled."""
        guild_configs = {k: v for k, v in self.config.items() if v["guild_id"] == interaction.guild_id}

        if not guild_configs:
            return await interaction.response.send_message("No auto-thread channels configured in this server.", ephemeral=True)

        lines = []
        for data in guild_configs.values():
            ch = interaction.guild.get_channel(data["channel_id"])
            ch_mention = ch.mention if ch else "#deleted-channel"
            lines.append(f"- {ch_mention}")

        embed = discord.Embed(
            title="Auto-Thread Channels",
            description="\n".join(lines),
            color=DARK_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        config_id = str(message.channel.id)
        if config_id not in self.config:
            return

        try:
            thread_name = (message.clean_content or "New thread")[:100]
            await message.create_thread(name=thread_name, auto_archive_duration=1440)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(AutoThread(bot))
