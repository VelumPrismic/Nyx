import json
import discord
from discord.ext import commands
from discord import app_commands
from db import get_all_panels, get_panel, upsert_panel, delete_panel

DARK_COLOR = 0x2b2d31


# ── USER-FACING ROLE SELECT (published panel) ────────────

class UserRoleSelect(discord.ui.Select):
    def __init__(self, role_ids: list[int], guild: discord.Guild):
        options = []
        for rid in role_ids:
            role = guild.get_role(rid)
            if role:
                options.append(discord.SelectOption(label=role.name, value=str(rid)))
        if not options:
            options.append(discord.SelectOption(label="No roles available", value="0"))
        super().__init__(
            custom_id="user_role_select",
            placeholder="Choose your roles...",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        row = await get_panel(str(interaction.message.id))
        if not row:
            return await interaction.response.send_message("This panel is no longer active.", ephemeral=True)

        panel_roles = set(json.loads(row["roles"]))
        selected = set(int(v) for v in self.values)
        member = interaction.user
        current = set(r.id for r in member.roles)

        changes = []
        for rid in (panel_roles & selected) - current:
            role = interaction.guild.get_role(rid)
            if role and role < interaction.guild.me.top_role:
                try:
                    await member.add_roles(role, reason="Role panel")
                    changes.append(f"Role '{role.name}' has been added.")
                except discord.Forbidden:
                    changes.append(f"❌ {role.name} (no permission)")

        for rid in (panel_roles & current) - selected:
            role = interaction.guild.get_role(rid)
            if role:
                try:
                    await member.remove_roles(role, reason="Role panel")
                    changes.append(f"Role '{role.name}' has been removed.")
                except discord.Forbidden:
                    changes.append(f"❌ {role.name} (no permission)")

        if changes:
            embed = discord.Embed(
                title="Roles Updated",
                description="\n".join(changes),
                color=DARK_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("No changes needed.", ephemeral=True)


# ── DESCRIPTION MODAL ─────────────────────────────────────

class DescriptionModal(discord.ui.Modal, title="Panel Description"):
    desc = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.long,
        required=False,
        max_length=4000,
        placeholder="Write your panel description here...",
    )

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        row = await get_panel(str(self.message_id))
        if not row:
            return await interaction.response.send_message("Setup expired.", ephemeral=True)

        await upsert_panel(
            str(self.message_id),
            str(interaction.guild_id),
            title=row["title"],
            description=self.desc.value,
            color=row["color"],
            role_ids=json.loads(row["roles"]),
            is_draft=True,
        )

        embed = setup_embed(row["title"], self.desc.value, row["color"], json.loads(row["roles"]), interaction.guild)
        await interaction.response.edit_message(embed=embed)


# ── ADMIN SETUP DROPDOWNS ─────────────────────────────────

class RolePicker(discord.ui.Select):
    def __init__(self, guild: discord.Guild, selected: list[int]):
        options = []
        for role in guild.roles:
            if not role.managed and role != guild.default_role and role < guild.me.top_role:
                options.append(discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    default=role.id in selected,
                ))
        super().__init__(
            placeholder="Select roles to include...",
            min_values=0,
            max_values=len(options) or 1,
            options=options or [discord.SelectOption(label="No roles available", value="0")],
        )

    async def callback(self, interaction: discord.Interaction):
        selected = [int(v) for v in self.values]
        msg_id = str(interaction.message.id)
        row = await get_panel(msg_id)
        if not row:
            return await interaction.response.send_message("Setup expired.", ephemeral=True)

        await upsert_panel(
            msg_id,
            str(interaction.guild_id),
            title=row["title"],
            description=row["description"],
            color=row["color"],
            role_ids=selected,
            is_draft=True,
        )

        embed = setup_embed(row["title"], row["description"], row["color"], selected, interaction.guild)
        view = SetupView()
        await interaction.response.edit_message(embed=embed, view=view)


