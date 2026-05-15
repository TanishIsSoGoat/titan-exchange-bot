import discord
from discord.ext import commands
from discord import app_commands
import io
from utils import has_staff_role, get_category_info, generate_html_transcript, get_rate


class DoneModal(discord.ui.Modal, title='✅ Mark Deal as Done'):
    pair = discord.ui.TextInput(
        label='Currency Pair',
        placeholder='e.g. USDT to INR / INR to LTC / BTC to INR',
        required=True, max_length=50
    )
    amount_usd = discord.ui.TextInput(
        label='Amount in USD ($) — fill ONE of USD or INR',
        placeholder='e.g. 15.5  (leave blank if entering INR below)',
        required=False, max_length=20
    )
    amount_inr = discord.ui.TextInput(
        label='Amount in INR (₹) — fill ONE of USD or INR',
        placeholder='e.g. 1567.25  (leave blank if entering USD above)',
        required=False, max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        usd_raw = self.amount_usd.value.strip().replace('$', '').replace(',', '')
        inr_raw = self.amount_inr.value.strip().replace('₹', '').replace(',', '')

        if not usd_raw and not inr_raw:
            return await interaction.response.send_message('❌ Please enter at least one amount (USD or INR).', ephemeral=True)

        rate = await get_rate(interaction.client.db, interaction.guild.id)

        try:
            if usd_raw and inr_raw:
                usd = float(usd_raw)
                inr = float(inr_raw)
            elif usd_raw:
                usd = float(usd_raw)
                config = await interaction.client.db.get_config(interaction.guild.id)
                c2i_below = config.get('rate_c2i_below') or 97.5
                c2i_above = config.get('rate_c2i_above') or 98.5
                sell_rate = c2i_above if usd >= 100 else c2i_below
                inr = round(usd * sell_rate, 2)
            else:
                inr = float(inr_raw)
                config = await interaction.client.db.get_config(interaction.guild.id)
                i2c_rate = config.get('rate_i2c') or 101
                usd = round(inr / i2c_rate, 4)
        except ValueError:
            return await interaction.response.send_message('❌ Invalid amount. Use numbers only e.g. 15.5', ephemeral=True)

        cog = interaction.client.get_cog('Done')
        if cog:
            await cog._process_done(interaction, self.pair.value, usd, inr)


class Done(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _process_done(self, interaction: discord.Interaction, pair: str, amount_usd: float, amount_inr: float):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        config = await self.bot.db.get_config(guild.id)

        ticket = await self.bot.db.get_ticket_by_channel(channel.id)
        if not ticket:
            return await interaction.followup.send('❌ This is not a ticket channel.', ephemeral=True)

        if ticket['status'] in ('closed', 'done'):
            return await interaction.followup.send('❌ This ticket is already closed/done.', ephemeral=True)

        exchanger = interaction.user
        client = guild.get_member(ticket['user_id'])

        # Must be the claimer or an admin
        is_claimer = ticket['claimed_by'] == exchanger.id
        from utils import has_admin_or_mod
        is_admin = await has_admin_or_mod(exchanger, config)
        if not is_claimer and not is_admin:
            return await interaction.followup.send('❌ Only the exchanger who claimed this ticket can use /done.', ephemeral=True)

        rate = await get_rate(self.bot.db, guild.id)

        # Record deal in DB
        await self.bot.db.record_deal(
            guild.id, ticket['id'], exchanger.id,
            ticket['user_id'], pair, amount_usd, amount_inr, rate
        )

        # Free exchanger limit
        deal_usd = ticket.get('deal_amount_usd') or amount_usd
        await self.bot.db.free_used_limit(guild.id, exchanger.id, deal_usd)

        # Mark ticket done
        await self.bot.db.mark_ticket_done(channel.id)

        # Get deal count for exchanger
        deal_count = await self.bot.db.get_deal_count(guild.id, exchanger.id)

        # Build vouch text
        vouch_text = f"+rep {exchanger.mention} legit exchange ✅ {pair} | Deal #{deal_count}"

        # ── Send the 4 vouch messages ──────────────────────────────────────────
        vouch_channel_id = config.get('vouch_channel')
        vouch_mention = f'<#{vouch_channel_id}>' if vouch_channel_id else '**#vouch channel**'

        # Msg 1 — Thank you
        embed1 = discord.Embed(
            description=(
                "## 🙏 Thank you for choosing Titan Exchange!\n"
                "We hope you enjoyed our service.\n"
                "Your deal has been completed successfully. ✅"
            ),
            color=0x2ECC71
        )
        embed1.set_footer(text='Titan Exchange')
        await channel.send(embed=embed1)

        # Msg 2 — Vouch template in copyable box
        embed2 = discord.Embed(
            title='📋 Your Vouch',
            description=(
                f"```\n{exchanger.name} +rep legit exchange ✅ {pair}\n```\n"
                f"> Copy the text above and paste it in the vouch channel!"
            ),
            color=0xF4C430
        )
        embed2.add_field(name='👷 Exchanger', value=exchanger.mention, inline=True)
        embed2.add_field(name='💱 Pair', value=pair, inline=True)
        embed2.add_field(name='💲 Amount', value=f'${amount_usd} / ₹{amount_inr:,.2f}', inline=True)
        await channel.send(embed=embed2)

        # Msg 3 — Paste in vouch channel
        embed3 = discord.Embed(
            description=f"📌 Kindly copy the vouch above and paste it in {vouch_mention}",
            color=0x5865F2
        )
        await channel.send(embed=embed3)

        # Msg 4 — Warning
        embed4 = discord.Embed(
            description="⚠️ **Skipping the vouch will lead to unwanted consequences.**\nYour cooperation is appreciated.",
            color=0xFF6B35
        )
        await channel.send(embed=embed4)

        # ── Generate & send transcript ─────────────────────────────────────────
        messages = await self.bot.db.get_transcript(ticket['id'])
        html = await generate_html_transcript(ticket, messages, guild)
        html_file_bytes = html.encode()

        info = get_category_info(ticket['category'])
        transcript_embed = discord.Embed(
            title=f"📄 Deal Transcript — #{ticket['ticket_number']:04d}",
            color=0x2ECC71,
            description=(
                f"**Pair:** {pair}\n"
                f"**Amount:** ${amount_usd} / ₹{amount_inr:,.2f}\n"
                f"**Rate used:** ₹{rate:.2f}/$\n"
                f"**Exchanger:** {exchanger.mention}\n"
                f"**Client:** {client.mention if client else ticket['user_id']}\n"
                f"**Deal #{deal_count}**"
            )
        )

        # Send to transcript channel
        if config['transcript_channel']:
            tr_ch = guild.get_channel(config['transcript_channel'])
            if tr_ch:
                f1 = discord.File(io.BytesIO(html_file_bytes), filename=f"ticket-{ticket['ticket_number']:04d}.html")
                await tr_ch.send(embed=transcript_embed, file=f1)

        # DM client
        if client:
            try:
                dm_embed = discord.Embed(
                    title='✅ Your Titan Exchange Deal is Complete!',
                    color=0x2ECC71,
                    description=(
                        f"**Server:** {guild.name}\n"
                        f"**Pair:** {pair}\n"
                        f"**Amount:** ${amount_usd} / ₹{amount_inr:,.2f}\n"
                        f"**Exchanger:** {exchanger.display_name}\n\n"
                        f"Thank you for using Titan Exchange! 🙏\n"
                        f"Please remember to leave a vouch in the server."
                    )
                )
                f2 = discord.File(io.BytesIO(html_file_bytes), filename=f"ticket-{ticket['ticket_number']:04d}.html")
                await client.send(embed=dm_embed, file=f2)
            except discord.Forbidden:
                pass

        # DM exchanger
        try:
            exc_embed = discord.Embed(
                title='✅ Deal Completed — Titan Exchange',
                color=0x2ECC71,
                description=(
                    f"**Pair:** {pair}\n"
                    f"**Amount:** ${amount_usd} / ₹{amount_inr:,.2f}\n"
                    f"**Client:** {client.display_name if client else 'Unknown'}\n"
                    f"**Total Deals Done:** {deal_count}\n\n"
                    f"Great work! Your limit has been freed up. 💪"
                )
            )
            f3 = discord.File(io.BytesIO(html_file_bytes), filename=f"ticket-{ticket['ticket_number']:04d}.html")
            await exchanger.send(embed=exc_embed, file=f3)
        except discord.Forbidden:
            pass

        await interaction.followup.send('✅ Deal marked as done! Vouch messages sent.', ephemeral=True)

    @app_commands.command(name='done', description='Mark this deal as complete and send vouch messages')
    async def slash_done(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message('❌ Not a ticket channel.', ephemeral=True)
        await interaction.response.send_modal(DoneModal())

    @commands.command(name='done')
    async def prefix_done(self, ctx):
        """Mark deal as done: ,done"""
        config = await self.bot.db.get_config(ctx.guild.id)
        if not await has_staff_role(ctx.author, config):
            return await ctx.send('❌ Staff only.')
        ticket = await self.bot.db.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return await ctx.send('❌ Not a ticket channel.')
        await ctx.send('Please use `/done` to open the deal completion form.')


async def setup(bot):
    await bot.add_cog(Done(bot))