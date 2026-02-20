import discord
import logging
from discord import app_commands, ui
from discord.ext import commands
from sqlalchemy.exc import IntegrityError

from database.base import async_session_factory
from database.repository import GoalRepository


class MilestoneModal(ui.Modal, title="Add New Milestone"):
    milestone_name = ui.TextInput(
        label="Milestone Name", placeholder="e.g. Barcelona, Read Harry Potter", max_length=50
    )
    threshold = ui.TextInput(label="Threshold Amount", placeholder="e.g. 2700000", min_length=1, max_length=18)

    def __init__(self, guild_id: int, goal_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.goal_name = goal_name
        self.logger = logging.getLogger(__name__)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.threshold.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Threshold must be a positive integer.", ephemeral=True)
            return

        name = self.milestone_name.value.strip()

        await interaction.response.defer()

        async with async_session_factory() as session:
            async with session.begin():
                repo = GoalRepository(session)

                goal = await repo.get_goal_by_name(self.guild_id, self.goal_name)
                if not goal:
                    await interaction.followup.send(f"Goal **{self.goal_name}** does not exist.")
                    return

                try:
                    await repo.add_milestone(goal.id, name, amount)
                except IntegrityError:
                    await interaction.followup.send(f"A milestone named **{name}** already exists for this goal.")
                    return

        self.logger.info(f"Milestone '{name}' ({amount}) added to '{self.goal_name}' by {interaction.user.id}")
        await interaction.followup.send(f"Milestone **{name}** added to **{self.goal_name}** at **{amount}**!")


class Milestones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @app_commands.command(name="milestone", description="Add a milestone to a goal using a form.")
    @app_commands.describe(goal_name="The name of the goal")
    @app_commands.guild_only()
    async def add_milestone(self, interaction: discord.Interaction, goal_name: str):
        self.logger.info(f"Command !milestone called by {interaction.user} (Guild: {interaction.guild.id})")
        modal = MilestoneModal(guild_id=interaction.guild_id, goal_name=goal_name.lower().strip())
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(Milestones(bot))
