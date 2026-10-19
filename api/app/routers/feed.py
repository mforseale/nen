import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import Field, ValidationError
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.activity import ActivityScope, accepted_friend_ids, activity_authors
from app.files import MAX_FILE_SIZE, MAX_FILES, MAX_POST_SIZE, classify_file, clean_name, file_view, file_visible
from app.models import ProfileFile, ProfilePost, ProfileDetails, ProfilePostLike, ProfilePostComment, User
from app.profile_data import person_view, post_view, visible
from app.routers.auth import get_current_user
from app.routers.community import Audience, PostInput, owned_item
from app.routers.workspace import Input, lock_user, optional_user

router = APIRouter(tags=["feed", "files"])


@router.get("/forum/posts")
def forum_posts(response: Response, scope: ActivityScope = "all", user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    allowed = ProfilePost.visibility == "public"
    if user:
        friends = accepted_friend_ids(user.id)
        allowed = or_(allowed, ProfilePost.user_id == user.id,
                      (ProfilePost.visibility == "friends") & ProfilePost.user_id.in_(friends))
    posts = db.scalars(select(ProfilePost).where(allowed, activity_authors(ProfilePost.user_id,scope,user)).order_by(ProfilePost.created_at.desc(), ProfilePost.id.desc()).limit(100)).all()
    return [post_view(post, db, viewer=user) for post in posts]


def pin_count(db, user_id):
    return db.scalar(select(func.count()).select_from(ProfileFile).where(ProfileFile.user_id == user_id, ProfileFile.pinned.is_(True)))


def room_for_pins(db, user_id, additional):
    if pin_count(db, user_id) + additional > MAX_FILES:
        raise HTTPException(409, "В закрепе может быть не больше 10 файлов. Снимите один из закрепов.")


async def read_file(upload):
    content = await upload.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Один файл должен быть не больше 25 МиБ")
    name = clean_name(upload.filename)
    kind, media = classify_file(name, content)
    return {"name": name, "content": content, "size": len(content), "kind": kind, "media_type": media}


class FeedInput(Input):
    title: str = Field(default="", max_length=150)
    content: str = Field(default="", max_length=10000)
    url: str = Field(default="", max_length=2000)
    visibility: Audience = "private"
    keep_ids: list[int] = Field(default_factory=list, max_length=10)
    pin_new: bool = False
    remove_image: bool = False

    @classmethod
    def from_json(cls, value):
        try:
            parsed = cls.model_validate_json(value)
            # Reuse the safe HTTP(S) URL policy of legacy JSON posts.
            PostInput.safe_url(parsed.url)
            return parsed
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError):
            raise HTTPException(422, "Проверьте текст, ссылку и параметры публикации")


