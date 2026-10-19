import base64
import binascii
import hashlib
import struct
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, field_validator, model_validator
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Friendship, ProfileAvatar, ProfileFile, ProfilePost, ProfileSettings, ProfileDetails, ProfilePostLike, ProfilePostComment, User, YearGoal
from app.profile_data import goal_view, person_view, post_view, profile_view, visible
from app.routers.auth import get_current_user
from app.routers.workspace import Decision, Input, lock_user, optional_user

router = APIRouter(tags=["profile", "friends"])
Audience = Literal["public", "friends", "private"]


def image_data(value):
    """Accept raster data only; no filesystem paths, remote fetches or SVG."""
    try:
        header, encoded = value.split(",", 1)
        media = {"data:image/png;base64": "image/png", "data:image/jpeg;base64": "image/jpeg", "data:image/webp;base64": "image/webp"}[header]
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, KeyError, binascii.Error):
        raise HTTPException(422, "Нужна картинка PNG, JPEG или WebP")
    if not content or len(content) > 1024 * 1024:
        raise HTTPException(422, "Размер картинки — не больше 1 МиБ")
    valid = False
    if media == "image/png" and len(content) >= 45 and content.startswith(b"\x89PNG\r\n\x1a\n") and content[12:16] == b"IHDR":
        width, height = struct.unpack(">II", content[16:24])
        valid = 0 < width <= 8192 and 0 < height <= 8192 and b"IEND" in content[-12:]
    elif media == "image/jpeg":
        valid = len(content) > 20 and content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")
    elif media == "image/webp":
        valid = len(content) > 20 and content.startswith(b"RIFF") and content[8:12] == b"WEBP" and int.from_bytes(content[4:8], "little") == len(content) - 8
    if not valid:
        raise HTTPException(422, "Не удалось прочитать картинку. Выберите другой файл")
    return content, media


