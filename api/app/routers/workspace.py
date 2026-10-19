from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog import TEMPLATES
from app.activity import ActivityScope, activity_authors
from app.database import get_db
from app.models import (Comment, Note, NoteGrant, Pact, PactCheckin,
                        PactDetails, PactParticipant, PactRarity, PactRequest, PactStatus,
                        PactTopic, PactVisibility, User)
from app.profile_data import profile_view
from app.directions import CATEGORIES, LIMIT, active_counts, pact_category, require_room
from app.routers.auth import get_current_user

router = APIRouter(tags=["workspace"])


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


def lock_user(db, user_id):
    # A write lock keeps count/check/insert atomic on SQLite; a row lock does
    # the same on PostgreSQL without changing the API contract.
    if db.bind.dialect.name == "sqlite":
        db.execute(text("UPDATE users SET username = username WHERE id = :id"), {"id": user_id})
    else:
        db.execute(select(User.id).where(User.id == user_id).with_for_update())


def optional_user(request: Request, db: Session = Depends(get_db)):
    try:
        return get_current_user(request, db)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        return None


def public_user(user):
    return {"id": user.id, "username": user.username, "full_name": user.full_name}


def member_pact(db, pact_id, user):
    pact = db.get(Pact, pact_id)
    member = db.scalar(select(PactParticipant).where(PactParticipant.pact_id == pact_id, PactParticipant.user_id == user.id))
    if not pact or not member:
        raise HTTPException(404, "Пакт не найден")
    return pact


def pact_view(db, pact, user):
    details = db.get(PactDetails, pact.id)
    days = db.scalars(select(PactCheckin.day).where(PactCheckin.pact_id == pact.id, PactCheckin.user_id == user.id).order_by(PactCheckin.day)).all()
    members = db.scalars(select(User).join(PactParticipant, User.id == PactParticipant.user_id).where(PactParticipant.pact_id == pact.id)).all()
    duration = details.duration_days if details else None
    return {"id": pact.id, "title": pact.title, "description": pact.description,
            "rarity": pact.rarity.value, "status": pact.status.value, "is_joint": pact.is_joint,
            "created_at": pact.created_at, "deadline": pact.deadline,
            "can_manage": pact.creator_id == user.id,
            "template_id": details.template_id if details else None, "duration_days": duration,
            "category": pact_category(db, pact, details), "is_custom": not pact.is_joint and not (details and details.template_id),
            "checkins": days, "progress": min(100, round(len(days) / duration * 100)) if duration else None,
            "members": [public_user(m) for m in members]}


def finish_date(start, rarity):
    if rarity == "common":
        return start + timedelta(days=7)
    if rarity == "legendary":
        return None
    year = start.year + (1 if rarity == "epic" or start.month == 12 else 0)
    month = start.month if rarity == "epic" else start.month % 12 + 1
    return start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))


@router.get("/catalog")
def catalog():
    # Retain the URL for old clients, without offering ready-made pacts.
    return []


@router.get("/my/pacts")
def my_pacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pacts = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user.id).order_by(Pact.created_at.desc())).all()
    return [pact_view(db, pact, user) for pact in pacts]


@router.get("/my/pacts/capacity")
def capacity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"limit": LIMIT, "counts": active_counts(db, user.id)}


@router.post("/catalog/{template_id}/join")
def join(template_id: str, user: User = Depends(get_current_user)):
    raise HTTPException(410, "Готовые пакты больше недоступны. Создайте свой пакт.")


class CategoryInput(Input):
    category: str = "Другое"

    @field_validator("category")
    @classmethod
    def known_category(cls, value):
        if value not in CATEGORIES:
            raise ValueError("Выберите тему пакта")
        return value


class PersonalPactInput(CategoryInput):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=5000)
    rarity: Literal["common", "rare", "epic", "legendary"] = "common"


