import discord
from discord.ext import commands
from discord import app_commands
from utils import has_admin_role


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Helper ────────────────────────────────────────────────────────────────

    async def _config_embed(self, guild: discord.Guild) -> discord.Embed:
        config = await self.bot.db.get_config(guild.id)

        def ch(cid): return guild.get_channel(cid).mention if cid and guild.get_channel(cid) else '`Not set`'
        def roles(lst): return ', '.join(guild.get_role(r).mention for r in lst if guild.get_role(r)) or '`None`'
        def cat(cid): return guild.get_channel(cid).name if cid and guild.get_channel(cid) else '`Not set`'

        embed = discord.Embed(title='⚙️ Titan Exchange Bot Config', color=0x5865F2)
        embed.add_field(name='Ticket Category', value=cat(config['ticket_category']), inline=True)
        embed.add_field(name='Closed Category', value=cat(config['closed_category']), inline=True)
        embed.add_field(name='Transcript Channel', value=ch(config['transcript_channel']), inline=True)
        embed.add_field(name='Log Channel', value=ch(config['log_channel']), inline=True)
        embed.add_field(name='Prefix', value=f'`{config["prefix"]}`', inline=True)
        embed.add_field(name='Ticket Counter', value=f'`{config["ticket_counter"]}`', inline=True)
        embed.add_field(name='Admin Roles', value=roles(config['admin_roles']), inline=False)
        embed.add_field(name='Mod Roles', value=roles(config['mod_roles']), inline=False)
        embed.add_field(name='Staff Roles', value=roles(config['staff_roles']), inline=False)
        embed.add_field(name='Dealer Roles', value=roles(config['dealer_roles']), inline=False)
        embed.set_footer(text='Use /setup or !setup commands to change any setting')
        return embed

    # ── Slash Command Group ───────────────────────────────────────────────────

    setup_group = app_commands.Group(name='setup', description='Configure the bot for this server')

    @setup_group.command(name='view', description='View current bot configuration')
    async def slash_view(self, interaction: discord.Interaction):
        embed = await self._config_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_group.command(name='transcript', description='Set the transcript log channel')
    @app_commands.describe(channel='Channel where transcripts will be sent')
    async def slash_transcript(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, transcript_channel=channel.id)
        await interaction.response.send_message(f'✅ Transcript channel set to {channel.mention}', ephemeral=True)

    @setup_group.command(name='logs', description='Set the log channel for ticket open/close events')
    @app_commands.describe(channel='Channel for ticket logs')
    async def slash_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, log_channel=channel.id)
        await interaction.response.send_message(f'✅ Log channel set to {channel.mention}', ephemeral=True)

    @setup_group.command(name='category', description='Set the Discord category where tickets are created')
    @app_commands.describe(category='The category channel')
    async def slash_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, ticket_category=category.id)
        await interaction.response.send_message(f'✅ Ticket category set to **{category.name}**', ephemeral=True)

    @setup_group.command(name='addrole', description='Add a role to a permission group')
    @app_commands.describe(
        group='Which group to add the role to',
        role='The role to add'
    )
    @app_commands.choices(group=[
        app_commands.Choice(name='Admin', value='admin_roles'),
        app_commands.Choice(name='Moderator', value='mod_roles'),
        app_commands.Choice(name='Staff / Support', value='staff_roles'),
        app_commands.Choice(name='Dealer / Trader', value='dealer_roles'),
    ])
    async def slash_addrole(self, interaction: discord.Interaction,
                             group: app_commands.Choice[str], role: discord.Role):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        role_list = config[group.value]
        if role.id in role_list:
            return await interaction.response.send_message(
                f'⚠️ {role.mention} is already in **{group.name}**.', ephemeral=True
            )
        role_list.append(role.id)
        await self.bot.db.set_config(interaction.guild.id, **{group.value: role_list})
        await interaction.response.send_message(
            f'✅ Added {role.mention} to **{group.name}**.', ephemeral=True
        )

    @setup_group.command(name='removerole', description='Remove a role from a permission group')
    @app_commands.describe(
        group='Which group to remove the role from',
        role='The role to remove'
    )
    @app_commands.choices(group=[
        app_commands.Choice(name='Admin', value='admin_roles'),
        app_commands.Choice(name='Moderator', value='mod_roles'),
        app_commands.Choice(name='Staff / Support', value='staff_roles'),
        app_commands.Choice(name='Dealer / Trader', value='dealer_roles'),
    ])
    async def slash_removerole(self, interaction: discord.Interaction,
                                group: app_commands.Choice[str], role: discord.Role):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        role_list = config[group.value]
        if role.id not in role_list:
            return await interaction.response.send_message(
                f'⚠️ {role.mention} is not in **{group.name}**.', ephemeral=True
            )
        role_list.remove(role.id)
        await self.bot.db.set_config(interaction.guild.id, **{group.value: role_list})
        await interaction.response.send_message(
            f'✅ Removed {role.mention} from **{group.name}**.', ephemeral=True
        )

    @setup_group.command(name='prefix', description='Change the bot command prefix')
    @app_commands.describe(prefix='New prefix (e.g. ! or . or $)')
    async def slash_prefix(self, interaction: discord.Interaction, prefix: str):
        config = await self.bot.db.get_config(interaction.guild.id)
        if not await has_admin_role(interaction.user, config):
            return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
        if len(prefix) > 5:
            return await interaction.response.send_message('❌ Prefix too long (max 5 chars).', ephemeral=True)
        await self.bot.db.set_config(interaction.guild.id, prefix=prefix)
        await interaction.response.send_message(f'✅ Prefix changed to `{prefix}`', ephemeral=True)

    # ── Prefix commands ───────────────────────────────────────────────────────

    @commands.group(name='setup', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def prefix_setup(self, ctx: commands.Context):
        """Bot setup commands. Use !setup <subcommand>"""
        embed = await self._config_embed(ctx.guild)
        await ctx.send(embed=embed)

    @prefix_setup.command(name='transcript')
    @commands.has_permissions(administrator=True)
    async def prefix_transcript(self, ctx, channel: discord.TextChannel):
        """Set transcript channel: !setup transcript #channel"""
        await self.bot.db.set_config(ctx.guild.id, transcript_channel=channel.id)
        await ctx.send(f'✅ Transcript channel set to {channel.mention}')

    @prefix_setup.command(name='logs')
    @commands.has_permissions(administrator=True)
    async def prefix_logs(self, ctx, channel: discord.TextChannel):
        """Set log channel: !setup logs #channel"""
        await self.bot.db.set_config(ctx.guild.id, log_channel=channel.id)
        await ctx.send(f'✅ Log channel set to {channel.mention}')

    @prefix_setup.command(name='category')
    @commands.has_permissions(administrator=True)
    async def prefix_category(self, ctx, *, category_name: str):
        """Set ticket category: !setup category <category name>"""
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        if not category:
            return await ctx.send(f'❌ Category `{category_name}` not found.')
        await self.bot.db.set_config(ctx.guild.id, ticket_category=category.id)
        await ctx.send(f'✅ Ticket category set to **{category.name}**')

    @prefix_setup.command(name='addrole')
    @commands.has_permissions(administrator=True)
    async def prefix_addrole(self, ctx, group: str, role: discord.Role):
        """Add role: !setup addrole <admin|mod|staff|dealer> @Role"""
        key_map = {'admin': 'admin_roles', 'mod': 'mod_roles', 'staff': 'staff_roles', 'dealer': 'dealer_roles'}
        key = key_map.get(group.lower())
        if not key:
            return await ctx.send('❌ Invalid group. Use: admin, mod, staff, dealer')
        config = await self.bot.db.get_config(ctx.guild.id)
        role_list = config[key]
        if role.id in role_list:
            return await ctx.send(f'⚠️ {role.mention} already in group.')
        role_list.append(role.id)
        await self.bot.db.set_config(ctx.guild.id, **{key: role_list})
        await ctx.send(f'✅ Added {role.mention} to `{group}`.')

    @prefix_setup.command(name='removerole')
    @commands.has_permissions(administrator=True)
    async def prefix_removerole(self, ctx, group: str, role: discord.Role):
        """Remove role: !setup removerole <admin|mod|staff|dealer> @Role"""
        key_map = {'admin': 'admin_roles', 'mod': 'mod_roles', 'staff': 'staff_roles', 'dealer': 'dealer_roles'}
        key = key_map.get(group.lower())
        if not key:
            return await ctx.send('❌ Invalid group. Use: admin, mod, staff, dealer')
        config = await self.bot.db.get_config(ctx.guild.id)
        role_list = config[key]
        if role.id not in role_list:
            return await ctx.send(f'⚠️ {role.mention} not in group.')
        role_list.remove(role.id)
        await self.bot.db.set_config(ctx.guild.id, **{key: role_list})
        await ctx.send(f'✅ Removed {role.mention} from `{group}`.')


async def setup(bot):
    await bot.add_cog(Setup(bot))
