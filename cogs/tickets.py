import discord
from discord.ext import commands
from discord import app_commands
import asyncio, io
from utils import (
    has_staff_role, has_admin_or_mod, build_ticket_embed,
    get_category_info, generate_html_transcript, get_rate, is_exchanger_role
)

MAX_OPEN = 1  # max open tickets per user


class ClaimAmountModal(discord.ui.Modal, title='Claim Ticket — Enter Deal Amount'):
    amount = discord.ui.TextInput(
        label='Deal Amount',
        placeholder='Enter amount in $ e.g. 15 (for $15 deal)',
        required=True, max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            usd = float(self.amount.value.strip().replace('$', ''))
        except ValueError:
            return await interaction.response.send_message('❌ Invalid amount.', ephemeral=True)

        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._do_claim(interaction, usd)


class TicketControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='🔒 Close', style=discord.ButtonStyle.danger, custom_id='ticket:close')
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await interaction.client.db.get_config(interaction.guild.id)
        if not await has_admin_or_mod(interaction.user, config):
            return await interaction.response.send_message('❌ Only Admin/Mod can close tickets.', ephemeral=True)
        await interaction.response.defer()
        cog = interaction.client.get_cog('Tickets')
        if cog:
            await cog._close_ticket(interaction.channel, interaction.user)

    @discord.ui.button(label='👤 Claim', style=discord.ButtonStyle.primary, custom_id='ticket:claim')
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await interaction.client.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        ticket = await interaction.client.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message('❌ Not a ticket channel.', ephemeral=True)
        if ticket['claimed_by']:
            claimer = interaction.guild.get_member(ticket['claimed_by'])
            return await interaction.response.send_message(
                f'❌ Already claimed by {claimer.mention if claimer else "someone"}.', ephemeral=True)
        # Only check limit for exchange tickets
        if ticket['category'] in ('i2c', 'c2i'):
            await interaction.response.send_modal(ClaimAmountModal())
        else:
            # Support/dispute — no limit check needed
            await interaction.client.db.claim_ticket(interaction.channel.id, interaction.user.id)
            user = interaction.guild.get_member(ticket['user_id'])
            embed = build_ticket_embed(ticket['category'], user, ticket['ticket_number'], interaction.user)
            try:
                await interaction.message.edit(embed=embed)
            except Exception:
                pass
            await interaction.response.send_message(f'✅ {interaction.user.mention} claimed this ticket.')


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self._register_views())

    async def _register_views(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(TicketControlView(self.bot))

    async def _open_ticket(self, interaction: discord.Interaction, category: str, answers: dict = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        config = await self.bot.db.get_config(guild.id)

        open_tickets = await self.bot.db.get_open_tickets(guild.id, user.id)
        if len(open_tickets) >= MAX_OPEN:
            ch = guild.get_channel(open_tickets[0]['channel_id'])
            return await interaction.followup.send(
                f'❌ You already have an open ticket: {ch.mention if ch else "existing channel"}', ephemeral=True)

        # Get/create category
        cat_channel = None
        if config['ticket_category']:
            cat_channel = guild.get_channel(config['ticket_category'])
        if not cat_channel:
            cat_channel = await guild.create_category('📩 Tickets')
            await self.bot.db.set_config(guild.id, ticket_category=cat_channel.id)

        ticket_num = await self.bot.db.increment_ticket_counter(guild.id)
        info = get_category_info(category)
        ch_name = f"{info['short'].lower()}-{ticket_num:04d}-{user.name[:8].lower()}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for key in ['admin_roles', 'mod_roles', 'staff_roles', 'dealer_roles']:
            for rid in config.get(key, []):
                role = guild.get_role(rid)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True, attach_files=True)

        channel = await guild.create_text_channel(
            ch_name, category=cat_channel, overwrites=overwrites,
            topic=f"Ticket #{ticket_num:04d} | {info['label']} | {user} ({user.id})"
        )

        ticket_id = await self.bot.db.create_ticket(guild.id, channel.id, user.id, category, ticket_num)

        embed = build_ticket_embed(category, user, ticket_num, modal_answers=answers)
        view = TicketControlView(self.bot)
        msg = await channel.send(content=f"{user.mention}", embed=embed, view=view)
        await msg.pin()

        await interaction.followup.send(f'✅ Ticket opened: {channel.mention}', ephemeral=True)

        if config['log_channel']:
            lch = guild.get_channel(config['log_channel'])
            if lch:
                lembed = discord.Embed(title='📂 Ticket Opened', color=0x2ECC71,
                    description=f"**User:** {user.mention}\n**Category:** {info['emoji']} {info['label']}\n**Channel:** {channel.mention}")
                await lch.send(embed=lembed)

    async def _do_claim(self, interaction: discord.Interaction, amount_usd: float):
        """Called after exchanger enters amount in modal."""
        guild = interaction.guild
        config = await self.bot.db.get_config(guild.id)
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message('❌ Not a ticket.', ephemeral=True)

        rate = await get_rate(self.bot.db, guild.id)
        amount_inr = round(amount_usd * rate, 2)

        # Check exchanger limit
        lim = await self.bot.db.get_exchanger_limit(guild.id, interaction.user.id)
        limit_usd = lim['limit_usd']
        used_usd = lim['used_usd']

        if limit_usd > 0:
            if used_usd + amount_usd > limit_usd:
                avail = limit_usd - used_usd
                return await interaction.response.send_message(
                    f'❌ **Limit exceeded!**\n'
                    f'Your limit: **${limit_usd}**\n'
                    f'Currently in use: **${used_usd}**\n'
                    f'Available: **${avail:.2f}**\n'
                    f'This deal: **${amount_usd}**\n\n'
                    f'You cannot claim deals that exceed your available limit.',
                    ephemeral=True
                )

        # Add to used limit
        await self.bot.db.add_used_limit(guild.id, interaction.user.id, amount_usd)

        # Claim ticket
        await self.bot.db.claim_ticket(interaction.channel.id, interaction.user.id, amount_usd, amount_inr)

        user = guild.get_member(ticket['user_id'])
        embed = build_ticket_embed(ticket['category'], user, ticket['ticket_number'], interaction.user)
        try:
            # Try to find and edit the pinned message
            pins = await interaction.channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed)
                    break
        except Exception:
            pass

        await interaction.response.send_message(
            f'✅ {interaction.user.mention} claimed this ticket!\n'
            f'💲 Deal Amount: **${amount_usd}** (~₹{amount_inr:,.2f})\n'
            f'📊 Limit used: **${used_usd + amount_usd:.2f}** / **${limit_usd}**'
        )

    async def _close_ticket(self, channel: discord.TextChannel, closer: discord.Member):
        ticket = await self.bot.db.get_ticket_by_channel(channel.id)
        if not ticket:
            return await channel.send('❌ Not a ticket channel.')

        guild = channel.guild
        config = await self.bot.db.get_config(guild.id)

        if not await has_admin_or_mod(closer, config):
            return await channel.send('❌ Only Admin/Mod can close tickets.')

        await channel.send('🔒 Saving transcript and closing...')
        await asyncio.sleep(1)

        messages = await self.bot.db.get_transcript(ticket['id'])
        html = await generate_html_transcript(ticket, messages, guild)
        await self.bot.db.close_ticket(channel.id)

        file = discord.File(io.BytesIO(html.encode()), filename=f"ticket-{ticket['ticket_number']:04d}.html")

        if config['transcript_channel']:
            tr_ch = guild.get_channel(config['transcript_channel'])
            if tr_ch:
                opener = guild.get_member(ticket['user_id'])
                info = get_category_info(ticket['category'])
                embed = discord.Embed(title=f"📄 Transcript — #{ticket['ticket_number']:04d}", color=0x5865F2,
                    description=f"**Category:** {info['emoji']} {info['label']}\n**Opened by:** {opener.mention if opener else ticket['user_id']}\n**Closed by:** {closer.mention}")
                await tr_ch.send(embed=embed, file=file)

        if config['log_channel']:
            lch = guild.get_channel(config['log_channel'])
            if lch:
                embed = discord.Embed(title='🔒 Ticket Closed', color=0xE74C3C,
                    description=f"**Ticket #:** {ticket['ticket_number']:04d}\n**Closed by:** {closer.mention}")
                await lch.send(embed=embed)

        await asyncio.sleep(2)
        await channel.delete(reason=f'Closed by {closer}')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if ticket and ticket['status'] == 'open':
            content = message.content or ''
            if message.attachments:
                content += ' ' + ' '.join(a.url for a in message.attachments)
            await self.bot.db.log_message(ticket['id'], message.author.id, str(message.author), content[:2000])

    @app_commands.command(name='close', description='Close the current ticket (Admin/Mod only)')
    async def slash_close(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_or_mod(interaction.user, config):
            return await interaction.response.send_message('❌ Admin/Mod only.', ephemeral=True)
        await interaction.response.defer()
        await self._close_ticket(interaction.channel, interaction.user)

    @app_commands.command(name='add', description='Add a user to this ticket')
    @app_commands.describe(member='Member to add')
    async def slash_add(self, interaction: discord.Interaction, member: discord.Member):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f'✅ Added {member.mention}.')

    @app_commands.command(name='remove', description='Remove a user from this ticket')
    @app_commands.describe(member='Member to remove')
    async def slash_remove(self, interaction: discord.Interaction, member: discord.Member):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f'✅ Removed {member.mention}.')

    @commands.command(name='close')
    async def prefix_close(self, ctx):
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_admin_or_mod(ctx.author, config):
            return await ctx.send('❌ Admin/Mod only.')
        await self._close_ticket(ctx.channel, ctx.author)

    @commands.command(name='add')
    async def prefix_add(self, ctx, member: discord.Member):
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_staff_role(ctx.author, config):
            return await ctx.send('❌ Staff only.')
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f'✅ Added {member.mention}.')

    @commands.command(name='remove')
    async def prefix_remove(self, ctx, member: discord.Member):
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_staff_role(ctx.author, config):
            return await ctx.send('❌ Staff only.')
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(f'✅ Removed {member.mention}.')


async def setup(bot):
    await bot.add_cog(Tickets(bot))