import discord
from discord.ext import commands
from discord import app_commands
from db import get_all_stickies, upsert_sticky, delete_sticky

DARK_COLOR = 0x2b2d31


class StickyMessageModal(discord.ui.Modal, title="Sticky Message"):
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        required=True,
        max_length=4000,
        placeholder="Write the sticky message content here...",
    )

    def __init__(self, channel: discord.TextChannel, cog):
        super().__init__()
        self.channel = channel
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        msg_id = await self.cog._refresh_sticky(self.channel, self.message.value)

        await upsert_sticky(str(self.channel.id), str(interaction.guild_id), self.message.value, str(msg_id))
        self.cog.stickies[str(self.channel.id)] = {
            "channel_id": self.channel.id,
            "guild_id": interaction.guild_id,
            "content": self.message.value,
            "last_message_id": str(msg_id),
        }

        embed = discord.Embed(
            description=f"Sticky message set in {self.channel.mention}",
            color=DARK_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ChannelSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild, cog):
        options = [
            discord.SelectOption(label=f"#{c.name}", value=str(c.id))
            for c in guild.text_channels
            if c.permissions_for(guild.me).send_messages
        ][:25]
        super().__init__(placeholder="Pick a channel...", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(int(self.values[0]))
        if not channel:
            return await interaction.response.send_message("Channel not found.", ephemeral=True)

        await interaction.response.send_modal(StickyMessageModal(channel, self.cog))


class Sticky(commands.Cog):
    """Keep a message pinned to the bottom of a channel."""

    def __init__(self, bot):
        self.bot = bot
        self.stickies = {}

    async def cog_load(self):
        self.stickies = await get_all_stickies()

    sticky = app_commands.Group(name="sticky", description="Manage sticky messages")

    async def _refresh_sticky(self, channel, content, old_message_id=None):
        if old_message_id:
            try:
                old = await channel.fetch_message(old_message_id)
                await old.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        embed = discord.Embed(description=content, color=DARK_COLOR)
        msg = await channel.send(embed=embed)
        return msg.id

    @sticky.command(name="set")
    async def set(self, interaction: discord.Interaction):
        """Set a sticky message that stays at the bottom of a channel."""
        view = discord.ui.View(timeout=300)
        view.add_item(ChannelSelect(interaction.guild, self))
        await interaction.response.send_message("Select a channel:", view=view, ephemeral=True)

    @sticky.command(name="stop")
    @app_commands.describe(channel="The channel to remove the sticky from")
    async def stop(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove the sticky message from a channel."""
        sticky_id = str(channel.id)
        if sticky_id not in self.stickies:
            return await interaction.response.send_message("No sticky is set in that channel.", ephemeral=True)

        try:
            old = await channel.fetch_message(int(self.stickies[sticky_id]["last_message_id"]))
            await old.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        await delete_sticky(sticky_id)
        del self.stickies[sticky_id]

        embed = discord.Embed(
            description=f"Sticky removed from {channel.mention}",
            color=DARK_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @sticky.command(name="list")
    async def list_channels(self, interaction: discord.Interaction):
        """List all active sticky messages in this server."""
        guild_stickies = {k: v for k, v in self.stickies.items() if v["guild_id"] == interaction.guild_id}

        if not guild_stickies:
            return await interaction.response.send_message("No active stickies in this server.", ephemeral=True)

        lines = []
        for data in guild_stickies.values():
            ch = interaction.guild.get_channel(data["channel_id"])
            ch_mention = ch.mention if ch else "#deleted-channel"
            lines.append(f"- {ch_mention}: {data['content'][:80]}")

        embed = discord.Embed(
            title="Active Stickies",
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

        sticky_id = str(message.channel.id)
        if sticky_id not in self.stickies:
            return

        data = self.stickies[sticky_id]
        new_msg_id = await self._refresh_sticky(message.channel, data["content"], data.get("last_message_id"))
        self.stickies[sticky_id]["last_message_id"] = str(new_msg_id)
        await upsert_sticky(sticky_id, str(message.guild.id), data["content"], str(new_msg_id))


async def setup(bot):
    await bot.add_cog(Sticky(bot))