class ChannelPicker(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [
            discord.SelectOption(label=f"#{c.name}", value=str(c.id))
            for c in guild.text_channels
            if c.permissions_for(guild.me).send_messages
        ][:25]
        super().__init__(placeholder="Pick a channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(int(self.values[0]))
        if not channel:
            return await interaction.response.send_message("Channel not found.", ephemeral=True)

        msg_id = str(interaction.message.id)
        row = await get_panel(msg_id)
        if not row or not json.loads(row["roles"]):
            return await interaction.response.send_message("Add at least one role first.", ephemeral=True)

        role_ids = json.loads(row["roles"])
        embed = discord.Embed(
            title=row["title"],
            description=row["description"] or None,
            color=row["color"],
        )
        role_mentions = []
        for rid in role_ids:
            r = interaction.guild.get_role(rid)
            if r:
                role_mentions.append(f"• {r.mention}")
        if role_mentions:
            embed.add_field(name="Roles", value="\n".join(role_mentions), inline=False)

        panel_msg = await channel.send(embed=embed)
        gid = str(interaction.guild_id)

        await upsert_panel(
            str(panel_msg.id),
            gid,
            channel_id=channel.id,
            title=row["title"],
            description=row["description"],
            color=row["color"],
            roles=role_ids,
            is_draft=False,
        )
        await delete_panel(msg_id)

        view = PanelView(interaction.client, role_ids, interaction.guild.id)
        await panel_msg.edit(view=view)
        interaction.client.add_view(view, message_id=panel_msg.id)

        await interaction.response.send_message(f"Panel sent to {channel.mention}.", ephemeral=True)


class SetupView(discord.ui.View):
    @discord.ui.button(label="Manage Roles", style=discord.ButtonStyle.primary)
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await get_panel(str(interaction.message.id))
        if not row:
            return await interaction.response.send_message("Setup expired.", ephemeral=True)

        picker = RolePicker(interaction.guild, json.loads(row["roles"]))
        view = discord.ui.View(timeout=300)
        view.add_item(picker)
        await interaction.response.edit_message(view=view)

    @discord.ui.button(label="Description", style=discord.ButtonStyle.secondary)
    async def description(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await get_panel(str(interaction.message.id))
        if not row:
            return await interaction.response.send_message("Setup expired.", ephemeral=True)

        modal = DescriptionModal(interaction.message.id)
        if row["description"]:
            modal.desc.default = row["description"]
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Publish", style=discord.ButtonStyle.success)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await get_panel(str(interaction.message.id))
        if not row:
            return await interaction.response.send_message("Setup expired.", ephemeral=True)
        if not json.loads(row["roles"]):
            return await interaction.response.send_message("Add at least one role first.", ephemeral=True)

        picker = ChannelPicker(interaction.guild)
        view = discord.ui.View(timeout=300)
        view.add_item(picker)
        await interaction.response.edit_message(view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_panel(str(interaction.message.id))
        await interaction.response.edit_message(content="Setup cancelled.", embed=None, view=None)


class PanelView(discord.ui.View):
    def __init__(self, bot, role_ids: list[int], guild_id: int):
        super().__init__(timeout=None)
        guild = bot.get_guild(guild_id)
        if guild:
            self.add_item(UserRoleSelect(role_ids, guild))


def setup_embed(title, description, color, role_ids, guild):
    embed = discord.Embed(title="Panel Setup", color=color)
    if description:
        embed.add_field(name="Description", value=description, inline=False)
    if role_ids:
        lines = [f"• {guild.get_role(r).mention}" for r in role_ids if guild.get_role(r)]
        embed.add_field(name=f"Roles ({len(lines)})", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Roles (0)", value="No roles added yet.", inline=False)
    return embed


# ── COG ───────────────────────────────────────────────────

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        panels = await get_all_panels()
        for msg_id, panel in panels.items():
            if not msg_id.isdigit():
                continue
            roles = json.loads(panel["roles"])
            if roles:
                view = PanelView(self.bot, roles, int(panel["guild_id"]))
                self.bot.add_view(view, message_id=int(msg_id))

    @app_commands.command()
    @app_commands.describe(
        title="Panel title (default: Reaction Roles)",
        color="Hex color (e.g. #2b2d31)",
    )
    async def panel(self, interaction: discord.Interaction, title: str = None, color: str = None):
        if color:
            try:
                color = int(color.lstrip("#"), 16)
            except ValueError:
                return await interaction.response.send_message("Invalid color. Use a hex like `#ff0000`.", ephemeral=True)

        draft_title = title or "Reaction Roles"
        draft_color = color or DARK_COLOR
        draft = {
            "title": draft_title,
            "description": "",
            "color": draft_color,
            "role_ids": [],
        }

        embed = setup_embed(draft_title, "", draft_color, [], interaction.guild)
        await interaction.response.send_message(embed=embed, view=SetupView())
        msg = await interaction.original_response()

        await upsert_panel(
            str(msg.id),
            str(interaction.guild.id),
            title=draft_title,
            color=draft_color,
            role_ids=[],
            is_draft=True,
        )


async def setup(bot):
    await bot.add_cog(Roles(bot))
