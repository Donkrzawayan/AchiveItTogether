import logging
import re
from typing import Optional, Sequence
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.exc import IntegrityError

from database.base import async_session_factory
from database.models import Goal, Milestone
from database.repository import GoalRepository
from services.cache import GoalCacheService
from utils.helpers import get_or_fetch_user


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.FORBIDDEN_GOAL_NAMES = ["help"]
        # Regex: !<goal> <amount> [@<user>]
        self.progress_pattern = re.compile(r"^!(\w+)\s+(\d+)(?:\s+<@!?(\d+)>)?\s*$")
        self.cache_service = GoalCacheService(async_session_factory)

    def _build_progress_message(
        self,
        target_user: discord.Member | discord.User,
        amount: int,
        goal_name: str,
        user_total: int,
        new_total: int,
        reached_milestones: Sequence[Milestone],
        next_milestone: Optional[Milestone],
    ) -> str:
        msg = (
            f"**{amount}** added to **{goal_name}** for **{target_user.mention}**! (User total: **{user_total}**)\n"
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

    async def _process_add_progress(
        self, guild_id: int, channel_id: int, target_user: discord.Member | discord.User, amount: int, goal_name: str
    ) -> tuple[str, str]:
        """A helper method that handles the database. Returns a tuple: (status, message)"""
        async with async_session_factory() as session:
            async with session.begin():
                repo = GoalRepository(session)

                goal = await repo.get_goal_by_name(guild_id, goal_name)
                if not goal:
                    return "not_found", ""

                if goal.channel_id is not None and goal.channel_id != channel_id:
                    return "wrong_channel", ""

                user = await repo.get_or_create_user(target_user.id, target_user.name)

                await repo.add_progress(goal.id, user.id, amount)
                await session.flush()

                total = await repo.get_total_progress(goal.id)
                user_total = await repo.get_user_progress(goal.id, user.id)
                last_total = total - amount
                reached_milestones = await repo.get_newly_reached_milestones(goal.id, last_total, total)

                next_milestone = None
                if not reached_milestones:
                    next_milestone = await repo.get_next_milestone(goal.id, total)

        response_msg = self._build_progress_message(
            target_user=target_user,
            amount=amount,
            goal_name=goal_name,
            user_total=user_total,
            new_total=total,
            reached_milestones=reached_milestones,
            next_milestone=next_milestone,
        )
        return "success", response_msg

    @app_commands.command(name="create", description="Create a new goal (e.g., steps, books).")
    @app_commands.describe(name="The name of the goal (one word)")
    @app_commands.guild_only()
    async def create_goal(self, interaction: discord.Interaction, name: str):
        goal_name = name.lower().strip()
        if not goal_name.isalnum():
            await interaction.response.send_message("Goal name must be alphanumeric.", ephemeral=True)
            return
        if goal_name in self.FORBIDDEN_GOAL_NAMES:
            await interaction.response.send_message(f"Name **{goal_name}** is forbidden for a goal.", ephemeral=True)
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

                    self.cache_service.add_goal(interaction.guild_id, goal_name)

                    self.logger.info(f"Goal '{goal_name}' created by {interaction.user.id}")
                    await interaction.followup.send(
                        f"Goal **{goal_name}** created!\n-# Locked to <#{interaction.channel_id}>"
                    )

                except IntegrityError:
                    await interaction.followup.send("Error creating goal.")

    @app_commands.command(name="add", description="Add progress to a goal.")
    @app_commands.describe(
        goal_name="The name of the goal", amount="The amount to add", user="Optional: Add progress for another user"
    )
    @app_commands.guild_only()
    async def add_progress(
        self, interaction: discord.Interaction, goal_name: str, amount: int, user: Optional[discord.Member] = None
    ):
        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        target_user = user or interaction.user
        goal_name_clean = goal_name.lower().strip()

        status, response_msg = await self._process_add_progress(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            target_user=target_user,
            amount=amount,
            goal_name=goal_name_clean,
        )

        if status == "not_found":
            await interaction.response.send_message(
                f"Goal **{goal_name_clean}** does not exist on this server.", ephemeral=True
            )
        elif status == "wrong_channel":
            await interaction.response.send_message(
                f"You can't add progress to **{goal_name_clean}** in this channel.", ephemeral=True
            )
        elif status == "success":
            self.logger.info(f"User {target_user.name} added {amount} to {goal_name_clean} via Slash Command")
            await interaction.response.send_message(response_msg)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages like '!steps 1000' or '!steps 1000 @user' and updates progress."""
        if message.author.bot or message.guild is None:
            return

        match = self.progress_pattern.match(message.content)
        if not match:
            return

        goal_name = match.group(1).lower()
        amount = int(match.group(2))

        if amount <= 0:
            return

        is_valid = await self.cache_service.is_valid_goal(message.guild.id, goal_name)
        if not is_valid:
            return

        target_user = message.author
        if match.group(3):
            target_id = int(match.group(3))
            fetched_user = await get_or_fetch_user(self.bot, target_id, message.guild)
            target_user = fetched_user if fetched_user else message.author

        self.logger.info(
            f"!{goal_name} called by {message.author.name} for {target_user.name} (Guild: {message.guild.id}, channel: {message.channel.name})"
        )

        status, response_msg = await self._process_add_progress(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            target_user=target_user,
            amount=amount,
            goal_name=goal_name,
        )

        if status == "not_found":
            self.logger.info(f"Non existing !{goal_name} called by {message.author}")
        elif status == "wrong_channel":
            self.logger.info(f"Wrong channel !{goal_name} called by {message.author}")
        elif status == "success":
            await message.add_reaction("✅")
            await message.reply(response_msg)

    def _build_help_embed(self, active_goals: Sequence[Goal] = []) -> discord.Embed:
        embed = discord.Embed(
            title="🛠️ How to use AchieveBot",
            description="Welcome to the goal tracking bot! Here is how you can manage your progress:",
            color=discord.Color.green(),
        )

        if active_goals:
            goals_lines = []
            for goal in active_goals:
                if goal.channel_id:
                    goals_lines.append(f"- **{goal.name}** (in <#{goal.channel_id}>)\n")
                else:
                    goals_lines.append(f"- **{goal.name}**\n")

            goals_text = "".join(goals_lines)

            embed.add_field(name="1. Create a Goal or progress an active one:", value=goals_text, inline=False)
        else:
            embed.add_field(
                name="1. Create a Goal",
                value="Use `/create <name>` on desired channel to start tracking a new goal (e.g. `/create steps`).\n"
                "-# This locks the goal to the channel you created it in.",
                inline=False,
            )

        embed.add_field(
            name="2. Log Progress",
            value="Type `!<goal> <amount> [@<user>]` directly in the chat!\n"
            "**Example:** `!steps 5000` or for someone else `!books 1 @User`\n"
            "Or use slash command: `/add <goal> <amount> [@<user>]`.",
            inline=False,
        )
        embed.add_field(
            name="3. Set Reminders",
            value="Use `/notify <goal>` to set up recurring DMs so you never forget to update your progress!",
            inline=False,
        )

        embed.set_footer(text="Tip: You can use !help or /help to see this message again.")
        return embed

    async def _process_help_message(self, guild_id):
        active_goals = []
        if guild_id:
            async with async_session_factory() as session:
                repo = GoalRepository(session)
                active_goals = await repo.get_active_goals_for_guild(guild_id)
        return self._build_help_embed(active_goals)

    @app_commands.command(name="help", description="Show the help menu and commands.")
    async def help_slash(self, interaction: discord.Interaction):
        embed = await self._process_help_message(interaction.guild_id)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="help")
    async def help_text(self, ctx: commands.Context):
        guild_id = ctx.guild.id if ctx.guild else None
        embed = await self._process_help_message(guild_id)
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Core(bot))
