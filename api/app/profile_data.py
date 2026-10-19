"""Shared profile projections and visibility rules. No writes or fabricated awards."""
from collections import Counter

from sqlalchemy import func, or_, select

from app.directions import CATEGORIES, pact_category
from app.files import file_view, file_visible
from app.models import (Friendship, Pact, PactCheckin, PactDetails, PactParticipant,
                        PactStatus, PactTopic, ProfileAvatar, ProfilePost,
                        ProfileFile, ProfileSettings, User, YearGoal)



def person_view(db, person):
    avatar = db.get(ProfileAvatar, person.id)
    return {"id": person.id, "username": person.username, "full_name": person.full_name,
            "avatar_url": f"/api/v1/people/{person.username}/avatar?v={avatar.version}" if avatar else None}


def relationship(db, owner_id, viewer):
    if not viewer:
        return {"status": "none", "id": None}
    if viewer.id == owner_id:
        return {"status": "self", "id": None}
    low, high = sorted((owner_id, viewer.id))
    item = db.scalar(select(Friendship).where(Friendship.low_id == low, Friendship.high_id == high))
    status = "none"
    if item and item.status == "accepted":
        status = "friends"
    elif item and item.status == "pending":
        status = "outgoing" if item.sender_id == viewer.id else "incoming"
    return {"status": status, "id": item.id if status != "none" else None}


def visible(db, item, viewer):
    return item.visibility == "public" or bool(viewer and (
        viewer.id == item.user_id or (item.visibility == "friends" and relationship(db, item.user_id, viewer)["status"] == "friends")))


def achievements(db, person):
    pacts = db.scalars(select(Pact).join(PactParticipant).where(
        PactParticipant.user_id == person.id, Pact.status.in_([PactStatus.active, PactStatus.completed]))).all()
    checkins = dict(db.execute(select(PactCheckin.pact_id, func.count()).where(
        PactCheckin.user_id == person.id).group_by(PactCheckin.pact_id)).all())
    committed = [pact for pact in pacts if checkins.get(pact.id, 0) > 0]
    tier_counts = Counter(pact.rarity.value for pact in committed)
    topic_counts = Counter(pact_category(db, pact) for pact in committed)
    kept = 0
    for pact in committed:
        details = db.get(PactDetails, pact.id)
        if pact.status == PactStatus.completed and details and details.duration_days and checkins[pact.id] / details.duration_days >= .8:
            kept += 1
    result = []

    def award(key, title, description, count, target, group, tier=None):
        result.append({"id": key, "title": title, "description": description,
                       "count": count, "target": target, "earned": count >= target, "group": group, "tier": tier})

    award("first-step", "Первый шаг", "Сделать первую ежедневную отметку в пакте", sum(checkins.values()), 1, "path")
    award("kept-word", "Сдержанное слово", "Завершить пакт с отметками не менее чем за 80% дней", kept, 1, "path")
    for tier in ("common", "rare", "epic", "legendary"):
        award("tier-" + tier, "Пять обещаний · " + tier.title(), f"5 пактов уровня {tier.title()} хотя бы с одной отметкой", tier_counts[tier], 5, "tier", tier)
    for index, category in enumerate(CATEGORIES):
        award("topic-" + str(index), category, f"5 пактов по теме «{category}» хотя бы с одной отметкой", topic_counts[category], 5, "topic")
    return result


def goal_view(goal):
    return {"id": goal.id, "year": goal.year, "title": goal.title, "description": goal.description,
            "target": goal.target, "current": goal.current, "unit": goal.unit, "visibility": goal.visibility}


def post_view(post, db=None, attachments=None):
    if attachments is None:
        attachments = db.scalars(select(ProfileFile).where(ProfileFile.post_id == post.id).order_by(ProfileFile.position, ProfileFile.id)).all() if db is not None else []
    return {"id": post.id, "kind": post.kind, "title": post.title, "content": post.content,
            "url": post.url, "visibility": post.visibility, "created_at": post.created_at, "updated_at": post.updated_at,
            "image_url": f"/api/v1/profile/posts/{post.id}/image?v={post.updated_at.timestamp()}" if post.image_type else None,
            "attachments": [file_view(item,db) for item in attachments]}


def profile_view(db, person, viewer):
    settings = db.get(ProfileSettings, person.id)
    goals = db.scalars(select(YearGoal).where(YearGoal.user_id == person.id).order_by(YearGoal.year.desc(), YearGoal.id)).all()
    posts = db.scalars(select(ProfilePost).where(ProfilePost.user_id == person.id).order_by(ProfilePost.created_at.desc(), ProfilePost.id.desc())).all()
    files = db.scalars(select(ProfileFile).where(ProfileFile.user_id == person.id).order_by(ProfileFile.position,ProfileFile.id)).all()
    friends = db.scalars(select(Friendship).where(or_(Friendship.low_id == person.id, Friendship.high_id == person.id), Friendship.status == "accepted").order_by(Friendship.id.desc()).limit(8)).all()
    count = db.scalar(select(func.count()).select_from(Friendship).where(
        or_(Friendship.low_id == person.id, Friendship.high_id == person.id), Friendship.status == "accepted"))
    return {"user": person_view(db, person), "created_at": person.created_at,
            "bio": settings.bio if settings else "", "accent": settings.accent if settings else "crimson",
            "friendship": relationship(db, person.id, viewer), "friend_count": count,
            "friend_preview": [person_view(db, db.get(User, item.high_id if item.low_id == person.id else item.low_id)) for item in friends],
            "pins": [file_view(item,db) for item in files if item.pinned and file_visible(db,item,viewer)],
            "achievements": achievements(db, person),
            "goals": [goal_view(goal) for goal in goals if visible(db, goal, viewer)],
            "posts": [post_view(post,db,[item for item in files if item.post_id == post.id]) for post in posts if visible(db, post, viewer)]}
