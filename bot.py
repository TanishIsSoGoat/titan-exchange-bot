import discord
from discord.ext import commands
import os, asyncio, logging
from dotenv import load_dotenv
from database import Database

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('TitanExchange')

class TitanBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self._get_prefix,
            intents=self._build_intents(),
            help_command=None
        )
        self.db = Database()

    def _build_intents(self):
        i = discord.Intents.default()
        i.message_content = True
        i.members = True
        i.guilds = True
        return i

    async def _get_prefix(self, bot, message):
        if not message.guild:
            return '!'
        config = await self.db.get_config(message.guild.id)
        return config.get('prefix', '!')

    async def setup_hook(self):
        await self.db.init()
        cogs = ['cogs.tickets', 'cogs.panel', 'cogs.setup', 'cogs.admin',
                'cogs.exchange', 'cogs.done', 'cogs.profile']
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f'Loaded: {cog}')
            except Exception as e:
                log.error(f'Failed {cog}: {e}')
        await self.tree.sync()
        log.info('Slash commands synced.')

    async def on_ready(self):
        log.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name='Titan Exchange'))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ No permission.', delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'❌ Missing: `{error.param.name}`', delete_after=5)
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            log.error(f'Command error: {error}')

bot = TitanBot()

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        log.error('DISCORD_TOKEN not set!')
        return
    async with bot:
        await bot.start(token)

if __name__ == '__main__':
    asyncio.run(main())
