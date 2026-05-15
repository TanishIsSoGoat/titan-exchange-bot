import discord
from discord.ext import commands
from discord import app_commands
from utils import has_admin_role, has_staff_role, hex_to_int


# ── Ticket Modals ─────────────────────────────────────────────────────────────

class I2CModal(discord.ui.Modal, title='💸 INR → Crypto Exchange'):
    amount = discord.ui.TextInput(
        label='Amount (INR)',
        placeholder='Enter how much INR you want to exchange e.g. 1000',
        required=True, max_length=20
    )
    crypto = discord.ui.TextInput(
        label='Crypto Type',
        placeholder='Which crypto do you want? USDT / SOL / LTC / BTC',
        required=True, max_length=20
    )
    payment_app = discord.ui.TextInput(
        label='Payment App',
        placeholder='Which app will you pay from? MBK / GPay / PhonePay',
        required=True, max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            '💵 INR Amount': self.amount.value,
            '🪙 Crypto': self.crypto.value,
            '📱 Payment App': self.payment_app.value,
        }
        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._open_ticket(interaction, 'i2c', answers)


class C2IModal(discord.ui.Modal, title='💰 Crypto → INR Exchange'):
    amount = discord.ui.TextInput(
        label='Amount (USD $)',
        placeholder='Enter how much crypto (in $) you want to exchange e.g. 10',
        required=True, max_length=20
    )
    crypto = discord.ui.TextInput(
        label='Crypto Type',
        placeholder='Which crypto are you sending? USDT / SOL / LTC / BTC',
        required=True, max_length=20
    )
    wallet = discord.ui.TextInput(
        label='Your Wallet',
        placeholder='CWallet / TrustWallet / Other',
        required=True, max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            '💲 USD Amount': self.amount.value,
            '🪙 Crypto': self.crypto.value,
            '👛 Wallet': self.wallet.value,
        }
        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._open_ticket(interaction, 'c2i', answers)


