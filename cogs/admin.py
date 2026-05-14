import discord
from discord.ext import commands
from discord import app_commands
from utils import has_admin_role, has_staff_role


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help', description='Show all bot commands')
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='🤖 Titan Exchange Bot — Command List',
            color=0x5865F2,
            description='Both `/slash` and `!prefix` commands are supported.'
        )
        embed.add_field(name='🎫 Ticket Commands', value=(
            '`/close` or `!close` — Close current ticket\n'
            '`/add @user` or `!add @user` — Add user to ticket\n'
            '`/remove @user` or `!remove @user` — Remove user from ticket\n'
        ), inline=False)
        embed.add_field(name='📋 Panel Commands', value=(
            '`/panel create` — Create a new panel (admin)\n'
            '`/panel list` — List all panels\n'
            '`/panel delete <id>` — Delete a panel (admin)\n'
            '`/panel send <id> #channel` — Send panel to channel (admin)\n'
        ), inline=False)
        embed.add_field(name='⚙️ Setup Commands', value=(
            '`/setup view` or `!setup` — View current config\n'
            '`/setup transcript #ch` — Set transcript channel\n'
            '`/setup logs #ch` — Set log channel\n'
            '`/setup category <name>` — Set ticket category\n'
            '`/setup addrole <group> @role` — Add role to group\n'
            '`/setup removerole <group> @role` — Remove role from group\n'
            '`/setup prefix <prefix>` — Change prefix\n'
        ), inline=False)
        embed.add_field(name='🔧 Admin Commands', value=(
            '`/admin tickets` — View open ticket stats\n'
            '`/admin resetcounter` — Reset ticket counter\n'
            '`/admin forceclosse #channel` — Force close a ticket\n'
        ), inline=False)
        embed.set_footer(text='Titan Exchange | Bot by Claude')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    admin_group = app_commands.Group(name='admin', description='Admin-only management commands')

    @admin_group.command(name='tickets', description='View open ticket stats')
    async def slash_tickets(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_staff_role(interaction.user, config):
            return await interaction.response.send_message('❌ Staff only.', ephemeral=True)

        async with self.bot.db.path and __import__('aiosqlite').connect(self.bot.db.path) as db:
            async with db.execute(
                "SELECT category, COUNT(*) as cnt FROM tickets WHERE guild_id = ? AND status = 'open' GROUP BY category",
                (interaction.guild.id,)
            ) as cur:
                rows = await cur.fetchall()

        embed = discord.Embed(title='📊 Open Tickets', color=0x2ECC71)
        total = 0
        for row in rows:
            cat, cnt = row
            embed.add_field(name=cat.replace('_', ' ').title(), value=f'`{cnt}` open', inline=True)
            total += cnt
        embed.set_footer(text=f'Total: {total} open tickets')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name='resetcounter', description='Reset the ticket counter to 0')
    async def slash_resetcounter(self, interaction: discord.Interaction):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, ticket_counter=0)
        await interaction.response.send_message('✅ Ticket counter reset to 0.', ephemeral=True)

    @admin_group.command(name='forceclose', description='Force close a ticket channel')
    @app_commands.describe(channel='The ticket channel to force close')
    async def slash_forceclose(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await interaction.response.send_message(f'🔒 Force closing {channel.mention}...', ephemeral=True)
        cog = self.bot.get_cog('Tickets')
        if cog:
            await cog._close_ticket(channel, interaction.user)

    # ── Prefix ────────────────────────────────────────────────────────────────

    @commands.command(name='help')
    async def prefix_help(self, ctx: commands.Context):
        """Show all commands."""
        embed = discord.Embed(
            title='🤖 Titan Exchange Bot — Command List',
            color=0x5865F2
        )
        embed.add_field(name='🎫 Tickets', value='`!close` `!add @user` `!remove @user`', inline=False)
        embed.add_field(name='📋 Panels', value='`!panel list` `!panel delete <id>`\n`/panel create` `/panel send`', inline=False)
        embed.add_field(name='⚙️ Setup', value='`!setup` `!setup transcript #ch` `!setup logs #ch`\n`!setup addrole <group> @role` `!setup removerole <group> @role`', inline=False)
        embed.set_footer(text='Titan Exchange')
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
