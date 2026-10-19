"""Private calendar planning with additive metadata for existing user records."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Calendar, CalendarEntry, CalendarEntryDetails, CalendarStyle, User
from app.routers.auth import get_current_user
from app.routers.workspace import Input, lock_user

router = APIRouter(tags=["calendars"])
Theme = Literal["classic", "grid", "journal"]
Kind = Literal["task", "event", "note"]
Priority = Literal["low", "normal", "high"]
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class CalendarInput(Input):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    theme: Theme = "classic"

    @field_validator("color")
    @classmethod
    def lowercase(cls, value):
        return value.lower()


class EntryInput(Input):
    calendar_id: int
    title: str = Field(min_length=1, max_length=150)
    day: date
    kind: Kind = "event"
    description: str = Field(default="", max_length=5000)
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    priority: Priority = "normal"
    completed: bool = False

    @model_validator(mode="after")
    def valid_schedule(self):
        if self.end_time and (not self.start_time or self.end_time <= self.start_time):
            raise ValueError("Время окончания должно быть позже начала в пределах одного дня")
        if self.kind != "task" and self.completed:
            raise ValueError("Выполнение можно отмечать только у задачи")
        return self


class EntryUpdate(Input):
    calendar_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=150)
    day: date | None = None
    kind: Kind | None = None
    description: str | None = Field(default=None, max_length=5000)
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    priority: Priority | None = None
    completed: bool | None = None


def owned_calendar(db, calendar_id, user):
    calendar = db.get(Calendar, calendar_id)
    if not calendar or calendar.user_id != user.id:
        raise HTTPException(404, "Календарь не найден")
    return calendar


def owned_entry(db, entry_id, user):
    entry = db.get(CalendarEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Запись не найдена")
    owned_calendar(db, entry.calendar_id, user)
    return entry


def calendar_view(db, calendar):
    style = db.get(CalendarStyle, calendar.id)
    return {"id": calendar.id, "name": calendar.name, "color": calendar.color,
            "theme": style.theme if style else "classic"}


def entry_view(entry, details=None):
    return {"id": entry.id, "calendar_id": entry.calendar_id, "title": entry.title,
            "day": entry.day, "kind": details.kind if details else "note",
            "description": details.description if details else "",
            "start_time": details.start_time if details else None,
            "end_time": details.end_time if details else None,
            "priority": details.priority if details else "normal",
            "completed": details.completed if details else False}


def write_entry(db, entry, payload):
    entry.calendar_id, entry.title, entry.day = payload.calendar_id, payload.title, payload.day
    db.add(entry)
    db.flush()
    details = db.get(CalendarEntryDetails, entry.id) or CalendarEntryDetails(entry_id=entry.id)
    for name in ["kind", "description", "start_time", "end_time", "priority", "completed"]:
        setattr(details, name, getattr(payload, name))
    db.add(details)
    db.commit()
    return entry_view(entry, details)


@router.get("/calendars")
def calendars(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Calendar).where(Calendar.user_id == user.id).order_by(Calendar.id)).all()
    return [calendar_view(db, calendar) for calendar in items]


@router.post("/calendars", status_code=201)
def create_calendar(payload: CalendarInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    if db.scalar(select(func.count()).select_from(Calendar).where(Calendar.user_id == user.id)) >= 10:
        raise HTTPException(409, "Можно создать не более 10 календарей")
    calendar = Calendar(user_id=user.id, name=payload.name, color=payload.color)
    db.add(calendar)
    try:
        db.flush()
        db.add(CalendarStyle(calendar_id=calendar.id, theme=payload.theme))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот цвет уже используется")
    return calendar_view(db, calendar)


@router.get("/calendars/{calendar_id}")
def get_calendar(calendar_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return calendar_view(db, owned_calendar(db, calendar_id, user))


@router.put("/calendars/{calendar_id}")
def edit_calendar(calendar_id: int, payload: CalendarInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    calendar = owned_calendar(db, calendar_id, user)
    calendar.name, calendar.color = payload.name, payload.color
    style = db.get(CalendarStyle, calendar_id) or CalendarStyle(calendar_id=calendar_id)
    style.theme = payload.theme
    db.add(style)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот цвет уже используется")
    return calendar_view(db, calendar)


@router.delete("/calendars/{calendar_id}", status_code=204)
def delete_calendar(calendar_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    calendar = owned_calendar(db, calendar_id, user)
    entry_ids = select(CalendarEntry.id).where(CalendarEntry.calendar_id == calendar_id)
    db.execute(delete(CalendarEntryDetails).where(CalendarEntryDetails.entry_id.in_(entry_ids)))
    db.execute(delete(CalendarEntry).where(CalendarEntry.calendar_id == calendar_id))
    db.execute(delete(CalendarStyle).where(CalendarStyle.calendar_id == calendar_id))
    db.delete(calendar)
    db.commit()


@router.get("/calendar-entries")
def entries(start: date, end: date, calendar_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "Выберите период от одного дня до года")
    statement = select(CalendarEntry).join(Calendar).where(
        Calendar.user_id == user.id, CalendarEntry.day >= start, CalendarEntry.day <= end
    )
    if calendar_id is not None:
        owned_calendar(db, calendar_id, user)
        statement = statement.where(CalendarEntry.calendar_id == calendar_id)
    items = db.scalars(statement.order_by(CalendarEntry.day, CalendarEntry.id)).all()
    details = {d.entry_id: d for d in db.scalars(select(CalendarEntryDetails).where(
        CalendarEntryDetails.entry_id.in_([entry.id for entry in items])
    )).all()} if items else {}
    return [entry_view(entry, details.get(entry.id)) for entry in items]


@router.post("/calendar-entries", status_code=201)
def create_entry(payload: EntryInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_calendar(db, payload.calendar_id, user)
    return write_entry(db, CalendarEntry(), payload)


@router.get("/calendar-entries/{entry_id}")
def get_entry(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = owned_entry(db, entry_id, user)
    return entry_view(entry, db.get(CalendarEntryDetails, entry_id))


@router.patch("/calendar-entries/{entry_id}")
def edit_entry(entry_id: int, payload: EntryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = owned_entry(db, entry_id, user)
    previous = entry_view(entry, db.get(CalendarEntryDetails, entry_id))
    previous.pop("id")
    try:
        merged = EntryInput.model_validate({**previous, **payload.model_dump(exclude_unset=True)})
    except ValidationError as exc:
        raise HTTPException(422, "Проверьте поля записи: дату, тип и время окончания") from exc
    owned_calendar(db, merged.calendar_id, user)
    return write_entry(db, entry, merged)


@router.delete("/calendar-entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = owned_entry(db, entry_id, user)
    db.execute(delete(CalendarEntryDetails).where(CalendarEntryDetails.entry_id == entry_id))
    db.delete(entry)
    db.commit()