class SupportModal(discord.ui.Modal, title='🎧 Support'):
    issue = discord.ui.TextInput(
        label='Describe your issue',
        placeholder='Tell us what you need help with...',
        style=discord.TextStyle.paragraph,
        required=True, max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        answers = {'📝 Issue': self.issue.value}
        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._open_ticket(interaction, 'support', answers)


class DisputeModal(discord.ui.Modal, title='⚠️ Dispute / Issue'):
    ticket_ref = discord.ui.TextInput(
        label='Ticket Reference (if any)',
        placeholder='e.g. #0012 or leave blank',
        required=False, max_length=20
    )
    description = discord.ui.TextInput(
        label='Describe the dispute',
        placeholder='What went wrong? Be as detailed as possible.',
        style=discord.TextStyle.paragraph,
        required=True, max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            '🔖 Reference': self.ticket_ref.value or 'None',
            '📝 Description': self.description.value,
        }
        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._open_ticket(interaction, 'dispute', answers)


# ── Dropdown ──────────────────────────────────────────────────────────────────

MODAL_MAP = {
    'i2c': I2CModal,
    'c2i': C2IModal,
    'support': SupportModal,
    'dispute': DisputeModal,
}

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label='I2C — INR to Crypto',
                value='i2c',
                emoji='💸',
                description='Exchange INR → Cryptocurrency'
            ),
            discord.SelectOption(
                label='C2I — Crypto to INR',
                value='c2i',
                emoji='💰',
                description='Exchange Cryptocurrency → INR'
            ),
            discord.SelectOption(
                label='Support',
                value='support',
                emoji='🎧',
                description='General support & questions'
            ),
            discord.SelectOption(
                label='Dispute / Issue',
                value='dispute',
                emoji='⚠️',
                description='Report a problem or dispute'
            ),
        ]
        super().__init__(
            placeholder='✨ Select a category to open a ticket...',
            min_values=1, max_values=1,
            options=options,
            custom_id='panel:dropdown'
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        modal_cls = MODAL_MAP.get(value)
        if modal_cls:
            await interaction.response.send_modal(modal_cls())


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ── Panel Create Modal ────────────────────────────────────────────────────────

class PanelCreateModal(discord.ui.Modal, title='Create Ticket Panel'):
    panel_title = discord.ui.TextInput(
        label='Panel Title',
        default='🏦 Titan Exchange — Open a Ticket',
        max_length=256
    )
    panel_description = discord.ui.TextInput(
        label='Panel Description',
        style=discord.TextStyle.paragraph,
        default=(
            "```\n"
            "╔══════════════════════════════╗\n"
            "       🏦  TITAN EXCHANGE\n"
            "╚══════════════════════════════╝\n"
            "```\n"
            "📊 **Exchange Rates**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💸 **INR → CRYPTO (I2C)**\n"
            "> ₹101 per $1 — Any Amount\n\n"
            "💰 **CRYPTO → INR (C2I)**\n"
            "> Below $100 → ₹97.5 per $1\n"
            "> Above $100 → ₹98.5 per $1\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ Fixed Rates · No Negotiation\n"
            "📌 Minimum: $1\n"
            "⏳ Be patient · Don't ping staff\n"
            "🚫 No spam tickets"
        ),
        max_length=4000, required=True
    )
    panel_color = discord.ui.TextInput(
        label='Embed Color (hex)',
        default='#F4C430',
        max_length=10, required=False
    )
    panel_footer = discord.ui.TextInput(
        label='Footer Text',
        default='Titan Exchange | Select a category below ⬇️',
        max_length=256, required=False
    )
    thumbnail_url = discord.ui.TextInput(
        label='Server Logo URL (optional)',
        placeholder='https://... (paste your server icon link)',
        required=False, max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        panel_data = {
            'title': self.panel_title.value,
            'description': self.panel_description.value,
            'color': hex_to_int(self.panel_color.value or '#F4C430'),
            'footer': self.panel_footer.value or None,
            'thumbnail': self.thumbnail_url.value or None,
        }
        embed = self._build_embed(panel_data)
        view = PanelView()
        msg = await interaction.channel.send(embed=embed, view=view)
        await interaction.client.db.create_panel(
            interaction.guild.id, interaction.channel.id, msg.id,
            panel_data['title'], panel_data['description'],
            panel_data['color'], panel_data.get('footer'), panel_data.get('thumbnail')
        )
        await interaction.response.send_message('✅ Panel created!', ephemeral=True)

    def _build_embed(self, d: dict) -> discord.Embed:
        embed = discord.Embed(title=d['title'], description=d['description'], color=d['color'])
        if d.get('footer'):
            embed.set_footer(text=d['footer'])
        if d.get('thumbnail'):
            embed.set_thumbnail(url=d['thumbnail'])
        return embed


# ── Cog ───────────────────────────────────────────────────────────────────────

class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self._restore_panels())

    async def _restore_panels(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(PanelView())

    panel_group = app_commands.Group(name='panel', description='Manage ticket panels')

    @panel_group.command(name='create', description='Create a new ticket panel in this channel')
    async def slash_panel_create(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await interaction.response.send_modal(PanelCreateModal())

    @panel_group.command(name='list', description='List all panels')
    async def slash_panel_list(self, interaction: discord.Interaction):
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        if not panels:
            return await interaction.response.send_message('📭 No panels.', ephemeral=True)
        embed = discord.Embed(title='📋 Panels', color=0x5865F2)
        for p in panels:
            ch = interaction.guild.get_channel(p['channel_id'])
            embed.add_field(
                name=f"ID {p['id']} — {p['title']}",
                value=f"Channel: {ch.mention if ch else 'unknown'}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @panel_group.command(name='delete', description='Delete a panel by ID')
    @app_commands.describe(panel_id='Panel ID from /panel list')
    async def slash_panel_delete(self, interaction: discord.Interaction, panel_id: int):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        panel = next((p for p in panels if p['id'] == panel_id), None)
        if not panel:
            return await interaction.response.send_message('❌ Not found.', ephemeral=True)
        try:
            ch = interaction.guild.get_channel(panel['channel_id'])
            if ch:
                msg = await ch.fetch_message(panel['message_id'])
                await msg.delete()
        except Exception:
            pass
        await self.bot.db.delete_panel(panel_id)
        await interaction.response.send_message(f'✅ Panel `{panel_id}` deleted.', ephemeral=True)

    @panel_group.command(name='send', description='Re-send a panel to another channel')
    @app_commands.describe(panel_id='Panel ID', channel='Target channel')
    async def slash_panel_send(self, interaction: discord.Interaction,
                                panel_id: int, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        panels = await self.bot.db.get_all_panels(interaction.guild.id)
        panel = next((p for p in panels if p['id'] == panel_id), None)
        if not panel:
            return await interaction.response.send_message('❌ Not found.', ephemeral=True)
        embed = discord.Embed(title=panel['title'], description=panel['description'], color=panel['color'])
        if panel.get('footer'):
            embed.set_footer(text=panel['footer'])
        if panel.get('thumbnail'):
            embed.set_thumbnail(url=panel['thumbnail'])
        view = PanelView()
        msg = await channel.send(embed=embed, view=view)
        await self.bot.db.update_panel_message(panel_id, msg.id)
        await interaction.response.send_message(f'✅ Sent to {channel.mention}!', ephemeral=True)

    # Prefix
    @commands.command(name='panel')
    @commands.has_permissions(administrator=True)
    async def prefix_panel(self, ctx, action='help', panel_id: int = None):
        if action == 'list':
            panels = await self.bot.db.get_all_panels(ctx.guild.id)
            if not panels:
                return await ctx.send('📭 No panels.')
            embed = discord.Embed(title='📋 Panels', color=0x5865F2)
            for p in panels:
                ch = ctx.guild.get_channel(p['channel_id'])
                embed.add_field(name=f"ID {p['id']} — {p['title']}",
                                value=f"Channel: {ch.mention if ch else 'unknown'}", inline=False)
            await ctx.send(embed=embed)
        elif action == 'delete' and panel_id:
            panels = await self.bot.db.get_all_panels(ctx.guild.id)
            panel = next((p for p in panels if p['id'] == panel_id), None)
            if not panel:
                return await ctx.send('❌ Not found.')
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
            await ctx.send('Use `/panel create` to create a panel, `!panel list`, `!panel delete <id>`')


async def setup(bot):
    await bot.add_cog(Panel(bot))
