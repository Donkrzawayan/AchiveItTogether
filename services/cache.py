import logging
from database.repository import GoalRepository

logger = logging.getLogger(__name__)


class GoalCacheService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._cache: dict[int, set[str]] = {}

    async def is_valid_goal(self, guild_id: int, goal_name: str) -> bool:
        if guild_id not in self._cache:
            async with self.session_factory() as session:
                repo = GoalRepository(session)
                self._cache[guild_id] = await repo.get_goal_names_for_guild(guild_id)
            logger.info(f"Loaded {len(self._cache[guild_id])} goals into cache for guild {guild_id}.")

        return goal_name in self._cache[guild_id]

    def add_goal(self, guild_id: int, goal_name: str):
        if guild_id in self._cache:
            self._cache[guild_id].add(goal_name)

    def remove_goal(self, guild_id: int, goal_name: str):
        if guild_id in self._cache:
            self._cache[guild_id].discard(goal_name)
