import discord
from discord.ext import commands
from discord import app_commands
from utils import get_rate


class Exchange(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_i2c_embed(self, inr: float, usd: float, rate: float, buy_rate: float) -> discord.Embed:
        embed = discord.Embed(
            title='💸 INR → Crypto (I2C) Calculator',
            color=0x2ECC71
        )
        embed.add_field(name='📥 You are Paying', value=f'**₹{inr:,.2f}**', inline=True)
        embed.add_field(name='📤 You will Receive', value=f'**${usd:.4f}**', inline=True)
        embed.add_field(name='📊 Exchange Rate', value=f'₹{buy_rate} per $1', inline=True)
        embed.add_field(name='🌐 Live USD/INR Rate', value=f'₹{rate:.2f}', inline=True)
        embed.set_footer(text='Titan Exchange | Rates may vary slightly at time of deal')
        return embed

    def _build_c2i_embed(self, usd: float, inr: float, rate: float, sell_rate: float) -> discord.Embed:
        embed = discord.Embed(
            title='💰 Crypto → INR (C2I) Calculator',
            color=0xE74C3C
        )
        embed.add_field(name='📥 You are Paying', value=f'**${usd:,.2f}**', inline=True)
        embed.add_field(name='📤 You will Receive', value=f'**₹{inr:,.2f}**', inline=True)
        sell_label = f'₹{sell_rate} per $1 ({"below $100" if usd < 100 else "above $100"})'
        embed.add_field(name='📊 Exchange Rate', value=sell_label, inline=True)
        embed.add_field(name='🌐 Live USD/INR Rate', value=f'₹{rate:.2f}', inline=True)
        embed.set_footer(text='Titan Exchange | Rates may vary slightly at time of deal')
        return embed

    async def _get_rates(self, guild_id: int):
        """Return live rate, i2c buy rate, c2i sell rate (below/above 100)."""
        config = await self.bot.db.get_config(guild_id)
        live = await get_rate(self.bot.db, guild_id)
        # Exchange rates stored in config or defaults
        i2c_rate = config.get('rate_i2c') or 101
        c2i_below = config.get('rate_c2i_below') or 97.5
        c2i_above = config.get('rate_c2i_above') or 98.5
        return live, i2c_rate, c2i_below, c2i_above

    # ── I2C ───────────────────────────────────────────────────────────────────

    @app_commands.command(name='i2c', description='Calculate INR → Crypto exchange')
    @app_commands.describe(amount='Amount in INR you want to exchange')
    async def slash_i2c(self, interaction: discord.Interaction, amount: float):
        live, i2c_rate, _, _ = await self._get_rates(interaction.guild.id)
        usd = round(amount / i2c_rate, 6)
        embed = self._build_i2c_embed(amount, usd, live, i2c_rate)
        await interaction.response.send_message(embed=embed)

    @commands.command(name='i2c')
    async def prefix_i2c(self, ctx, amount: str):
        """Calculate INR to Crypto: ,i2c 1000"""
        try:
            inr = float(amount.replace(',', '').replace('₹', ''))
        except ValueError:
            return await ctx.send('❌ Invalid amount. Example: `,i2c 1000`')
        live, i2c_rate, _, _ = await self._get_rates(ctx.guild.id)
        usd = round(inr / i2c_rate, 6)
        embed = self._build_i2c_embed(inr, usd, live, i2c_rate)
        await ctx.send(embed=embed)

    # ── C2I ───────────────────────────────────────────────────────────────────

    @app_commands.command(name='c2i', description='Calculate Crypto → INR exchange')
    @app_commands.describe(amount='Amount in USD $ you want to exchange')
    async def slash_c2i(self, interaction: discord.Interaction, amount: float):
        live, _, c2i_below, c2i_above = await self._get_rates(interaction.guild.id)
        sell_rate = c2i_above if amount >= 100 else c2i_below
        inr = round(amount * sell_rate, 2)
        embed = self._build_c2i_embed(amount, inr, live, sell_rate)
        await interaction.response.send_message(embed=embed)

    @commands.command(name='c2i')
    async def prefix_c2i(self, ctx, amount: str):
        """Calculate Crypto to INR: ,c2i 10"""
        try:
            usd = float(amount.replace(',', '').replace('$', ''))
        except ValueError:
            return await ctx.send('❌ Invalid amount. Example: `,c2i 10`')
        live, _, c2i_below, c2i_above = await self._get_rates(ctx.guild.id)
        sell_rate = c2i_above if usd >= 100 else c2i_below
        inr = round(usd * sell_rate, 2)
        embed = self._build_c2i_embed(usd, inr, live, sell_rate)
        await ctx.send(embed=embed)

    # ── Rate info ─────────────────────────────────────────────────────────────

    @app_commands.command(name='rate', description='Show current exchange rates')
    async def slash_rate(self, interaction: discord.Interaction):
        live, i2c_rate, c2i_below, c2i_above = await self._get_rates(interaction.guild.id)
        config = await self.bot.db.get_config(interaction.guild.id)
        override = config.get('rate_override')
        embed = discord.Embed(title='📊 Titan Exchange — Current Rates', color=0xF4C430)
        embed.add_field(name='🌐 Live USD/INR', value=f'₹{live:.2f}', inline=True)
        embed.add_field(name='⚙️ Rate Mode', value='Manual Override' if override else 'Live Auto-Fetch', inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.add_field(name='💸 I2C Rate (INR→Crypto)', value=f'₹{i2c_rate} per $1', inline=True)
        embed.add_field(name='💰 C2I Below $100', value=f'₹{c2i_below} per $1', inline=True)
        embed.add_field(name='💰 C2I Above $100', value=f'₹{c2i_above} per $1', inline=True)
        embed.set_footer(text='Use /setrate to override | /setexchangerate to change exchange rates')
        await interaction.response.send_message(embed=embed)

    @commands.command(name='rate')
    async def prefix_rate(self, ctx):
        """Show current rates: ,rate"""
        live, i2c_rate, c2i_below, c2i_above = await self._get_rates(ctx.guild.id)
        config = await self.bot.db.get_config(ctx.guild.id)
        override = config.get('rate_override')
        embed = discord.Embed(title='📊 Titan Exchange — Current Rates', color=0xF4C430)
        embed.add_field(name='🌐 Live USD/INR', value=f'₹{live:.2f}', inline=True)
        embed.add_field(name='⚙️ Mode', value='Manual' if override else 'Auto', inline=True)
        embed.add_field(name='💸 I2C', value=f'₹{i2c_rate}/$', inline=True)
        embed.add_field(name='💰 C2I <$100', value=f'₹{c2i_below}/$', inline=True)
        embed.add_field(name='💰 C2I >$100', value=f'₹{c2i_above}/$', inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Exchange(bot))
