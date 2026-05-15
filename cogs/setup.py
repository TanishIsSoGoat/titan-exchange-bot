import discord
from discord.ext import commands
from discord import app_commands
from utils import has_admin_role, has_admin_or_mod, fetch_live_rate


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _config_embed(self, guild: discord.Guild) -> discord.Embed:
        config = await self.bot.db.get_config(guild.id)
        def ch(cid): return guild.get_channel(cid).mention if cid and guild.get_channel(cid) else '`Not set`'
        def roles(lst): return ', '.join(guild.get_role(r).mention for r in lst if guild.get_role(r)) or '`None`'
        def cat(cid): return f'`{guild.get_channel(cid).name}`' if cid and guild.get_channel(cid) else '`Not set`'

        embed = discord.Embed(title='⚙️ Titan Exchange Config', color=0x5865F2)
        embed.add_field(name='Prefix', value=f'`{config["prefix"]}`', inline=True)
        embed.add_field(name='Ticket Category', value=cat(config['ticket_category']), inline=True)
        embed.add_field(name='Transcript Channel', value=ch(config['transcript_channel']), inline=True)
        embed.add_field(name='Log Channel', value=ch(config['log_channel']), inline=True)
        embed.add_field(name='Vouch Channel', value=ch(config['vouch_channel']), inline=True)
        embed.add_field(name='Rate Override', value=f'`₹{config["rate_override"]}`' if config.get('rate_override') else '`Auto (Live)`', inline=True)
        embed.add_field(name='I2C Rate', value=f'`₹{config.get("rate_i2c", 101)}`', inline=True)
        embed.add_field(name='C2I Rate (<$100)', value=f'`₹{config.get("rate_c2i_below", 97.5)}`', inline=True)
        embed.add_field(name='C2I Rate (>$100)', value=f'`₹{config.get("rate_c2i_above", 98.5)}`', inline=True)
        embed.add_field(name='Admin Roles', value=roles(config['admin_roles']), inline=False)
        embed.add_field(name='Mod Roles', value=roles(config['mod_roles']), inline=False)
        embed.add_field(name='Staff Roles', value=roles(config['staff_roles']), inline=False)
        embed.add_field(name='Dealer Roles', value=roles(config['dealer_roles']), inline=False)
        embed.set_footer(text='Use /setup or ,setup commands to change settings')
        return embed

    setup_group = app_commands.Group(name='setup', description='Configure the bot')

    @setup_group.command(name='view', description='View current bot configuration')
    async def slash_view(self, interaction: discord.Interaction):
        embed = await self._config_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_group.command(name='transcript', description='Set transcript channel')
    @app_commands.describe(channel='Channel for transcripts')
    async def slash_transcript(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, transcript_channel=channel.id)
        await interaction.response.send_message(f'✅ Transcript → {channel.mention}', ephemeral=True)

    @setup_group.command(name='logs', description='Set log channel')
    @app_commands.describe(channel='Channel for logs')
    async def slash_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, log_channel=channel.id)
        await interaction.response.send_message(f'✅ Logs → {channel.mention}', ephemeral=True)

    @setup_group.command(name='vouchchannel', description='Set the vouch channel')
    @app_commands.describe(channel='Channel where users paste vouches')
    async def slash_vouch(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, vouch_channel=channel.id)
        await interaction.response.send_message(f'✅ Vouch channel → {channel.mention}', ephemeral=True)

    @setup_group.command(name='category', description='Set ticket category')
    @app_commands.describe(category='The Discord category for tickets')
    async def slash_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, ticket_category=category.id)
        await interaction.response.send_message(f'✅ Category → **{category.name}**', ephemeral=True)

    @setup_group.command(name='prefix', description='Change command prefix')
    @app_commands.describe(prefix='New prefix e.g. ! or , or .')
    async def slash_prefix(self, interaction: discord.Interaction, prefix: str):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        if len(prefix) > 3:
            return await interaction.response.send_message('❌ Max 3 characters.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, prefix=prefix)
        await interaction.response.send_message(f'✅ Prefix changed to `{prefix}`', ephemeral=True)

    @setup_group.command(name='addrole', description='Add a role to a permission group')
    @app_commands.describe(group='Group to add to', role='Role to add')
    @app_commands.choices(group=[
        app_commands.Choice(name='Admin', value='admin_roles'),
        app_commands.Choice(name='Moderator', value='mod_roles'),
        app_commands.Choice(name='Staff', value='staff_roles'),
        app_commands.Choice(name='Dealer', value='dealer_roles'),
    ])
    async def slash_addrole(self, interaction: discord.Interaction,
                             group: app_commands.Choice[str], role: discord.Role):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        role_list = config[group.value]
        if role.id in role_list:
            return await interaction.response.send_message(f'⚠️ Already in {group.name}.', ephemeral=True)
        role_list.append(role.id)
        await self.bot.db.set_config(interaction.guild.id, **{group.value: role_list})
        await interaction.response.send_message(f'✅ {role.mention} → **{group.name}**', ephemeral=True)

    @setup_group.command(name='removerole', description='Remove a role from a permission group')
    @app_commands.choices(group=[
        app_commands.Choice(name='Admin', value='admin_roles'),
        app_commands.Choice(name='Moderator', value='mod_roles'),
        app_commands.Choice(name='Staff', value='staff_roles'),
        app_commands.Choice(name='Dealer', value='dealer_roles'),
    ])
    async def slash_removerole(self, interaction: discord.Interaction,
                                group: app_commands.Choice[str], role: discord.Role):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        role_list = config[group.value]
        if role.id not in role_list:
            return await interaction.response.send_message(f'⚠️ Not in {group.name}.', ephemeral=True)
        role_list.remove(role.id)
        await self.bot.db.set_config(interaction.guild.id, **{group.value: role_list})
        await interaction.response.send_message(f'✅ Removed {role.mention} from **{group.name}**', ephemeral=True)

    # ── Rate Commands ─────────────────────────────────────────────────────────

    @app_commands.command(name='setrate', description='Override the live USD/INR rate manually')
    @app_commands.describe(rate='Rate to set e.g. 84.5 (set 0 to go back to auto)')
    async def slash_setrate(self, interaction: discord.Interaction, rate: float):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        if rate == 0:
            await self.bot.db.set_config(interaction.guild.id, rate_override=None)
            live = await fetch_live_rate()
            return await interaction.response.send_message(
                f'✅ Rate override removed. Using live rate: **₹{live:.2f}**', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, rate_override=rate)
        await interaction.response.send_message(f'✅ USD/INR rate overridden to **₹{rate}**', ephemeral=True)

    @app_commands.command(name='setexchangerate', description='Set exchange rates (I2C/C2I)')
    @app_commands.describe(
        i2c='INR→Crypto rate (e.g. 101)',
        c2i_below='Crypto→INR rate below $100 (e.g. 97.5)',
        c2i_above='Crypto→INR rate above $100 (e.g. 98.5)'
    )
    async def slash_setexchangerate(self, interaction: discord.Interaction,
                                     i2c: float = None, c2i_below: float = None, c2i_above: float = None):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        updates = {}
        if i2c is not None:
            updates['rate_i2c'] = i2c
        if c2i_below is not None:
            updates['rate_c2i_below'] = c2i_below
        if c2i_above is not None:
            updates['rate_c2i_above'] = c2i_above
        if not updates:
            return await interaction.response.send_message('❌ Provide at least one rate to update.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, **updates)
        lines = []
        if i2c: lines.append(f'I2C: ₹{i2c}/$')
        if c2i_below: lines.append(f'C2I (<$100): ₹{c2i_below}/$')
        if c2i_above: lines.append(f'C2I (>$100): ₹{c2i_above}/$')
        await interaction.response.send_message('✅ Rates updated:\n' + '\n'.join(lines), ephemeral=True)

    # ── Exchanger Limit Commands ───────────────────────────────────────────────

    @app_commands.command(name='setlimit', description='Set an exchanger\'s deal limit in USD')
    @app_commands.describe(member='The exchanger', limit='Limit in USD e.g. 20')
    async def slash_setlimit(self, interaction: discord.Interaction, member: discord.Member, limit: float):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_exchanger_limit(interaction.guild.id, member.id, limit)
        from utils import get_rate
        rate = await get_rate(self.bot.db, interaction.guild.id)
        inr_equiv = round(limit * rate, 2)
        await interaction.response.send_message(
            f'✅ {member.mention}\'s limit set to **${limit}** (~₹{inr_equiv:,.2f})', ephemeral=True)

    @commands.command(name='setlimit')
    @commands.has_permissions(administrator=True)
    async def prefix_setlimit(self, ctx, member: discord.Member, limit: float):
        """Set exchanger limit: ,setlimit @user 20"""
        await self.bot.db.set_exchanger_limit(ctx.guild.id, member.id, limit)
        from utils import get_rate
        rate = await get_rate(self.bot.db, ctx.guild.id)
        inr_equiv = round(limit * rate, 2)
        await ctx.send(f'✅ {member.mention}\'s limit → **${limit}** (~₹{inr_equiv:,.2f})')

    # ── Prefix Setup ──────────────────────────────────────────────────────────

    @commands.group(name='setup', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def prefix_setup(self, ctx):
        embed = await self._config_embed(ctx.guild)
        await ctx.send(embed=embed)

    @prefix_setup.command(name='transcript')
    @commands.has_permissions(administrator=True)
    async def pre_transcript(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_config(ctx.guild.id, transcript_channel=channel.id)
        await ctx.send(f'✅ Transcript → {channel.mention}')

    @prefix_setup.command(name='logs')
    @commands.has_permissions(administrator=True)
    async def pre_logs(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_config(ctx.guild.id, log_channel=channel.id)
        await ctx.send(f'✅ Logs → {channel.mention}')

    @prefix_setup.command(name='vouchchannel')
    @commands.has_permissions(administrator=True)
    async def pre_vouch(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_config(ctx.guild.id, vouch_channel=channel.id)
        await ctx.send(f'✅ Vouch → {channel.mention}')

    @prefix_setup.command(name='addrole')
    @commands.has_permissions(administrator=True)
    async def pre_addrole(self, ctx, group: str, role: discord.Role):
        key_map = {'admin': 'admin_roles', 'mod': 'mod_roles', 'staff': 'staff_roles', 'dealer': 'dealer_roles'}
        key = key_map.get(group.lower())
        if not key:
            return await ctx.send('❌ Use: admin / mod / staff / dealer')
        config = await self.bot.db.get_config(ctx.guild.id)
        lst = config[key]
        if role.id not in lst:
            lst.append(role.id)
            await self.bot.db.set_config(ctx.guild.id, **{key: lst})
        await ctx.send(f'✅ {role.mention} → `{group}`')

    @prefix_setup.command(name='removerole')
    @commands.has_permissions(administrator=True)
    async def pre_removerole(self, ctx, group: str, role: discord.Role):
        key_map = {'admin': 'admin_roles', 'mod': 'mod_roles', 'staff': 'staff_roles', 'dealer': 'dealer_roles'}
        key = key_map.get(group.lower())
        if not key:
            return await ctx.send('❌ Use: admin / mod / staff / dealer')
        config = await self.bot.db.get_config(ctx.guild.id)
        lst = config[key]
        if role.id in lst:
            lst.remove(role.id)
            await self.bot.db.set_config(ctx.guild.id, **{key: lst})
        await ctx.send(f'✅ Removed {role.mention} from `{group}`')

    @prefix_setup.command(name='prefix')
    @commands.has_permissions(administrator=True)
    async def pre_prefix(self, ctx, prefix: str):
        await self.bot.db.set_config(ctx.guild.id, prefix=prefix)
        await ctx.send(f'✅ Prefix → `{prefix}`')

    @commands.command(name='setrate')
    @commands.has_permissions(administrator=True)
    async def pre_setrate(self, ctx, rate: float):
        """Override USD/INR rate: ,setrate 84.5 (use 0 for auto)"""
        if rate == 0:
            await self.bot.db.set_config(ctx.guild.id, rate_override=None)
            live = await fetch_live_rate()
            return await ctx.send(f'✅ Back to live rate: **₹{live:.2f}**')
        await self.bot.db.set_config(ctx.guild.id, rate_override=rate)
        await ctx.send(f'✅ Rate → **₹{rate}**')

    @commands.command(name='setexchangerate')
    @commands.has_permissions(administrator=True)
    async def pre_setexchangerate(self, ctx, rate_type: str, rate: float):
        """Set exchange rate: ,setexchangerate i2c 101 | c2i_below 97.5 | c2i_above 98.5"""
        key_map = {'i2c': 'rate_i2c', 'c2i_below': 'rate_c2i_below', 'c2i_above': 'rate_c2i_above'}
        key = key_map.get(rate_type.lower())
        if not key:
            return await ctx.send('❌ Use: i2c / c2i_below / c2i_above')
        await self.bot.db.set_config(ctx.guild.id, **{key: rate})
        await ctx.send(f'✅ `{rate_type}` rate → **₹{rate}**')


async def setup(bot):
    await bot.add_cog(Setup(bot))