@router.post("/my/pacts", status_code=201)
def create_personal_pact(payload: PersonalPactInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    titles = db.scalars(select(Pact.title).where(Pact.creator_id == user.id, Pact.status == PactStatus.active)).all()
    if any(title.casefold() == payload.title.casefold() for title in titles):
        raise HTTPException(409, "У вас уже есть активный пакт с таким названием")
    require_room(db, user.id, payload.category, payload.rarity)
    start = datetime.now(timezone.utc)
    end = finish_date(start, payload.rarity)
    pact = Pact(title=payload.title, description=payload.description, rarity=PactRarity(payload.rarity),
                creator_id=user.id, status=PactStatus.active, visibility=PactVisibility.private, deadline=end)
    db.add(pact)
    db.flush()
    db.add_all([PactDetails(pact_id=pact.id, duration_days=(end.date() - start.date()).days if end else None),
                PactTopic(pact_id=pact.id, category=payload.category),
                PactParticipant(pact_id=pact.id, user_id=user.id, role="creator")])
    db.commit()
    return pact_view(db, pact, user)


def lock_pact_members(db, pact):
    ids = db.scalars(select(PactParticipant.user_id).where(PactParticipant.pact_id == pact.id)).all()
    for member_id in sorted(set(ids)):
        lock_user(db, member_id)
    db.refresh(pact)
    return ids


@router.put("/my/pacts/{pact_id}/category")
def move_pact(pact_id: int, payload: CategoryInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pact = member_pact(db, pact_id, user)
    if pact.creator_id != user.id:
        raise HTTPException(403, "Перенести пакт может только автор")
    members = lock_pact_members(db, pact)
    if pact.status != PactStatus.active:
        raise HTTPException(409, "Переносить можно только активные пакты")
    for member_id in set(members):
        require_room(db, member_id, payload.category, pact.rarity.value, pact.id, "У одного из участников: " if pact.is_joint else "")
    topic = db.get(PactTopic, pact.id) or PactTopic(pact_id=pact.id)
    topic.category = payload.category
    db.add(topic)
    db.commit()
    return pact_view(db, pact, user)


@router.post("/my/pacts/{pact_id}/cancel")
def cancel_pact(pact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pact = member_pact(db, pact_id, user)
    if pact.creator_id != user.id:
        raise HTTPException(403, "Отменить пакт может только автор")
    lock_pact_members(db, pact)
    if pact.status != PactStatus.active:
        raise HTTPException(409, "Пакт сейчас не активен")
    pact.status = PactStatus.cancelled
    db.commit()
    return pact_view(db, pact, user)


class CheckinInput(Input):
    day: date
    utc_offset_minutes: int = Field(default=0, ge=-720, le=840)


@router.post("/my/pacts/checkin-all")
def checkin_all(payload: CheckinInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    utc_now = datetime.now(timezone.utc)
    if payload.day != (utc_now + timedelta(minutes=payload.utc_offset_minutes)).date():
        raise HTTPException(422, "Отметить можно только сегодняшний день")
    lock_user(db, user.id)
    pacts = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user.id, Pact.status == PactStatus.active)).unique().all()
    result = {"marked": [], "already_marked": [], "expired": [], "at_limit": []}
    for pact in pacts:
        if pact.deadline and utc_now >= pact.deadline.replace(tzinfo=timezone.utc):
            result["expired"].append(pact.id)
            continue
        if db.scalar(select(PactCheckin.id).where(PactCheckin.pact_id == pact.id, PactCheckin.user_id == user.id, PactCheckin.day == payload.day)):
            result["already_marked"].append(pact.id)
            continue
        details = db.get(PactDetails, pact.id)
        count = db.scalar(select(func.count()).select_from(PactCheckin).where(PactCheckin.pact_id == pact.id, PactCheckin.user_id == user.id))
        if details and details.duration_days and count >= details.duration_days:
            result["at_limit"].append(pact.id)
            continue
        if payload.day < pact.created_at.date() - timedelta(days=1):
            continue
        db.add(PactCheckin(pact_id=pact.id, user_id=user.id, day=payload.day))
        result["marked"].append(pact.id)
    db.commit()
    return result


@router.post("/my/pacts/{pact_id}/checkin")
def checkin(pact_id: int, payload: CheckinInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    pact = member_pact(db, pact_id, user)
    if pact.status != PactStatus.active:
        raise HTTPException(409, "Пакт сейчас не активен")
    utc_now = datetime.now(timezone.utc)
    today = (utc_now + timedelta(minutes=payload.utc_offset_minutes)).date()
    if payload.day != today or payload.day < pact.created_at.date() - timedelta(days=1):
        raise HTTPException(422, "Отметить можно только сегодняшний день")
    if pact.deadline and utc_now >= pact.deadline.replace(tzinfo=timezone.utc):
        raise HTTPException(409, "Срок пакта истёк")
    details = db.get(PactDetails, pact.id)
    count = db.scalar(select(func.count()).select_from(PactCheckin).where(PactCheckin.pact_id == pact_id, PactCheckin.user_id == user.id))
    if details and details.duration_days and count >= details.duration_days:
        return pact_view(db, pact, user)
    if not db.scalar(select(PactCheckin).where(PactCheckin.pact_id == pact_id, PactCheckin.user_id == user.id, PactCheckin.day == payload.day)):
        db.add(PactCheckin(pact_id=pact_id, user_id=user.id, day=payload.day))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return pact_view(db, pact, user)


@router.post("/my/pacts/{pact_id}/complete")
def complete(pact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pact = member_pact(db, pact_id, user)
    if pact.is_joint and pact.creator_id != user.id:
        raise HTTPException(403, "Завершить совместный пакт может автор")
    lock_pact_members(db, pact)
    if pact.status != PactStatus.active:
        raise HTTPException(409, "Пакт сейчас не активен")
    if not pact.deadline or pact.deadline.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(409, "Пакт можно завершить после истечения его срока")
    pact.status = PactStatus.completed
    db.commit()
    return pact_view(db, pact, user)


class JointInput(CategoryInput):
    category: str = "Социум"
    recipient: str = Field(min_length=3, max_length=50)
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=5000)
    duration_days: int = Field(ge=1, le=36500)


@router.post("/requests", status_code=201)
def send_request(payload: JointInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipient = db.scalar(select(User).where(User.username == payload.recipient.strip().lstrip("@")))
    if not recipient:
        raise HTTPException(404, "Пользователь не найден")
    if recipient.id == user.id:
        raise HTTPException(422, "Выберите другого пользователя")
    rarity = "common" if payload.duration_days <= 7 else "rare" if payload.duration_days <= 31 else "epic"
    lock_user(db, user.id)
    require_room(db, user.id, payload.category, rarity)
    pact = Pact(title=payload.title, description=payload.description, creator_id=user.id, rarity=PactRarity(rarity), is_joint=True, status=PactStatus.draft, visibility=PactVisibility.private)
    db.add(pact)
    db.flush()
    db.add_all([PactDetails(pact_id=pact.id, duration_days=payload.duration_days), PactTopic(pact_id=pact.id, category=payload.category), PactParticipant(pact_id=pact.id, user_id=user.id, role="creator"), PactRequest(pact_id=pact.id, sender_id=user.id, recipient_id=recipient.id)])
    db.commit()
    return {"id": pact.id, "status": "pending"}


@router.get("/requests")
def requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(PactRequest).where(or_(PactRequest.recipient_id == user.id, PactRequest.sender_id == user.id)).order_by(PactRequest.created_at.desc())).all()
    result = []
    for item in items:
        pact = db.get(Pact, item.pact_id)
        details = db.get(PactDetails, pact.id)
        result.append({"id": item.id, "pact_id": pact.id, "title": pact.title, "description": pact.description, "duration_days": details.duration_days, "category": pact_category(db, pact), "rarity": pact.rarity.value, "status": item.status, "incoming": item.recipient_id == user.id, "sender": public_user(db.get(User, item.sender_id)), "recipient": public_user(db.get(User, item.recipient_id)), "created_at": item.created_at})
    return result


class Decision(Input):
    accept: bool


@router.post("/requests/{request_id}/respond")
def respond(request_id: int, payload: Decision, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(PactRequest).where(PactRequest.id == request_id, PactRequest.recipient_id == user.id))
    if not item:
        raise HTTPException(404, "Запрос не найден")
    for participant_id in sorted((item.sender_id, item.recipient_id)):
        lock_user(db, participant_id)
    db.refresh(item)
    if item.status != "pending":
        raise HTTPException(409, "Ответ уже сохранён")
    pact = db.get(Pact, item.pact_id)
    if payload.accept:
        require_room(db, item.sender_id, pact_category(db, pact), pact.rarity.value, label="У автора: ")
        require_room(db, item.recipient_id, pact_category(db, pact), pact.rarity.value, label="У получателя: ")
    decision = "accepted" if payload.accept else "declined"
    changed = db.execute(update(PactRequest).where(PactRequest.id == request_id, PactRequest.status == "pending").values(status=decision))
    if changed.rowcount != 1:
        raise HTTPException(409, "Ответ уже сохранён")
    pact = db.get(Pact, item.pact_id)
    pact.status = PactStatus.active if payload.accept else PactStatus.cancelled
    if payload.accept:
        pact.created_at = datetime.now(timezone.utc)
        pact.deadline = pact.created_at + timedelta(days=db.get(PactDetails, pact.id).duration_days)
        db.add(PactParticipant(pact_id=pact.id, user_id=user.id))
    db.commit()
    return {"status": decision}


class NoteInput(Input):
    title: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=1, max_length=20000)
    visibility: Literal["public", "invited", "private"] = "private"
    invitees: list[str] = Field(default_factory=list, max_length=100)


def note_visible(db, note, user):
    return note.visibility == "public" or (user and (note.user_id == user.id or (note.visibility == "invited" and db.scalar(select(NoteGrant.id).where(NoteGrant.note_id == note.id, NoteGrant.user_id == user.id)))))


def note_view(db, note, user):
    author = db.get(User, note.user_id)
    invitees = db.scalars(select(User.username).join(NoteGrant, User.id == NoteGrant.user_id).where(NoteGrant.note_id == note.id)).all() if user and user.id == note.user_id else []
    return {"id": note.id, "title": note.title, "content": note.content, "visibility": note.visibility, "author": public_user(author), "invitees": invitees, "created_at": note.created_at, "updated_at": note.updated_at}


def write_note(db, note, payload, user):
    invited = []
    if payload.visibility == "invited":
        for name in {name.strip().lstrip("@") for name in payload.invitees}:
            invitee = db.scalar(select(User).where(User.username == name))
            if not invitee:
                raise HTTPException(422, f"Пользователь {name} не найден")
            if invitee.id != user.id:
                invited.append(invitee)
    note.title, note.content, note.visibility = payload.title, payload.content, payload.visibility
    note.updated_at = datetime.now(timezone.utc)
    db.add(note)
    db.flush()
    db.execute(delete(NoteGrant).where(NoteGrant.note_id == note.id))
    for invitee in invited:
        db.add(NoteGrant(note_id=note.id, user_id=invitee.id))
    db.commit()
    return note_view(db, note, user)


@router.get("/notes")
def notes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Note).where(or_(Note.user_id == user.id, Note.id.in_(select(NoteGrant.note_id).where(NoteGrant.user_id == user.id)))).order_by(Note.updated_at.desc())).all()
    return [note_view(db, n, user) for n in items if note_visible(db, n, user)]


