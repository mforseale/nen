"""Canonical pact directions, legacy projections and active capacity."""
from sqlalchemy import select

from app.catalog import TEMPLATES
from app.models import Pact, PactDetails, PactParticipant, PactStatus, PactTopic

CATEGORIES = ("Тело", "Социум", "Дисциплина", "Разум", "Созидание", "Другое")
TIERS = ("common", "rare", "epic", "legendary")
LIMIT = None  # Unlimited; retained in the compatibility capacity response.
LEGACY = {"Движение": "Тело", "Здоровье": "Тело", "Принципы": "Социум",
          "Осознанность": "Дисциплина", "Фокус": "Дисциплина", "Развитие": "Разум",
          "Творчество": "Созидание", "Личное": "Другое"}


def normalize_category(value):
    return value if value in CATEGORIES else LEGACY.get(value, "Другое")


def pact_category(db, pact, details=None):
    topic = db.get(PactTopic, pact.id)
    details = details or db.get(PactDetails, pact.id)
    template = TEMPLATES.get(details.template_id) if details else None
    return normalize_category(topic.category) if topic else template["category"] if template else "Социум" if pact.is_joint else "Другое"


def active_counts(db, user_id, exclude_id=None):
    counts = {category: {tier: 0 for tier in TIERS} for category in CATEGORIES}
    pacts = db.scalars(select(Pact).join(PactParticipant).where(PactParticipant.user_id == user_id, Pact.status == PactStatus.active)).unique().all()
    for pact in pacts:
        if pact.id != exclude_id:
            counts[pact_category(db, pact)][pact.rarity.value] += 1
    return counts


def require_room(db, user_id, category, tier, exclude_id=None, label=""):
    # Compatibility for older internal callers; directions no longer have quotas.
    return None