async def save_post(db, user, item, raw, uploads):
    payload = FeedInput.from_json(raw)
    if len(set(payload.keep_ids)) != len(payload.keep_ids) or len(payload.keep_ids) + len(uploads) > MAX_FILES:
        raise HTTPException(422, "В посте может быть до 10 разных файлов")
    files = []
    for upload in uploads:
        fields = await read_file(upload)
        if sum(item["size"] for item in files) + fields["size"] > MAX_POST_SIZE:
            raise HTTPException(413,"Суммарный размер вложений поста — до 50 МиБ")
        files.append(fields)
    lock_user(db, user.id)
    if item.id:
        refreshed = db.scalar(select(ProfilePost).where(ProfilePost.id == item.id).execution_options(populate_existing=True))
        if not refreshed:
            raise HTTPException(404,"Публикация уже удалена")
        item = refreshed
    existing = db.scalars(select(ProfileFile).where(ProfileFile.post_id == item.id).execution_options(populate_existing=True)).all() if item.id else []
    owned_ids = {asset.id for asset in existing}
    if not set(payload.keep_ids) <= owned_ids:
        raise HTTPException(404, "Вложение не найдено в этой публикации")
    by_id = {asset.id:asset for asset in existing}
    retained = [by_id[file_id] for file_id in payload.keep_ids]
    if sum(asset.size for asset in retained) + sum(asset["size"] for asset in files) > MAX_POST_SIZE:
        raise HTTPException(413, "Суммарный размер вложений поста — до 50 МиБ")
    if not (payload.title or payload.content or payload.url or retained or files or item.image_type and not payload.remove_image):
        raise HTTPException(422, "Добавьте текст, ссылку или вложение")
    removed = [asset for asset in existing if asset.id not in payload.keep_ids]
    if payload.pin_new:
        room_for_pins(db, user.id, len(files) - sum(asset.pinned for asset in removed))
    for asset in removed:
        db.delete(asset)
    for key in ("title", "content", "url", "visibility"):
        setattr(item, key, getattr(payload, key))
    item.kind, item.updated_at = "post", datetime.now(timezone.utc)
    if payload.remove_image:
        item.image, item.image_type = None, None
    db.add(item);db.flush()
    for position, asset in enumerate(retained):
        asset.position = position
    for index, fields in enumerate(files, len(retained)):
        db.add(ProfileFile(user_id=user.id, post_id=item.id, position=index, pinned=payload.pin_new, **fields))
    db.commit()
    return post_view(item, db, viewer=user)


