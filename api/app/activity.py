"""Author filters supplement visibility checks; they never grant access."""
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select, true

from app.models import Friendship

ActivityScope = Literal["all", "friends", "mine"]


def accepted_friend_ids(user_id):
    return select(Friendship.high_id).where(Friendship.low_id == user_id, Friendship.status == "accepted").union(
        select(Friendship.low_id).where(Friendship.high_id == user_id, Friendship.status == "accepted"))


def activity_authors(column, scope, user):
    if scope == "all":
        return true()
    if not user:
        raise HTTPException(401, "Войдите, чтобы посмотреть эту активность")
    return column == user.id if scope == "mine" else column.in_(accepted_friend_ids(user.id))