@router.get("/notes/{note_id}")
def read_note(note_id: int, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or not note_visible(db, note, user):
        raise HTTPException(404, "Заметка не найдена")
    return note_view(db, note, user)


@router.post("/notes", status_code=201)
def create_note(payload: NoteInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return write_note(db, Note(user_id=user.id), payload, user)


@router.put("/notes/{note_id}")
def edit_note(note_id: int, payload: NoteInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(404, "Заметка не найдена")
    return write_note(db, note, payload, user)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(404, "Заметка не найдена")
    db.execute(delete(NoteGrant).where(NoteGrant.note_id == note_id))
    db.delete(note)
    db.commit()


class CommentInput(Input):
    content: str = Field(min_length=1, max_length=3000)
    template_id: str | None = None
    pact_id: int | None = None


def comment_view(db, comment):
    pact = db.get(Pact, comment.pact_id) if comment.pact_id else None
    title = pact.title if pact else TEMPLATES.get(comment.template_id, {}).get("title", "Архивное обсуждение")
    return {"id": comment.id, "content": comment.content, "template_id": comment.template_id, "pact_id": comment.pact_id, "topic_title": title, "author": public_user(db.get(User, comment.user_id)), "created_at": comment.created_at}


@router.get("/forum")
def forum(response: Response, template_id: str | None = None, pact_id: int | None = None, scope: ActivityScope = "all", user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    authors = activity_authors(Comment.user_id,scope,user)
    own = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user.id).order_by(Pact.created_at.desc())).all() if user else []
    accessible = or_(Comment.template_id.is_not(None), Comment.pact_id.in_([p.id for p in own]))
    if pact_id:
        if not user:
            raise HTTPException(401, "Войдите в профиль")
        member_pact(db, pact_id, user)
        accessible = Comment.pact_id == pact_id
    elif template_id:
        accessible = Comment.template_id == template_id
    items = db.scalars(select(Comment).where(accessible, authors).order_by(Comment.created_at.desc(), Comment.id.desc()).limit(100)).all()
    trending = db.execute(select(Comment.template_id, Comment.pact_id, func.count()).where(accessible, authors, Comment.created_at >= datetime.now(timezone.utc) - timedelta(days=7)).group_by(Comment.template_id, Comment.pact_id).order_by(func.count().desc(), Comment.template_id, Comment.pact_id).limit(4)).all()
    archive_ids = db.scalars(select(Comment.template_id).where(Comment.template_id.is_not(None)).distinct()).all()
    topics = [{"pact_id": p.id, "template_id": None, "title": p.title} for p in own]
    topics += [{"pact_id": None, "template_id": t, "title": TEMPLATES.get(t, {}).get("title", "Архивное обсуждение")} for t in archive_ids]
    return {"comments": [comment_view(db, c) for c in items], "topics": topics, "trending": [{"template_id": t, "pact_id": p, "count": count, "title": db.get(Pact, p).title if p else TEMPLATES.get(t, {}).get("title", "Архивное обсуждение")} for t, p, count in trending]}


@router.post("/forum", status_code=201)
def post_comment(payload: CommentInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if bool(payload.template_id) == bool(payload.pact_id):
        raise HTTPException(422, "Выберите один пакт")
    if payload.template_id:
        raise HTTPException(410, "Это архивное обсуждение. Выберите свой пакт.")
    if payload.pact_id:
        member_pact(db, payload.pact_id, user)
    if not payload.content.strip():
        raise HTTPException(422, "Напишите сообщение")
    comment = Comment(user_id=user.id, **payload.model_dump())
    db.add(comment)
    db.commit()
    return comment_view(db, comment)


@router.get("/people/{username}")
def profile(username: str, response: Response, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    person = db.scalar(select(User).where(User.username == username))
    if not person:
        raise HTTPException(404, "Пользователь не найден")
    items = db.scalars(select(Note).where(Note.user_id == person.id).order_by(Note.updated_at.desc())).all()
    return {**profile_view(db, person, user), "notes": [note_view(db, n, user) for n in items if note_visible(db, n, user)]}


@router.get("/search")
def search(q: str = Query(default="", max_length=100), kind: Literal["pacts", "users", "notes"] = "pacts", user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    query = q.strip().casefold()
    if not query:
        return []
    if kind == "pacts":
        if not user:
            return []
        pacts = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user.id).order_by(Pact.created_at.desc())).all()
        return [{"id": p.id, "title": p.title, "subtitle": p.rarity.value, "href": f"/people/{user.username}?pact={p.id}#pacts"} for p in pacts if query in (p.title + " " + p.description).casefold()][:20]
    if kind == "users":
        people = db.scalars(select(User).order_by(User.id)).all()
        return [{"id": p.id, "title": p.full_name, "subtitle": "@" + p.username, "href": "/people/" + p.username} for p in people if query.lstrip("@") in (p.username + " " + p.full_name).casefold()][:20]
    # Apply access rules before returning even titles or excerpts.
    items = db.scalars(select(Note).order_by(Note.updated_at.desc())).all()
    return [{"id": n.id, "title": n.title, "subtitle": "@" + db.get(User, n.user_id).username, "href": "/notes/" + str(n.id)} for n in items if note_visible(db, n, user) and query in (n.title + n.content).casefold()][:20]
