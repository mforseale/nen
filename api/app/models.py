from datetime import date, datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PactRarity(PyEnum):
    common = "common"
    rare = "rare"
    epic = "epic"
    legendary = "legendary"


class PactStatus(PyEnum):
    draft = "draft"
    active = "active"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PactVisibility(PyEnum):
    public = "public"
    private = "private"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    created_pacts: Mapped[list["Pact"]] = relationship(back_populates="creator")
    participation: Mapped[list["PactParticipant"]] = relationship(back_populates="user")


class Pact(Base):
    __tablename__ = "pacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    rarity: Mapped[PactRarity] = mapped_column(Enum(PactRarity), default=PactRarity.common, nullable=False)
    status: Mapped[PactStatus] = mapped_column(Enum(PactStatus), default=PactStatus.draft, nullable=False)
    visibility: Mapped[PactVisibility] = mapped_column(Enum(PactVisibility), default=PactVisibility.public, nullable=False)
    is_joint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stake_amount: Mapped[float | None] = mapped_column(nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    creator: Mapped[User] = relationship(back_populates="created_pacts")
    participants: Mapped[list["PactParticipant"]] = relationship(back_populates="pact")


class PactParticipant(Base):
    __tablename__ = "pact_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="participant", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    pact: Mapped[Pact] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(back_populates="participation")


class UserCredential(Base):
    __tablename__ = "user_credentials"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class PactDetails(Base):
    __tablename__ = "pact_details"
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), primary_key=True)
    template_id: Mapped[str | None] = mapped_column(String(80))
    duration_days: Mapped[int | None] = mapped_column(Integer)


class PactRequest(Base):
    __tablename__ = "pact_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), unique=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PactCheckin(Base):
    __tablename__ = "pact_checkins"
    __table_args__ = (UniqueConstraint("pact_id", "user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    content: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class NoteGrant(Base):
    __tablename__ = "note_grants"
    __table_args__ = (UniqueConstraint("note_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Calendar(Base):
    __tablename__ = "calendars"
    __table_args__ = (UniqueConstraint("user_id", "color"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7))


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    day: Mapped[date] = mapped_column(Date)


class CalendarStyle(Base):
    __tablename__ = "calendar_styles"
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(20), default="classic")


class CalendarEntryDetails(Base):
    __tablename__ = "calendar_entry_details"
    entry_id: Mapped[int] = mapped_column(ForeignKey("calendar_entries.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="event")
    description: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[str | None] = mapped_column(String(5))
    end_time: Mapped[str | None] = mapped_column(String(5))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[str | None] = mapped_column(String(80), index=True)
    pact_id: Mapped[int | None] = mapped_column(ForeignKey("pacts.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PactTopic(Base):
    __tablename__ = "pact_topics"
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(50))


class ProfileSettings(Base):
    __tablename__ = "profile_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    accent: Mapped[str] = mapped_column(String(20), default="crimson")


class ProfileAvatar(Base):
    __tablename__ = "profile_avatars"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    media_type: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(32))


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("low_id", "high_id"), CheckConstraint("low_id < high_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    low_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    high_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class YearGoal(Base):
    __tablename__ = "year_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    target: Mapped[int] = mapped_column(Integer, default=1)
    current: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(30), default="шагов")
    visibility: Mapped[str] = mapped_column(String(20), default="private")


class ProfilePost(Base):
    __tablename__ = "profile_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="post")
    title: Mapped[str] = mapped_column(String(150))
    content: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    image: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    image_type: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProfileFile(Base):
    __tablename__ = "profile_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("profile_posts.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    kind: Mapped[str] = mapped_column(String(20), default="file")
    size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PactTracking(Base):
    __tablename__ = "pact_tracking"
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utc_offset_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PactBreak(Base):
    __tablename__ = "pact_breaks"
    __table_args__ = (UniqueConstraint("pact_id", "user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    pact_id: Mapped[int] = mapped_column(ForeignKey("pacts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProfileDetails(Base):
    __tablename__ = "profile_details"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    status_text: Mapped[str] = mapped_column(String(280), default="")
    status_audio_id: Mapped[int | None] = mapped_column(ForeignKey("profile_files.id"))
    location: Mapped[str] = mapped_column(String(120), default="")
    interests: Mapped[str] = mapped_column(String(500), default="")
    website: Mapped[str] = mapped_column(String(2000), default="")
    about: Mapped[str] = mapped_column(Text, default="")


class ProfilePostLike(Base):
    __tablename__ = "profile_post_likes"
    post_id: Mapped[int] = mapped_column(ForeignKey("profile_posts.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProfilePostComment(Base):
    __tablename__ = "profile_post_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("profile_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
