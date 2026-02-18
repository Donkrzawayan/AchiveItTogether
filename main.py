import asyncio
import logging
import discord
from discord.ext import commands
from database.base import init_db
from config import settings
from utils.logger_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class AchieveBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        logger.info("--- Database initialization ---")
        await init_db()
        logger.info("--- Database ready ---")

        await self.load_extension("cogs.core")
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.milestones")

        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("------")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            # Ignores CommandNotFound because commands are dynamically handled in on_message.
            return
        
        await super().on_command_error(ctx, error)


async def main():
    token = settings.DISCORD_TOKEN.get_secret_value()

    bot = AchieveBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
