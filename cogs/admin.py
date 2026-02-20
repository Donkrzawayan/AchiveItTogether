import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from database.base import async_session_factory
from database.repository import GoalRepository
from database.models import Goal
from config import settings


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def _check_permissions(self, user: discord.Member, goal: Goal) -> bool:
        if goal.creator_id and user.id == goal.creator_id:
            return True
        if user.id == user.guild.owner_id:
            return True
        if user.guild_permissions.administrator:
            return True
        if settings.ALLOWED_ROLE_ID and any(r.id == settings.ALLOWED_ROLE_ID for r in user.roles):
            return True
        return False

    async def _update_lock_status(self, interaction: discord.Interaction, name: str, channel_id: Optional[int]):
        await interaction.response.defer(ephemeral=True)

        goal_name = name.lower().strip()

        async with async_session_factory() as session:
            async with session.begin():
                repo = GoalRepository(session)

                goal = await repo.get_goal_by_name(interaction.guild_id, goal_name)
                if not goal:
                    await interaction.followup.send(f"Goal **{goal_name}** does not exist.")
                    return
                if not self._check_permissions(interaction.user, goal):
                    await interaction.followup.send("You don't have permission to manage this goal.")
                    return

                await repo.update_goal_channel(goal.id, channel_id)

        if channel_id:
            self.logger.info(f"Goal '{goal.name}' locked to {channel_id} by {interaction.user.id}")
            await interaction.followup.send(f"Goal **{goal.name}** is now locked to <#{channel_id}>.")
        else:
            self.logger.info(f"Goal '{goal.name}' unlocked by {interaction.user.id}")
            await interaction.followup.send(f"Goal **{goal.name}** is now unlocked and accessible everywhere.")

    @app_commands.command(name="lock_channel", description="Lock a goal to the current channel.")
    @app_commands.describe(name="The name of the goal to lock")
    @app_commands.guild_only()
    async def lock_channel(self, interaction: discord.Interaction, name: str):
        await self._update_lock_status(interaction, name, interaction.channel_id)

    @app_commands.command(name="unlock_channel", description="Unlock a goal (make it available in all channels).")
    @app_commands.describe(name="The name of the goal to unlock")
    @app_commands.guild_only()
    async def unlock_channel(self, interaction: discord.Interaction, name: str):
        await self._update_lock_status(interaction, name, None)


async def setup(bot):
    await bot.add_cog(Admin(bot))
