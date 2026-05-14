import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
from utils import (
    has_staff_role, has_admin_role, build_ticket_embed,
    get_category_info, generate_html_transcript, CATEGORY_COLORS
)

MAX_OPEN_TICKETS = 1  # Max open tickets per user per guild


class TicketCloseView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='🔒 Close Ticket', style=discord.ButtonStyle.danger, custom_id='ticket:close')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cog = self.bot.get_cog('Tickets')
        if cog:
            await cog._close_ticket(interaction.channel, interaction.user)

    @discord.ui.button(label='👤 Claim', style=discord.ButtonStyle.primary, custom_id='ticket:claim')
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await interaction.client.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.member, config):
            return await interaction.response.send_message('❌ Only staff can claim tickets.', ephemeral=True)
        ticket = await interaction.client.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message('❌ Ticket not found.', ephemeral=True)
        if ticket['claimed_by']:
            claimer = interaction.guild.get_member(ticket['claimed_by'])
            name = claimer.display_name if claimer else 'Someone'
            return await interaction.response.send_message(f'❌ Already claimed by **{name}**.', ephemeral=True)

        await interaction.client.db.claim_ticket(interaction.channel.id, interaction.user.id)
        user = interaction.guild.get_member(ticket['user_id'])
        embed = build_ticket_embed(ticket['category'], user, ticket['ticket_number'], interaction.user)
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f'✅ {interaction.user.mention} claimed this ticket.', ephemeral=False)

    @discord.ui.button(label='➕ Add User', style=discord.ButtonStyle.secondary, custom_id='ticket:adduser')
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await interaction.client.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.member, config):
            return await interaction.response.send_message('❌ Only staff can add users.', ephemeral=True)

        modal = AddUserModal()
        await interaction.response.send_modal(modal)


class AddUserModal(discord.ui.Modal, title='Add User to Ticket'):
    user_id = discord.ui.TextInput(
        label='User ID or Mention',
        placeholder='Enter user ID e.g. 123456789012345678',
        required=True,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_id.value.strip().replace('<@', '').replace('>', '').replace('!', '')
        try:
            uid = int(raw)
            member = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message('❌ User not found.', ephemeral=True)

        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f'✅ Added {member.mention} to the ticket.')


