from typing import Optional, Sequence
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Milestone, User, Goal, Progress


class GoalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, user_id: int, username: str) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(id=user_id, username=username)
            self.session.add(user)
            await self.session.flush()

        return user

    async def get_goal_by_name(self, guild_id: int, name: str) -> Optional[Goal]:
        stmt = select(Goal).where((Goal.guild_id == guild_id) & (Goal.name == name))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_goal(self, guild_id: int, creator_id: int, name: str, channel_id: int | None = None) -> Goal:
        """Creates a new goal.

        Raises:
            IntegrityError: If the pair guild_id and name is not unique.
        """
        goal = Goal(guild_id=guild_id, creator_id=creator_id, name=name, channel_id=channel_id)
        self.session.add(goal)
        await self.session.flush()
        return goal

    async def add_progress(self, goal_id: int, user_id: int, amount: int) -> Progress:
        progress = Progress(goal_id=goal_id, user_id=user_id, amount=amount)
        self.session.add(progress)
        return progress

    async def get_total_progress(self, goal_id: int) -> int:
        """Calculates the total progress for a given goal."""
        stmt = select(func.sum(Progress.amount)).where(Progress.goal_id == goal_id)
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total if total else 0

    async def update_goal_channel(self, goal_id: int, channel_id: Optional[int]) -> None:
        stmt = update(Goal).where(Goal.id == goal_id).values(channel_id=channel_id)
        await self.session.execute(stmt)

    async def add_milestone(self, goal_id: int, name: str, threshold: int) -> Milestone:
        """Adds a new milestone definition to a goal."""
        milestone = Milestone(goal_id=goal_id, name=name, threshold=threshold)
        self.session.add(milestone)
        await self.session.flush()
        return milestone

    async def get_newly_reached_milestones(self, goal_id: int, old_total: int, new_total: int) -> Sequence[Milestone]:
        stmt = select(Milestone).where(
            (Milestone.goal_id == goal_id) & (Milestone.threshold > old_total) & (Milestone.threshold <= new_total)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_user_progress(self, goal_id: int, user_id: int) -> int:
        stmt = select(func.sum(Progress.amount)).where((Progress.goal_id == goal_id) & (Progress.user_id == user_id))
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total if total else 0

    async def get_next_milestone(self, goal_id: int, current_total: int) -> Optional[Milestone]:
        stmt = (
            select(Milestone)
            .where((Milestone.goal_id == goal_id) & (Milestone.threshold > current_total))
            .order_by(Milestone.threshold.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
