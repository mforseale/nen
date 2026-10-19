from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PactRarity, PactStatus, PactVisibility


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=2, max_length=120)


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    login: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class PactParticipantRead(BaseModel):
    id: int
    user_id: int
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PactBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str | None = None
    goal: str | None = None
    rarity: PactRarity = PactRarity.common
    visibility: PactVisibility = PactVisibility.public
    is_joint: bool = False
    stake_amount: float | None = None
    deadline: datetime | None = None


class PactCreate(PactBase):
    pass


class PactUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = None
    goal: str | None = None
    status: PactStatus | None = None
    rarity: PactRarity | None = None
    visibility: PactVisibility | None = None
    is_joint: bool | None = None
    stake_amount: float | None = None
    deadline: datetime | None = None


class PactRead(PactBase):
    id: int
    status: PactStatus
    creator_id: int
    created_at: datetime
    updated_at: datetime
    participants: list[PactParticipantRead] = []

    model_config = ConfigDict(from_attributes=True)


class HealthCheck(BaseModel):
    status: Literal["ok"] = "ok"
