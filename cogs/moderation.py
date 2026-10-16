import asyncio
import discord
from discord.ext import commands
from discord import app_commands

DARK_COLOR = 0x2b2d31


def mod_embed(description: str) -> discord.Embed:
    return discord.Embed(description=description, color=DARK_COLOR)


class BulkDeleteView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=120)
        self.guild = guild
        self._message: discord.Message | None = None
        self._timer_started = False

        self.channel_select = discord.ui.ChannelSelect(
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.voice,
                discord.ChannelType.category,
            ],
            min_values=1,
            max_values=25,
            placeholder="Select channels to delete...",
        )
        self.channel_select.callback = self._on_select
        self.add_item(self.channel_select)

        self.delete_button = discord.ui.Button(
            label="Delete Selected",
            style=discord.ButtonStyle.danger,
            disabled=True,
        )
        self.delete_button.callback = self._on_delete
        self.add_item(self.delete_button)

    async def _on_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not self._timer_started and self.channel_select.values:
            self._timer_started = True
            asyncio.create_task(self._enable_after_delay())

    async def _enable_after_delay(self):
        await asyncio.sleep(3)
        self.delete_button.disabled = False
        if self._message:
            await self._message.edit(view=self)

    async def _on_delete(self, interaction: discord.Interaction):
        selected = self.channel_select.values
        if not selected:
            return await interaction.response.send_message(
                embed=mod_embed("No channels selected."), ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        deleted = []
        failed = []
        for channel in selected:
            chan = self.guild.get_channel(channel.id)
            if not chan:
                failed.append(f"#{channel.name}")
                continue
            try:
                await chan.delete()
                deleted.append(f"#{chan.name}")
            except (discord.Forbidden, discord.HTTPException):
                failed.append(f"#{chan.name}")

        parts = []
        if deleted:
            parts.append(f"Deleted {len(deleted)} channel(s): {', '.join(deleted)}")
        if failed:
            parts.append(f"Failed: {', '.join(failed)}")

        await interaction.followup.send(embed=mod_embed("\n".join(parts)), ephemeral=True)
        self.stop()


class Moderation(commands.Cog):
    """Moderation commands."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(amount="Number of messages to delete")
    async def purge(self, interaction: discord.Interaction, amount: int):
        """Delete a number of messages."""
        if amount < 1:
            return await interaction.response.send_message(
                embed=mod_embed("You must purge at least 1 message."), ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=mod_embed(f"Deleted {len(deleted)} message(s)."), ephemeral=True,
        )

    @app_commands.command()
    @app_commands.describe(username="The username of the user to unban")
    async def unban(self, interaction: discord.Interaction, username: str):
        """Unban a user by their username."""
        await interaction.response.defer(ephemeral=True)

        matches = []
        async for ban_entry in interaction.guild.bans():
            if username.lower() in ban_entry.user.name.lower():
                matches.append(ban_entry.user)

        if not matches:
            return await interaction.followup.send(
                embed=mod_embed("No banned user found with that username."), ephemeral=True,
            )
        if len(matches) > 1:
            return await interaction.followup.send(
                embed=mod_embed(f"Multiple matches found. Use the ID instead: {', '.join(str(u.id) for u in matches)}"),
                ephemeral=True,
            )

        user = matches[0]
        try:
            await interaction.guild.unban(user)
            await interaction.followup.send(
                embed=mod_embed(f"**{user}** has been unbanned."), ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=mod_embed("I don't have permission to unban users."), ephemeral=True,
            )

    @app_commands.command()
    async def bulkdelete(self, interaction: discord.Interaction):
        """Bulk delete text, voice, or category channels."""
        view = BulkDeleteView(interaction.guild)
        await interaction.response.send_message(
            "Select channels to delete. The button will unlock in 3 seconds.",
            view=view,
            ephemeral=True,
        )
        view._message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Moderation(bot))