def raster_response(content, media):
    return Response(content, media_type=media, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/my/profile")
def own_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_view(db, user, user)


@router.get("/my/profile/identity")
def own_identity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return person_view(db, user)


class ProfileInput(Input):
    full_name: str = Field(min_length=2, max_length=120)
    bio: str = Field(default="", max_length=2000)
    accent: Literal["crimson", "silver", "gold"] = "crimson"
    status_text: str = Field(default="", max_length=280)
    status_audio_id: int | None = Field(default=None, gt=0)
    location: str = Field(default="", max_length=120)
    interests: str = Field(default="", max_length=500)
    website: str = Field(default="", max_length=2000)
    about: str = Field(default="", max_length=5000)

    @field_validator("website")
    @classmethod
    def safe_website(cls, value):
        return PostInput.safe_url(value)


@router.put("/my/profile")
def edit_profile(payload: ProfileInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    settings = db.get(ProfileSettings, user.id) or ProfileSettings(user_id=user.id)
    user.full_name = payload.full_name
    settings.bio, settings.accent = payload.bio, payload.accent
    details = db.get(ProfileDetails, user.id) or ProfileDetails(user_id=user.id)
    if payload.status_audio_id:
        audio = db.get(ProfileFile, payload.status_audio_id)
        if not audio or audio.user_id != user.id or audio.kind != "audio" or audio.post_id:
            raise HTTPException(422, "Для статуса выберите свой отдельный музыкальный файл")
    # Older clients editing only name/bio keep the expanded settings unchanged.
    for key in payload.model_fields_set - {"full_name", "bio", "accent"}:
        setattr(details, key, getattr(payload, key))
    db.add(details)
    db.add(settings)
    db.commit()
    return profile_view(db, user, user)


class ImageInput(Input):
    data_url: str = Field(max_length=1_400_000)


@router.put("/my/profile/avatar")
def upload_avatar(payload: ImageInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content, media = image_data(payload.data_url)
    lock_user(db, user.id)
    avatar = db.get(ProfileAvatar, user.id) or ProfileAvatar(user_id=user.id)
    avatar.content, avatar.media_type, avatar.version = content, media, hashlib.sha256(content).hexdigest()[:24]
    db.add(avatar)
    db.commit()
    return person_view(db, user)


@router.delete("/my/profile/avatar", status_code=204)
def delete_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    avatar = db.get(ProfileAvatar, user.id)
    if avatar:
        db.delete(avatar)
        db.commit()


@router.get("/people/{username}/avatar")
def avatar(username: str, db: Session = Depends(get_db)):
    person = db.scalar(select(User).where(User.username == username))
    item = db.get(ProfileAvatar, person.id) if person else None
    if not item:
        raise HTTPException(404, "Аватар не найден")
    return raster_response(item.content, item.media_type)


def friendship_view(db, item, user):
    other_id = item.high_id if item.low_id == user.id else item.low_id
    return {"id": item.id, "person": person_view(db, db.get(User, other_id)), "status": item.status,
            "incoming": item.sender_id != user.id, "created_at": item.created_at}


@router.get("/friends")
def friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Friendship).where(or_(Friendship.low_id == user.id, Friendship.high_id == user.id)).order_by(Friendship.created_at.desc())).all()
    return [friendship_view(db, item, user) for item in items]


class FriendInput(Input):
    username: str = Field(min_length=3, max_length=51)


@router.post("/friends", status_code=201)
def add_friend(payload: FriendInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    person = db.scalar(select(User).where(User.username == payload.username.lstrip("@")))
    if not person:
        raise HTTPException(404, "Пользователь не найден")
    if person.id == user.id:
        raise HTTPException(422, "Нельзя добавить себя в друзья")
    low, high = sorted((person.id, user.id))
    lock_user(db, low)
    item = db.scalar(select(Friendship).where(Friendship.low_id == low, Friendship.high_id == high))
    if item and item.status in ("pending", "accepted"):
        raise HTTPException(409, "Вы уже друзья или заявка ожидает ответа")
    if not item:
        item = Friendship(low_id=low, high_id=high)
    item.sender_id, item.status, item.created_at = user.id, "pending", datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return friendship_view(db, item, user)


def owned_friendship(db, friendship_id, user):
    item = db.get(Friendship, friendship_id)
    if not item or user.id not in (item.low_id, item.high_id):
        raise HTTPException(404, "Заявка не найдена")
    lock_user(db, item.low_id)
    item = db.scalar(select(Friendship).where(Friendship.id == friendship_id).execution_options(populate_existing=True))
    if not item:
        raise HTTPException(404, "Заявка уже удалена")
    return item


@router.post("/friends/{friendship_id}/respond")
def respond_friend(friendship_id: int, payload: Decision, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_friendship(db, friendship_id, user)
    if item.sender_id == user.id:
        raise HTTPException(403, "Ответить может только получатель заявки")
    if item.status != "pending":
        raise HTTPException(409, "Заявка уже рассмотрена")
    item.status = "accepted" if payload.accept else "declined"
    db.commit()
    return friendship_view(db, item, user)


@router.delete("/friends/{friendship_id}", status_code=204)
def remove_friend(friendship_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_friendship(db, friendship_id, user)
    if item.status == "pending" and item.sender_id != user.id:
        raise HTTPException(403, "Входящую заявку можно принять или отклонить")
    db.delete(item)
    db.commit()


class GoalInput(Input):
    year: int = Field(ge=2000, le=2100)
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)
    target: int = Field(default=1, ge=1, le=1_000_000_000)
    current: int = Field(default=0, ge=0, le=1_000_000_000)
    unit: str = Field(default="шагов", min_length=1, max_length=30)
    visibility: Audience = "private"

    @model_validator(mode="after")
    def progress_within_target(self):
        if self.current > self.target:
            raise ValueError("Прогресс не может быть больше цели")
        return self


def owned_item(db, model, item_id, user):
    item = db.get(model, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Запись не найдена")
    return item


@router.post("/my/goals", status_code=201)
def create_goal(payload: GoalInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = YearGoal(user_id=user.id, **payload.model_dump())
    db.add(goal)
    db.commit()
    return goal_view(goal)


@router.put("/my/goals/{goal_id}")
def edit_goal(goal_id: int, payload: GoalInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = owned_item(db, YearGoal, goal_id, user)
    for key, value in payload.model_dump().items():
        setattr(goal, key, value)
    db.commit()
    return goal_view(goal)


@router.delete("/my/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(owned_item(db, YearGoal, goal_id, user))
    db.commit()


class PostInput(Input):
    kind: Literal["post", "image", "music", "film", "book", "link"] = "post"
    title: str = Field(min_length=1, max_length=150)
    content: str = Field(default="", max_length=10000)
    url: str = Field(default="", max_length=2000)
    visibility: Audience = "private"
    image_data: str | None = Field(default=None, max_length=1_400_000)
    remove_image: bool = False

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value:
            try:
                parsed = urlsplit(value)
                valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password and not any(c.isspace() or ord(c) < 32 for c in value)
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Нужна полная HTTP(S)-ссылка")
        return value


def write_post(db, item, payload):
    image, media = (image_data(payload.image_data) if payload.image_data else (None, None) if payload.remove_image else (item.image, item.image_type))
    if payload.kind == "image" and not image:
        raise HTTPException(422, "Загрузите картинку")
    if payload.kind == "post" and not payload.content and not image:
        raise HTTPException(422, "Напишите текст публикации")
    if payload.kind == "link" and not payload.url:
        raise HTTPException(422, "Добавьте ссылку")
    for key, value in payload.model_dump(exclude={"image_data", "remove_image"}).items():
        setattr(item, key, value)
    item.image, item.image_type, item.updated_at = image, media, datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return post_view(item, db, viewer=db.get(User, item.user_id))


@router.post("/my/posts", status_code=201)
def create_post(payload: PostInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return write_post(db, ProfilePost(user_id=user.id), payload)


@router.put("/my/posts/{post_id}")
def edit_post(post_id: int, payload: PostInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return write_post(db, owned_item(db, ProfilePost, post_id, user), payload)


@router.delete("/my/posts/{post_id}", status_code=204)
def delete_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    post = owned_item(db, ProfilePost, post_id, user)
    db.execute(delete(ProfilePostLike).where(ProfilePostLike.post_id == post_id))
    db.execute(delete(ProfilePostComment).where(ProfilePostComment.post_id == post_id))
    db.execute(delete(ProfileFile).where(ProfileFile.post_id == post_id, ProfileFile.user_id == user.id))
    db.delete(post)
    db.commit()


@router.get("/profile/posts/{post_id}/image")
def post_image(post_id: int, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    item = db.get(ProfilePost, post_id)
    if not item or not item.image or not visible(db, item, user):
        raise HTTPException(404, "Картинка не найдена")
    return raster_response(item.image, item.image_type)
