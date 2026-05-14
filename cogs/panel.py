import discord
from discord.ext import commands
from discord import app_commands
from utils import (
    DEFAULT_CATEGORIES, has_admin_role, has_staff_role,
    build_panel_embed, hex_to_int
)
from cogs.tickets import CategorySelectView
import json


# ── Modals ────────────────────────────────────────────────────────────────────

class PanelCreateModal(discord.ui.Modal, title='Create Ticket Panel'):
    panel_title = discord.ui.TextInput(
        label='Panel Title',
        default='📩 Open a Ticket — Titan Exchange',
        max_length=256
    )
    panel_description = discord.ui.TextInput(
        label='Panel Description',
        style=discord.TextStyle.paragraph,
        default=(
            "╔══════════════════════════╗\n"
            "       🏦 TITAN EXCHANGE\n"
            "╚══════════════════════════╝\n\n"
            "📊 **Exchange Rates**\n"
            "──────────────────────────\n"
            "🟢 **INR → CRYPTO**\n"
            "> ₹101 / $1 — Any Amount\n\n"
            "🔴 **CRYPTO → INR**\n"
            "> Below $100 → ₹97.5 / $1\n"
            "> Above $100 → ₹98.5 / $1\n\n"
            "🔄 **CRYPTO → CRYPTO**\n"
            "> 0.5% Transaction Fee\n"
            "──────────────────────────\n"
            "✅ Fixed Rates — No Negotiation\n"
            "📌 Minimum Exchange: $1\n"
            "⏳ Be Patient. Don't Ping Staff.\n"
            "🚫 Don't open tickets for no reason."
        ),
        max_length=4000,
        required=True
    )
    panel_color = discord.ui.TextInput(
        label='Embed Color (hex, e.g. #FFD700)',
        default='#2F3136',
        max_length=10,
        required=False
    )
    panel_footer = discord.ui.TextInput(
        label='Footer Text (optional)',
        default='Titan Exchange | Select a category below',
        max_length=256,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        panel_data = {
            'title': self.panel_title.value,
            'description': self.panel_description.value,
            'color': hex_to_int(self.panel_color.value or '#2F3136'),
            'footer': self.panel_footer.value or None,
        }
        await interaction.response.send_message(
            '✅ Panel data received! Now select which categories to show on this panel.',
            ephemeral=True,
            view=CategoryPickerView(interaction.client, panel_data, interaction.channel)
        )


class CategoryPickerView(discord.ui.View):
    """Let the admin pick which categories appear on the panel."""

    def __init__(self, bot, panel_data: dict, target_channel: discord.TextChannel):
        super().__init__(timeout=120)
        self.bot = bot
        self.panel_data = panel_data
        self.target_channel = target_channel
        self.selected = []

        options = [
            discord.SelectOption(
                label=c['label'],
                value=c['value'],
                emoji=c.get('emoji'),
                description=c.get('description', '')
            )
            for c in DEFAULT_CATEGORIES
        ]
        select = discord.ui.Select(
            placeholder='Select categories for this panel...',
            options=options,
            min_values=1,
            max_values=len(options)
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        values = interaction.data['values']
        cats = [c for c in DEFAULT_CATEGORIES if c['value'] in values]
        self.panel_data['categories'] = cats

        embed = build_panel_embed(
            self.panel_data['title'],
            self.panel_data['description'],
            self.panel_data['color'],
            self.panel_data.get('footer'),
            self.panel_data.get('thumbnail')
        )
        view = CategorySelectView(self.bot, cats)
        panel_msg = await self.target_channel.send(embed=embed, view=view)

        # Save to DB
        await self.bot.db.create_panel(
            interaction.guild.id,
            self.target_channel.id,
            panel_msg.id,
            self.panel_data['title'],
            self.panel_data['description'],
            self.panel_data['color'],
            self.panel_data.get('footer'),
            self.panel_data.get('thumbnail'),
            cats
        )

        await interaction.response.edit_message(
            content=f'✅ Panel sent to {self.target_channel.mention}!',
            view=None
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self._restore_panels())

    async def _restore_panels(self):
        """Re-register all panel views on bot restart."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            panels = await self.bot.db.get_all_panels(guild.id)
            for panel in panels:
                if panel['categories']:
                    self.bot.add_view(
                        CategorySelectView(self.bot, panel['categories']),
                        message_id=panel['message_id']
                    )

    # ── Slash commands ────────────────────────────────────────────────────────

    panel_group = app_commands.Group(name='panel', description='Manage ticket panels')

    @panel_group.command(name='create', description='Create a new ticket panel in this channel')
    async def slash_panel_create(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await interaction.response.send_modal(PanelCreateModal())

    @panel_group.command(name='list', description='List all panels in this server')
    async def slash_panel_list(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        if not panels:
            return await interaction.response.send_message('📭 No panels found.', ephemeral=True)
        embed = discord.Embed(title='📋 Ticket Panels', color=0x5865F2)
        for p in panels:
            ch = interaction.guild.get_channel(p['channel_id'])
            embed.add_field(
                name=f"ID {p['id']} — {p['title']}",
                value=f"Channel: {ch.mention if ch else 'unknown'} | Categories: {len(p['categories'])}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @panel_group.command(name='delete', description='Delete a panel by ID')
    @app_commands.describe(panel_id='Panel ID (use /panel list to find it)')
    async def slash_panel_delete(self, interaction: discord.Interaction, panel_id: int):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        panel = next((p for p in panels if p['id'] == panel_id), None)
        if not panel:
            return await interaction.response.send_message('❌ Panel not found.', ephemeral=True)

        # Try to delete the message
        try:
            ch = interaction.guild.get_channel(panel['channel_id'])
            if ch:
                msg = await ch.fetch_message(panel['message_id'])
                await msg.delete()
        except Exception:
            pass

        await self.bot.db.delete_panel(panel_id)
        await interaction.response.send_message(f'✅ Panel `{panel_id}` deleted.', ephemeral=True)

    @panel_group.command(name='send', description='Send an existing panel to a different channel')
    @app_commands.describe(panel_id='Panel ID', channel='Target channel')
    async def slash_panel_send(self, interaction: discord.Interaction,
                                panel_id: int, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        panel = next((p for p in panels if p['id'] == panel_id), None)
        if not panel:
            return await interaction.response.send_message('❌ Panel not found.', ephemeral=True)

        embed = build_panel_embed(panel['title'], panel['description'], panel['color'],
                                  panel.get('footer'), panel.get('thumbnail'))
        view = CategorySelectView(self.bot, panel['categories'])
        msg = await channel.send(embed=embed, view=view)
        await self.bot.db.update_panel_message(panel_id, msg.id)
        await interaction.response.send_message(
            f'✅ Panel sent to {channel.mention}!', ephemeral=True
        )

    # ── Prefix commands ───────────────────────────────────────────────────────

    @commands.command(name='panel')
    @commands.has_permissions(administrator=True)
    async def prefix_panel(self, ctx: commands.Context, action: str = 'help', panel_id: int = None):
        """Manage panels: !panel create | list | delete <id> | send <id> #channel"""
        if action == 'create':
            await ctx.send('Use `/panel create` (slash command) to open the panel builder modal.')
        elif action == 'list':
            panels = await self.bot.db.get_all_panels(ctx.guild.id)
            if not panels:
                return await ctx.send('📭 No panels found.')
            embed = discord.Embed(title='📋 Ticket Panels', color=0x5865F2)
            for p in panels:
                ch = ctx.guild.get_channel(p['channel_id'])
                embed.add_field(
                    name=f"ID {p['id']} — {p['title']}",
                    value=f"Channel: {ch.mention if ch else 'unknown'} | Categories: {len(p['categories'])}",
                    inline=False
                )
            await ctx.send(embed=embed)
        elif action == 'delete' and panel_id:
            panels = await self.bot.db.get_all_panels(ctx.guild.id)
            panel = next((p for p in panels if p['id'] == panel_id), None)
            if not panel:
                return await ctx.send('❌ Panel not found.')
            try:
                ch = ctx.guild.get_channel(panel['channel_id'])
                if ch:
                    msg = await ch.fetch_message(panel['message_id'])
                    await msg.delete()
            except Exception:
                pass
            await self.bot.db.delete_panel(panel_id)
            await ctx.send(f'✅ Panel `{panel_id}` deleted.')
        else:
            await ctx.send(
                '**Panel Commands:**\n'
                '`/panel create` — Create a new panel (modal)\n'
                '`!panel list` — List all panels\n'
                '`!panel delete <id>` — Delete a panel\n'
                '`/panel send <id> #channel` — Re-send panel to another channel'
            )


async def setup(bot):
    await bot.add_cog(Panel(bot))