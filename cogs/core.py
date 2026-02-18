import logging
import re
from typing import Optional, Sequence
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.exc import IntegrityError

from database.base import async_session_factory
from database.models import Milestone
from database.repository import GoalRepository


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        # Regex: !goal 123
        self.progress_pattern = re.compile(r"^!(\w+)\s+(\d+)$")

    def _build_progress_message(
        self,
        author: discord.Member,
        amount: int,
        goal_name: str,
        user_total: int,
        new_total: int,
        reached_milestones: Sequence[Milestone],
        next_milestone: Optional[Milestone],
    ) -> str:
        msg = (
            f"**{author.mention}** added **{amount}** to **{goal_name}**! (User total: **{user_total}**)\n"
            f"Total: **{new_total}**"
        )

        if reached_milestones:
            msg += "\n\n🎉 **MILESTONE REACHED!** 🎉"
            for ms in reached_milestones:
                msg += f"\n🏆 **{ms.name}** ({ms.threshold})"

        elif next_milestone:
            remaining = next_milestone.threshold - new_total

            if next_milestone.threshold > 0:
                percent = (new_total / next_milestone.threshold) * 100
            else:
                percent = 100.0

            msg += f"\nNext milestone: **{next_milestone.name}** in **{remaining}**/{next_milestone.threshold} ({percent:.1f}%)"

        return msg

    @app_commands.command(name="create", description="Create a new goal (e.g., steps, books).")
    @app_commands.describe(name="The name of the goal (one word)")
    async def create_goal(self, interaction: discord.Interaction, name: str):
        goal_name = name.lower().strip()
        if not goal_name.isalnum():
            await interaction.response.send_message("Goal name must be alphanumeric.", ephemeral=True)
            return

        await interaction.response.defer()

        async with async_session_factory() as session:
            async with session.begin():
                repo = GoalRepository(session)

                if await repo.get_goal_by_name(interaction.guild_id, goal_name):
                    await interaction.followup.send(f"Goal **{goal_name}** already exists.")
                    return

                await repo.get_or_create_user(interaction.user.id, interaction.user.name)

                try:
                    await repo.create_goal(
                        guild_id=interaction.guild_id,
                        creator_id=interaction.user.id,
                        name=goal_name,
                        channel_id=interaction.channel_id,
                    )
                    self.logger.info(f"Goal '{goal_name}' created by {interaction.user.id}")
                    await interaction.followup.send(
                        f"Goal **{goal_name}** created!\n-# Locked to <#{interaction.channel_id}>"
                    )

                except IntegrityError:
                    await interaction.followup.send("Error creating goal.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages like '!steps 1000' and updates progress."""
        if message.author.bot:
            return

        match = self.progress_pattern.match(message.content)
        if not match:
            return

        goal_name = match.group(1).lower()
        amount = int(match.group(2))

        if amount <= 0:
            return

        self.logger.info(
            f"!{goal_name} called by {message.author} (Guild: {message.guild.id}, channel: {message.channel.name})"
        )

        async with async_session_factory() as session:
            async with session.begin():
                repo = GoalRepository(session)

                goal = await repo.get_goal_by_name(message.guild.id, goal_name)
                if not goal:
                    self.logger.info(f"Non existing !{goal_name} called by {message.author}")
                    return
                if goal.channel_id is not None and goal.channel_id != message.channel.id:
                    self.logger.info(f"Wrong channel !{goal_name} called by {message.author}")
                    return

                user = await repo.get_or_create_user(message.author.id, message.author.name)

                await repo.add_progress(goal.id, user.id, amount)
                await session.flush()

                total = await repo.get_total_progress(goal.id)
                user_total = await repo.get_user_progress(goal.id, user.id)
                last_total = total - amount
                reached_milestones = await repo.get_newly_reached_milestones(goal.id, last_total, total)

                next_milestone = None
                if not reached_milestones:
                    next_milestone = await repo.get_next_milestone(goal.id, total)

        self.logger.info(f"User {user.username} added {amount} to {goal_name}")
        await message.add_reaction("✅")

        response_msg = self._build_progress_message(
            author=message.author,
            amount=amount,
            goal_name=goal_name,
            user_total=user_total,
            new_total=total,
            reached_milestones=reached_milestones,
            next_milestone=next_milestone,
        )

        await message.reply(response_msg)


async def setup(bot):
    await bot.add_cog(Core(bot))
