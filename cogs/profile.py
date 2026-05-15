import discord
from discord.ext import commands
from discord import app_commands
from utils import get_rate, is_exchanger_role


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _build_profile(self, guild: discord.Guild, member: discord.Member) -> discord.Embed:
        config = await self.bot.db.get_config(guild.id)
        stats = await self.bot.db.get_user_stats(guild.id, member.id)
        lim = await self.bot.db.get_exchanger_limit(guild.id, member.id)
        rate = await get_rate(self.bot.db, guild.id)

        exchanger_stats = next((s for s in stats if s['role'] == 'exchanger'), None)
        client_stats = next((s for s in stats if s['role'] == 'client'), None)

        is_exc = is_exchanger_role(member, config) or (exchanger_stats and exchanger_stats['total_deals'] > 0)
        is_client = client_stats and client_stats['total_deals'] > 0

        # Determine status label
        if is_exc and is_client:
            status = '👷 Exchanger + 👤 Client'
        elif is_exc:
            status = '👷 Exchanger'
        elif is_client:
            status = '👤 Client'
        else:
            status = '🆕 New Member'

        embed = discord.Embed(
            title=f'👤 Profile — {member.display_name}',
            color=0x5865F2
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='🏷️ Status', value=status, inline=False)

        # Exchanger section
        if is_exc:
            limit_usd = lim['limit_usd']
            used_usd = lim['used_usd']
            available = max(0, limit_usd - used_usd)
            limit_inr = round(limit_usd * rate, 2)
            used_inr = round(used_usd * rate, 2)
            avail_inr = round(available * rate, 2)

            embed.add_field(name='\u200b', value='**━━━ 👷 Exchanger Stats ━━━**', inline=False)
            if exchanger_stats:
                avg = (exchanger_stats['total_usd'] / exchanger_stats['total_deals']) if exchanger_stats['total_deals'] > 0 else 0
                embed.add_field(name='✅ Deals Done', value=f"`{exchanger_stats['total_deals']}`", inline=True)
                embed.add_field(name='💲 Total Volume ($)', value=f"`${exchanger_stats['total_usd']:.2f}`", inline=True)
                embed.add_field(name='💰 Total Volume (₹)', value=f"`₹{exchanger_stats['total_inr']:,.2f}`", inline=True)
                embed.add_field(name='📊 Avg Deal Size', value=f"`${avg:.2f}`", inline=True)
            else:
                embed.add_field(name='✅ Deals Done', value='`0`', inline=True)

            embed.add_field(name='\u200b', value='**━━━ 📊 Limit ━━━**', inline=False)
            if limit_usd > 0:
                bar_filled = int((used_usd / limit_usd) * 10) if limit_usd > 0 else 0
                bar = '🟩' * bar_filled + '⬜' * (10 - bar_filled)
                embed.add_field(name='🔢 Limit', value=f'`${limit_usd}` (~₹{limit_inr:,.2f})', inline=True)
                embed.add_field(name='🔴 In Use', value=f'`${used_usd}` (~₹{used_inr:,.2f})', inline=True)
                embed.add_field(name='🟢 Available', value=f'`${available:.2f}` (~₹{avail_inr:,.2f})', inline=True)
                embed.add_field(name='📈 Usage', value=bar, inline=False)
            else:
                embed.add_field(name='⚠️ Limit', value='`Not set` — Contact an admin', inline=False)

        # Client section
        if is_client:
            embed.add_field(name='\u200b', value='**━━━ 👤 Client Stats ━━━**', inline=False)
            avg = (client_stats['total_usd'] / client_stats['total_deals']) if client_stats['total_deals'] > 0 else 0
            embed.add_field(name='✅ Deals Done', value=f"`{client_stats['total_deals']}`", inline=True)
            embed.add_field(name='💲 Total ($)', value=f"`${client_stats['total_usd']:.2f}`", inline=True)
            embed.add_field(name='💰 Total (₹)', value=f"`₹{client_stats['total_inr']:,.2f}`", inline=True)
            embed.add_field(name='📊 Avg Deal', value=f"`${avg:.2f}`", inline=True)

        if not is_exc and not is_client:
            embed.add_field(name='ℹ️ Info', value='No deals recorded yet.', inline=False)

        embed.set_footer(text=f'Titan Exchange | ID: {member.id}')
        return embed

    @app_commands.command(name='profile', description='View a user\'s exchange profile')
    @app_commands.describe(member='The member to view (leave blank for yourself)')
    async def slash_profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer()
        embed = await self._build_profile(interaction.guild, target)
        await interaction.followup.send(embed=embed)

    @commands.command(name='profile')
    async def prefix_profile(self, ctx, member: discord.Member = None):
        """View profile: ,profile @user"""
        target = member or ctx.author
        embed = await self._build_profile(ctx.guild, target)
        await ctx.send(embed=embed)

    @app_commands.command(name='mylimit', description='Check your current exchanger limit')
    async def slash_mylimit(self, interaction: discord.Interaction):
        lim = await self.bot.db.get_exchanger_limit(interaction.guild.id, interaction.user.id)
        rate = await get_rate(self.bot.db, interaction.guild.id)
        limit_usd = lim['limit_usd']
        used_usd = lim['used_usd']
        available = max(0, limit_usd - used_usd)

        if limit_usd == 0:
            return await interaction.response.send_message(
                '⚠️ You don\'t have a limit set. Contact an admin to set your exchanger limit.', ephemeral=True)

        embed = discord.Embed(title='📊 Your Exchanger Limit', color=0x5865F2)
        embed.add_field(name='🔢 Total Limit', value=f'`${limit_usd}` (~₹{limit_usd * rate:,.2f})', inline=True)
        embed.add_field(name='🔴 In Use', value=f'`${used_usd}` (~₹{used_usd * rate:,.2f})', inline=True)
        embed.add_field(name='🟢 Available', value=f'`${available:.2f}` (~₹{available * rate:,.2f})', inline=True)
        bar_filled = int((used_usd / limit_usd) * 10) if limit_usd > 0 else 0
        embed.add_field(name='📈 Usage', value='🟩' * bar_filled + '⬜' * (10 - bar_filled), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name='mylimit')
    async def prefix_mylimit(self, ctx):
        """Check your limit: ,mylimit"""
        lim = await self.bot.db.get_exchanger_limit(ctx.guild.id, ctx.author.id)
        rate = await get_rate(self.bot.db, ctx.guild.id)
        limit_usd = lim['limit_usd']
        used_usd = lim['used_usd']
        available = max(0, limit_usd - used_usd)
        if limit_usd == 0:
            return await ctx.send('⚠️ No limit set. Contact an admin.')
        embed = discord.Embed(title='📊 Your Exchanger Limit', color=0x5865F2)
        embed.add_field(name='Total', value=f'`${limit_usd}`', inline=True)
        embed.add_field(name='In Use', value=f'`${used_usd}`', inline=True)
        embed.add_field(name='Available', value=f'`${available:.2f}`', inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
