from datetime import datetime, date, time
from typing import List
from sqlalchemy import BigInteger, String, ForeignKey, Time, Date, UniqueConstraint, func, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Discord ID
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    milestones: Mapped[List["Milestone"]] = relationship(
        "Milestone", back_populates="goal", cascade="all, delete-orphan"
    )
    progress_entries: Mapped[List["Progress"]] = relationship("Progress", back_populates="goal")

    __table_args__ = (UniqueConstraint("guild_id", "name", name="_guild_goal_uc"),)

    def __repr__(self):
        return f"<Goal(id={self.id}, guild={self.guild_id}, name='{self.name}')>"


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50))
    threshold: Mapped[int] = mapped_column(BigInteger, nullable=False)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="milestones")

    __table_args__ = (UniqueConstraint("goal_id", "name", name="_goal_milestone_uc"),)

    def __repr__(self):
        return f"<Milestone(id={self.id}, goal={self.goal_id}, name='{self.name}')>"


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped["Goal"] = relationship("Goal", back_populates="progress_entries")

    def __repr__(self):
        return f"<Progress(id={self.id}, goal={self.goal_id}, user={self.user_id}, timestamp={self.timestamp})>"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Store the days of the week as a list of integers (0=Monday, 6=Sunday)
    days_of_week: Mapped[List[int]] = mapped_column(ARRAY(Integer))
    time: Mapped[time] = mapped_column(Time, nullable=False)
    last_sent_date: Mapped[date] = mapped_column(Date, nullable=True)

    goal: Mapped["Goal"] = relationship("Goal")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (UniqueConstraint("goal_id", "user_id", name="_goal_user_uc"),)

    def __repr__(self):
        return f"<Reminder(id={self.id}, goal={self.goal_id}, user={self.user_id})>"
