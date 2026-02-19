import logging
import discord
from datetime import datetime
from discord import app_commands
from discord.ext import commands, tasks

from cogs.ui.notifications import ReminderView
from database.base import async_session_factory
from database.repository import GoalRepository

logger = logging.getLogger(__name__)


class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_reminders_loop.start()

    def cog_unload(self):
        self.check_reminders_loop.cancel()

    @app_commands.command(name="notify", description="Setup reminders for a goal.")
    @app_commands.describe(goal_name="The name of the goal")
    async def notify(self, interaction: discord.Interaction, goal_name: str):
        await interaction.response.defer(ephemeral=True)

        goal_name_clean = goal_name.lower().strip()
        initial_days = []
        initial_time = None

        async with async_session_factory() as session:
            repo = GoalRepository(session)
            goal = await repo.get_goal_by_name(interaction.guild_id, goal_name_clean)
            if not goal:
                await interaction.followup.send(f"Goal **{goal_name_clean}** does not exist.", ephemeral=True)
                return

            reminder = await repo.get_reminder(goal.id, interaction.user.id)
            if reminder:
                initial_days = reminder.days_of_week
                initial_time = reminder.time

        view = ReminderView(interaction.guild_id, goal_name_clean, initial_days, initial_time)
        await interaction.followup.send(
            f"Please configure reminders for **{goal_name_clean}**:", view=view, ephemeral=True
        )

    async def _get_discord_user(self, user_id: int) -> discord.User | None:
        """Get the user from the cache, and if it's not there, fetch it from the API."""
        user = self.bot.get_user(user_id)
        if user:
            return user
        try:
            return await self.bot.fetch_user(user_id)
        except discord.NotFound:
            logger.warning(f"User {user_id} not found.")
            return None

    async def _send_reminder_dm(self, user: discord.User, goal_name: str, channel_id: int | None):
        description = f"Hey! Remember to work on your goal: **{goal_name}** today!"
        if channel_id:
            # '-#' is a Discord markdown prefix for a subtext
            description += f"\n\n-# Use command `!{goal_name} <amount>` in <#{channel_id}> to track progress."

        embed = discord.Embed(
            title="🔔 Goal Reminder!",
            description=description,
            color=discord.Color.blue(),
        )
        if not channel_id:
            embed.set_footer(text=f"Use command !{goal_name} <amount> to track progress.")

        await user.send(embed=embed)

    async def _process_single_reminder(self, repo, reminder, today_date):
        try:
            user = await self._get_discord_user(reminder.user_id)
            if not user:
                return

            try:
                await self._send_reminder_dm(user, reminder.goal.name, reminder.goal.channel_id)
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to user {reminder.user_id} (DMs closed).")
                return

            await repo.mark_reminder_sent(reminder.id, today_date)
            logger.info(f"Sent reminder to {user.name} for goal {reminder.goal.name}")

        except Exception as e:
            logger.error(f"Error processing reminder {reminder.id}: {e}")

    @tasks.loop(seconds=60)
    async def check_reminders_loop(self):
        now = datetime.now()
        current_day = now.weekday()  # 0 = Monday
        current_time = now.time().replace(second=0, microsecond=0)
        today_date = now.date()

        try:
            async with async_session_factory() as session:
                async with session.begin():
                    repo = GoalRepository(session)

                    due_reminders = await repo.get_due_reminders(current_day, current_time, today_date)
                    if not due_reminders:
                        return

                    logger.info(f"Found {len(due_reminders)} reminders to send.")

                    for reminder in due_reminders:
                        await self._process_single_reminder(repo, reminder, today_date)

        except Exception as e:
            logger.error(f"Critical error in check_reminders_loop: {e}")

    @check_reminders_loop.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Notifications(bot))
