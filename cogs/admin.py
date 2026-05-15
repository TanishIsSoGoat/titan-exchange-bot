import discord
from discord.ext import commands
from discord import app_commands
from utils import has_staff_role, has_admin_role, has_admin_or_mod


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help', description='Show all bot commands')
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title='🤖 Titan Exchange Bot — Commands', color=0x5865F2)
        embed.add_field(name='🎫 Tickets', value=(
            '`/close` `,close` — Close ticket *(Admin/Mod)*\n'
            '`/add @user` `,add @user` — Add user\n'
            '`/remove @user` `,remove @user` — Remove user\n'
            '`/done` `,done` — Mark deal done + send vouch\n'
        ), inline=False)
        embed.add_field(name='💱 Exchange Calculator', value=(
            '`/i2c <INR>` `,i2c <INR>` — INR → Crypto calc\n'
            '`/c2i <USD>` `,c2i <USD>` — Crypto → INR calc\n'
            '`/rate` `,rate` — Show current rates\n'
        ), inline=False)
        embed.add_field(name='👤 Profile', value=(
            '`/profile [@user]` `,profile [@user]` — View stats\n'
            '`/mylimit` `,mylimit` — Check your exchanger limit\n'
        ), inline=False)
        embed.add_field(name='📋 Panels *(Admin)*', value=(
            '`/panel create` — Create ticket panel\n'
            '`/panel list` — List panels\n'
            '`/panel delete <id>` — Delete panel\n'
            '`/panel send <id> #ch` — Send panel to channel\n'
        ), inline=False)
        embed.add_field(name='⚙️ Setup *(Admin)*', value=(
            '`/setup view` — View config\n'
            '`/setup transcript #ch` — Set transcript channel\n'
            '`/setup logs #ch` — Set log channel\n'
            '`/setup vouchchannel #ch` — Set vouch channel\n'
            '`/setup category` — Set ticket category\n'
            '`/setup addrole <group> @role` — Add role\n'
            '`/setup removerole <group> @role` — Remove role\n'
            '`/setup prefix <p>` — Change prefix\n'
            '`/setrate <rate>` — Override USD/INR rate (0=auto)\n'
            '`/setexchangerate` — Set I2C/C2I rates\n'
            '`/setlimit @user <$>` — Set exchanger limit\n'
        ), inline=False)
        embed.add_field(name='🔧 Admin', value=(
            '`/admin tickets` — Open ticket stats\n'
            '`/admin resetcounter` — Reset ticket counter\n'
            '`/admin forceclose #ch` — Force close ticket\n'
        ), inline=False)
        embed.set_footer(text='Titan Exchange | Both / slash and , prefix work')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    admin_group = app_commands.Group(name='admin', description='Admin utilities')

    @admin_group.command(name='tickets', description='View open ticket stats')
    async def slash_tickets(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)
        async with __import__('aiosqlite').connect(self.bot.db.path) as db:
            async with db.execute(
                "SELECT category, COUNT(*) FROM tickets WHERE guild_id=? AND status='open' GROUP BY category",
                (interaction.guild.id,)) as cur:
                rows = await cur.fetchall()
        embed = discord.Embed(title='📊 Open Tickets', color=0x2ECC71)
        total = 0
        for cat, cnt in rows:
            embed.add_field(name=cat.upper(), value=f'`{cnt}`', inline=True)
            total += cnt
        embed.set_footer(text=f'Total: {total} open')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name='resetcounter', description='Reset ticket counter to 0')
    async def slash_reset(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, ticket_counter=0)
        await interaction.response.send_message('✅ Counter reset to 0.', ephemeral=True)

    @admin_group.command(name='forceclose', description='Force close a ticket channel')
    @app_commands.describe(channel='Ticket channel to close')
    async def slash_forceclose(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_or_mod(interaction.user, config):
            return await interaction.response.send_message('❌ Admin/Mod only.', ephemeral=True)
        await interaction.response.send_message(f'🔒 Force closing {channel.mention}...', ephemeral=True)
        cog = self.bot.get_cog('Tickets')
        if cog:
            await cog._close_ticket(channel, interaction.user)

    @commands.command(name='help')
    async def prefix_help(self, ctx):
        embed = discord.Embed(title='🤖 Titan Exchange — Commands', color=0x5865F2)
        embed.add_field(name='Tickets', value='`,close` `,add` `,remove` `,done`', inline=False)
        embed.add_field(name='Calculator', value='`,i2c <INR>` `,c2i <USD>` `,rate`', inline=False)
        embed.add_field(name='Profile', value='`,profile [@user]` `,mylimit`', inline=False)
        embed.add_field(name='Admin', value='`,setlimit @user <$>` `,setrate <rate>` `,setexchangerate <type> <rate>`', inline=False)
        embed.add_field(name='Setup', value='`,setup` `,setup transcript #ch` `,setup addrole <group> @role`', inline=False)
        embed.set_footer(text='Use /help for full slash command list')
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