@router.post("/my/feed", status_code=201)
async def create_post(payload: str = Form(...), files: list[UploadFile] = File(default=[]), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await save_post(db, user, ProfilePost(user_id=user.id), payload, files)


@router.put("/my/feed/{post_id}")
async def edit_post(post_id: int, payload: str = Form(...), files: list[UploadFile] = File(default=[]), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await save_post(db, user, owned_item(db, ProfilePost, post_id, user), payload, files)


@router.post("/my/files", status_code=201)
async def upload_pin(file: UploadFile = File(...), visibility: Audience = Form(default="private"), pinned: bool = Form(default=True), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fields = await read_file(file)
    lock_user(db, user.id)
    if pinned:
        room_for_pins(db, user.id, 1)
    item = ProfileFile(user_id=user.id, pinned=pinned, visibility=visibility, **fields)
    db.add(item);db.commit()
    return file_view(item,db)


@router.get("/my/files")
def own_files(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(ProfileFile).where(ProfileFile.user_id == user.id).order_by(ProfileFile.created_at.desc(),ProfileFile.id.desc())).all()
    return [file_view(item,db) for item in items]


class FileUpdate(Input):
    pinned: bool
    visibility: Audience | None = None


@router.put("/my/files/{file_id}")
def update_file(file_id: int, payload: FileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    item = owned_item(db, ProfileFile, file_id, user)
    if payload.pinned and not item.pinned:
        room_for_pins(db, user.id, 1)
    item.pinned = payload.pinned
    if payload.visibility is not None and item.post_id is None:
        item.visibility = payload.visibility
    db.commit()
    return file_view(item,db)


@router.delete("/my/files/{file_id}", status_code=204)
def delete_file(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    item = owned_item(db, ProfileFile, file_id, user)
    db.execute(update(ProfileDetails).where(ProfileDetails.user_id == user.id, ProfileDetails.status_audio_id == file_id).values(status_audio_id=None))
    db.delete(item);db.commit()


def visible_post(db, post_id, user):
    item = db.get(ProfilePost, post_id)
    if not item or not visible(db, item, user):
        raise HTTPException(404, "Публикация не найдена")
    return item


@router.get("/profile/posts/{post_id}")
def read_post(post_id: int, response: Response, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return post_view(visible_post(db, post_id, user), db, viewer=user)


@router.put("/profile/posts/{post_id}/like")
def like_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    post = visible_post(db, post_id, user)
    if not db.get(ProfilePostLike, (post_id, user.id)):
        db.add(ProfilePostLike(post_id=post_id, user_id=user.id))
    db.commit()
    return post_view(post, db, viewer=user)


@router.delete("/profile/posts/{post_id}/like")
def unlike_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    post = visible_post(db, post_id, user)
    db.execute(delete(ProfilePostLike).where(ProfilePostLike.post_id == post_id, ProfilePostLike.user_id == user.id))
    db.commit()
    return post_view(post, db, viewer=user)


class PostCommentInput(Input):
    content: str = Field(min_length=1, max_length=3000)


def post_comment_view(db, item, post, user):
    return {"id": item.id, "post_id": item.post_id, "content": item.content, "created_at": item.created_at,
            "author": person_view(db, db.get(User, item.user_id)),
            "can_delete": bool(user and user.id in (item.user_id, post.user_id))}


@router.get("/profile/posts/{post_id}/comments")
def post_comments(post_id: int, response: Response, limit: int | None = Query(default=None, ge=1, le=100), user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    post = visible_post(db, post_id, user)
    query = select(ProfilePostComment).where(ProfilePostComment.post_id == post_id).order_by(ProfilePostComment.created_at, ProfilePostComment.id)
    if limit is not None:
        query = query.limit(limit)
    items = db.scalars(query).all()
    return [post_comment_view(db, item, post, user) for item in items]


@router.post("/profile/posts/{post_id}/comments", status_code=201)
def add_post_comment(post_id: int, payload: PostCommentInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    post = visible_post(db, post_id, user)
    item = ProfilePostComment(post_id=post_id, user_id=user.id, content=payload.content)
    db.add(item);db.commit()
    return post_comment_view(db, item, post, user)


@router.delete("/profile/posts/{post_id}/comments/{comment_id}", status_code=204)
def delete_post_comment(post_id: int, comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    post = visible_post(db, post_id, user)
    item = db.get(ProfilePostComment, comment_id)
    if not item or item.post_id != post_id or user.id not in (item.user_id, post.user_id):
        raise HTTPException(404, "Комментарий не найден")
    db.delete(item);db.commit()


@router.api_route("/profile/files/{file_id}/content", methods=["GET", "HEAD"])
def content(file_id: int, request: Request, download: bool = False, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    item = db.get(ProfileFile, file_id)
    if not item or not file_visible(db, item, user):
        raise HTTPException(404, "Файл не найден")
    attachment = download or item.kind == "file"
    headers = {"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff", "Content-Security-Policy":"sandbox; default-src 'none'",
               "Content-Disposition":("attachment" if attachment else "inline") + f"; filename=download; filename*=UTF-8''{quote(item.name, safe='')}", "Accept-Ranges":"bytes"}
    start, end, status = 0, item.size - 1, 200
    if request.headers.get("range"):
        match = re.fullmatch(r"bytes=(\d*)-(\d*)",request.headers["range"])
        if not match or not any(match.groups()) or item.size == 0:
            raise HTTPException(416,"Недопустимый диапазон",headers={"Content-Range":f"bytes */{item.size}"})
        left, right = match.groups()
        if len(left)>20 or len(right)>20:
            raise HTTPException(416,"Недопустимый диапазон",headers={"Content-Range":f"bytes */{item.size}"})
        if left:
            start = int(left);end = min(int(right) if right else end, end)
        else:
            length = int(right)
            if not length:
                raise HTTPException(416,"Недопустимый диапазон",headers={"Content-Range":f"bytes */{item.size}"})
            start = max(0,item.size-length)
        if start > end:
            raise HTTPException(416,"Недопустимый диапазон",headers={"Content-Range":f"bytes */{item.size}"})
        status = 206;headers["Content-Range"] = f"bytes {start}-{end}/{item.size}"
    headers["Content-Length"] = str(max(0,end-start+1))
    return Response(None if request.method == "HEAD" else item.content[start:end+1], status_code=status, media_type="application/octet-stream" if attachment else item.media_type, headers=headers)
