import discord
from discord import app_commands
from discord.ext import commands
from typing import Sequence

from database.base import async_session_factory
from database.models import Goal
from database.repository import GoalRepository
from utils.i18n import get_text


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_help_embed(self, locale: discord.Locale | None, active_goals: Sequence[Goal] = []) -> discord.Embed:
        embed = discord.Embed(
            title=get_text(locale, "help.title"),
            description=get_text(locale, "help.desc"),
            color=discord.Color.green(),
        )

        if active_goals:
            goals_lines = [
                f"- **{goal.name}** (in <#{goal.channel_id}>)\n" if goal.channel_id else f"- **{goal.name}**\n"
                for goal in active_goals
            ]
            embed.add_field(name=get_text(locale, "help.active_goals"), value="".join(goals_lines), inline=False)
        else:
            embed.add_field(
                name=get_text(locale, "help.create_goal"),
                value=get_text(locale, "help.create_goal_val"),
                inline=False,
            )

        embed.add_field(
            name=get_text(locale, "help.log_progress"), value=get_text(locale, "help.log_progress_val"), inline=False
        )
        embed.add_field(
            name=get_text(locale, "help.set_reminders"), value=get_text(locale, "help.set_reminders_val"), inline=False
        )
        embed.set_footer(text=get_text(locale, "help.footer"))

        return embed

    async def _process_help_message(self, guild_id, locale: discord.Locale | None = None):
        active_goals = []
        if guild_id:
            async with async_session_factory() as session:
                repo = GoalRepository(session)
                active_goals = await repo.get_active_goals_for_guild(guild_id)
        return self._build_help_embed(locale, active_goals)

    @app_commands.command(name="help", description="Show the help menu and commands.")
    async def help_slash(self, interaction: discord.Interaction):
        embed = await self._process_help_message(interaction.guild_id, interaction.locale)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="help")
    async def help_text(self, ctx: commands.Context):
        guild_id = ctx.guild.id if ctx.guild else None
        locale = ctx.guild.preferred_locale if ctx.guild else None
        embed = await self._process_help_message(guild_id, locale)
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