class CategorySelectView(discord.ui.View):
    """View shown on the ticket panel — one button per category."""

    def __init__(self, bot, categories: list):
        super().__init__(timeout=None)
        self.bot = bot
        for cat in categories:
            btn = discord.ui.Button(
                label=cat['label'],
                emoji=cat.get('emoji', '🎫'),
                style=discord.ButtonStyle.secondary,
                custom_id=f"panel:open:{cat['value']}"
            )
            btn.callback = self._make_callback(cat['value'])
            self.add_item(btn)

    def _make_callback(self, category_value: str):
        async def callback(interaction: discord.Interaction):
            cog = self.bot.get_cog('Tickets')
            if cog:
                await cog._open_ticket(interaction, category_value)
        return callback


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Re-register persistent views on startup
        bot.loop.create_task(self._register_views())

    async def _register_views(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(TicketCloseView(self.bot))

    async def _open_ticket(self, interaction: discord.Interaction, category_value: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        config = await self.bot.db.get_config(guild.id)

        # Check for existing open ticket
        open_tickets = await self.bot.db.get_open_tickets(guild.id, user.id)
        if len(open_tickets) >= MAX_OPEN_TICKETS:
            ch = guild.get_channel(open_tickets[0]['channel_id'])
            mention = ch.mention if ch else 'an existing channel'
            return await interaction.followup.send(
                f'❌ You already have an open ticket: {mention}', ephemeral=True
            )

        # Get/create ticket category
        category = None
        if config['ticket_category']:
            category = guild.get_channel(config['ticket_category'])
        if not category:
            category = await guild.create_category('📩 Tickets')
            await self.bot.db.set_config(guild.id, ticket_category=category.id)

        # Ticket number
        ticket_num = await self.bot.db.increment_ticket_counter(guild.id)
        info = get_category_info(category_value)
        channel_name = f"ticket-{ticket_num:04d}-{user.name[:10].lower()}"

        # Build permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for role_list_key in ['admin_roles', 'mod_roles', 'staff_roles', 'dealer_roles']:
            for role_id in config.get(role_list_key, []):
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True, attach_files=True
                    )

        # Create channel
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket #{ticket_num:04d} | {info['label']} | {user} ({user.id})"
        )

        # Save to DB
        ticket_id = await self.bot.db.create_ticket(
            guild.id, channel.id, user.id, category_value, ticket_num
        )

        # Send ticket embed
        embed = build_ticket_embed(category_value, user, ticket_num)
        view = TicketCloseView(self.bot)
        msg = await channel.send(
            content=f"{user.mention} Welcome! Staff will be with you shortly.",
            embed=embed,
            view=view
        )
        await msg.pin()

        await interaction.followup.send(
            f'✅ Your ticket has been opened: {channel.mention}', ephemeral=True
        )

        # Log to log channel
        if config['log_channel']:
            log_ch = guild.get_channel(config['log_channel'])
            if log_ch:
                log_embed = discord.Embed(
                    title='📂 Ticket Opened',
                    color=CATEGORY_COLORS.get(category_value, 0x2ECC71),
                    description=(
                        f"**User:** {user.mention} (`{user.id}`)\n"
                        f"**Category:** {info['emoji']} {info['label']}\n"
                        f"**Channel:** {channel.mention}\n"
                        f"**Ticket #:** {ticket_num:04d}"
                    )
                )
                await log_ch.send(embed=log_embed)

    async def _close_ticket(self, channel: discord.TextChannel, closer: discord.Member):
        ticket = await self.bot.db.get_ticket_by_channel(channel.id)
        if not ticket:
            return await channel.send('❌ This channel is not a ticket.')

        guild = channel.guild
        config = await self.bot.db.get_config(guild.id)

        # Check permission: opener or staff
        is_opener = ticket['user_id'] == closer.id
        is_staff = await has_staff_role(closer, config)
        if not is_opener and not is_staff:
            return await channel.send('❌ Only the ticket opener or staff can close this ticket.')

        # Notify
        await channel.send('🔒 Closing ticket and saving transcript...')
        await asyncio.sleep(1)

        # Generate transcript
        messages = await self.bot.db.get_transcript(ticket['id'])
        html = await generate_html_transcript(ticket, messages, guild)

        # Close in DB
        await self.bot.db.close_ticket(channel.id)

        # Send transcript
        if config['transcript_channel']:
            tr_ch = guild.get_channel(config['transcript_channel'])
            if tr_ch:
                info = get_category_info(ticket['category'])
                opener = guild.get_member(ticket['user_id'])
                embed = discord.Embed(
                    title=f"📄 Transcript — Ticket #{ticket['ticket_number']:04d}",
                    color=0x5865F2,
                    description=(
                        f"**Category:** {info['emoji']} {info['label']}\n"
                        f"**Opened by:** {opener.mention if opener else ticket['user_id']}\n"
                        f"**Closed by:** {closer.mention}\n"
                        f"**Messages logged:** {len(messages)}"
                    )
                )
                file = discord.File(
                    io.BytesIO(html.encode()),
                    filename=f"ticket-{ticket['ticket_number']:04d}.html"
                )
                await tr_ch.send(embed=embed, file=file)

        # Log closure
        if config['log_channel']:
            log_ch = guild.get_channel(config['log_channel'])
            if log_ch:
                log_embed = discord.Embed(
                    title='🔒 Ticket Closed',
                    color=0xE74C3C,
                    description=(
                        f"**Ticket #:** {ticket['ticket_number']:04d}\n"
                        f"**Closed by:** {closer.mention}\n"
                        f"**Channel:** #{channel.name}"
                    )
                )
                await log_ch.send(embed=log_embed)

        await asyncio.sleep(2)
        await channel.delete(reason=f"Ticket closed by {closer}")

    # ── Message logging for transcripts ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if ticket and ticket['status'] == 'open':
            content = message.content or ''
            if message.attachments:
                content += ' ' + ' '.join(a.url for a in message.attachments)
            await self.bot.db.log_message(
                ticket['id'], message.author.id,
                str(message.author), content[:2000]
            )

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name='close', description='Close the current ticket')
    async def slash_close(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._close_ticket(interaction.channel, interaction.user)

    @app_commands.command(name='add', description='Add a user to this ticket')
    @app_commands.describe(member='The member to add')
    async def slash_add(self, interaction: discord.Interaction, member: discord.Member):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f'✅ Added {member.mention} to the ticket.')

    @app_commands.command(name='remove', description='Remove a user from this ticket')
    @app_commands.describe(member='The member to remove')
    async def slash_remove(self, interaction: discord.Interaction, member: discord.Member):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f'✅ Removed {member.mention} from the ticket.')

    # ── Prefix commands ───────────────────────────────────────────────────────

    @commands.command(name='close')
    async def prefix_close(self, ctx: commands.Context):
        """Close the current ticket."""
        await self._close_ticket(ctx.channel, ctx.author)

    @commands.command(name='add')
    async def prefix_add(self, ctx: commands.Context, member: discord.Member):
        """Add a user to the current ticket."""
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_staff_role(ctx.author, config):
            return await ctx.send('❌ Staff only.')
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f'✅ Added {member.mention}.')

    @commands.command(name='remove')
    async def prefix_remove(self, ctx: commands.Context, member: discord.Member):
        """Remove a user from the current ticket."""
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_staff_role(ctx.author, config):
            return await ctx.send('❌ Staff only.')
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(f'✅ Removed {member.mention}.')


async def setup(bot):
    await bot.add_cog(Tickets(bot))
