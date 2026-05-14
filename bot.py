import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv
from database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger('TitanExchange')

PREFIX = os.getenv('PREFIX', '!')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class TitanBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None
        )
        self.db = Database()

    async def setup_hook(self):
        await self.db.init()
        cogs = ['cogs.tickets', 'cogs.panel', 'cogs.setup', 'cogs.admin']
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f'Loaded cog: {cog}')
            except Exception as e:
                log.error(f'Failed to load cog {cog}: {e}')
        await self.tree.sync()
        log.info('Slash commands synced.')

    async def on_ready(self):
        log.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='Titan Exchange | !help'
            )
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You don\'t have permission to use this command.', delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'❌ Missing argument: `{error.param.name}`', delete_after=5)
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            log.error(f'Command error: {error}')

bot = TitanBot()

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        log.error('DISCORD_TOKEN not set in environment variables!')
        return
    async with bot:
        await bot.start(token)

if __name__ == '__main__':
    asyncio.run(main())
