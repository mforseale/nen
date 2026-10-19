"""Date-based automatic progress, with explicit breaks and preserved manual history."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import PactBreak, PactCheckin, PactDetails, PactStatus, PactTracking


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def tracking_view(db, pact, user_id, utc_offset_minutes=None, now=None):
    now = now or datetime.now(timezone.utc)
    tracking = db.get(PactTracking, (pact.id, user_id))
    offset_minutes = utc_offset_minutes if utc_offset_minutes is not None else tracking.utc_offset_minutes if tracking else 0
    offset = timedelta(minutes=offset_minutes)
    end = utc(now)
    if pact.deadline:
        end = min(end, utc(pact.deadline) - timedelta(microseconds=1))
    if pact.status not in (PactStatus.active, PactStatus.draft):
        end = min(end, utc(pact.updated_at))
    end_day = (end + offset).date()
    manual = set(db.scalars(select(PactCheckin.day).where(
        PactCheckin.pact_id == pact.id, PactCheckin.user_id == user_id,
        PactCheckin.day <= end_day)).all())
    breaks = sorted(set(db.scalars(select(PactBreak.day).where(
        PactBreak.pact_id == pact.id, PactBreak.user_id == user_id,
        PactBreak.day <= end_day)).all()))
    details = db.get(PactDetails, pact.id)
    duration = details.duration_days if details else None
    start_day = (utc(tracking.started_at) + offset).date() if tracking else None
    historic = {day for day in manual if start_day is None or day < start_day}
    auto_end = end_day
    if start_day and duration:
        auto_end = min(auto_end, start_day + timedelta(days=max(0, duration-len(historic))-1))
    auto_count = max(0, (auto_end-start_day).days+1) if start_day and pact.status != PactStatus.draft else 0
    actual_breaks = {day for day in breaks if start_day and start_day <= day <= auto_end}
    total = len(historic) + auto_count - len(actual_breaks)
    if duration:
        total = min(duration, total)
    streak = 0
    if auto_count:
        # A finite pact may remain active during the final partial calendar day
        # after its duration cap. A break reported then must still reset its streak.
        streak_breaks = [day for day in breaks if start_day <= day <= end_day]
        last_break = max(streak_breaks) if streak_breaks else None
        streak = max(0, (auto_end-last_break).days) if last_break else auto_count
        cursor = start_day-timedelta(days=1)
        if not last_break:
            while cursor in historic:
                streak += 1
                cursor -= timedelta(days=1)
    else:
        cursor = end_day
        while cursor in historic:
            streak += 1
            cursor -= timedelta(days=1)
    return {"tracking_mode": "automatic" if tracking else "legacy",
            "tracking_started_on": start_day, "streak_days": streak,
            "total_days": total, "broken_days": breaks,
            "last_break_on": breaks[-1] if breaks else None,
            "progress": min(100, round(total/duration*100)) if duration else None}
