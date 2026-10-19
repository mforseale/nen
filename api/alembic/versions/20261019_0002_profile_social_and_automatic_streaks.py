"""Profile status, post conversations and automatic pact tracking.

Revision ID: 20261019_0002
Revises: 20261019_0001
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "20261019_0002"
down_revision = "20261019_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pact_tracking",
        sa.Column("pact_id", sa.Integer(), sa.ForeignKey("pacts.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utc_offset_minutes", sa.Integer(), nullable=False))
    op.create_table("pact_breaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pact_id", sa.Integer(), sa.ForeignKey("pacts.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pact_id", "user_id", "day"))
    op.create_index("ix_pact_breaks_pact_id", "pact_breaks", ["pact_id"])
    op.create_table("profile_details",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("status_text", sa.String(280), nullable=False),
        sa.Column("status_audio_id", sa.Integer(), sa.ForeignKey("profile_files.id"), nullable=True),
        sa.Column("location", sa.String(120), nullable=False),
        sa.Column("interests", sa.String(500), nullable=False),
        sa.Column("website", sa.String(2000), nullable=False),
        sa.Column("about", sa.Text(), nullable=False))
    op.create_table("profile_post_likes",
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("profile_posts.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("profile_post_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("profile_posts.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_profile_post_comments_post_id", "profile_post_comments", ["post_id"])
    # Start only now: past days without a manual checkin are never invented.
    # Old finished/cancelled pacts retain exactly their manual history.
    op.get_bind().execute(sa.text(
        "INSERT INTO pact_tracking (pact_id,user_id,started_at,utc_offset_minutes) "
        "SELECT pp.pact_id,pp.user_id,:started_at,0 FROM pact_participants pp "
        "JOIN pacts p ON p.id=pp.pact_id WHERE p.status='active' "
        "GROUP BY pp.pact_id,pp.user_id"), {"started_at": datetime.now(timezone.utc)})


def downgrade():
    raise RuntimeError("This revision preserves social and streak history; restore a verified backup instead of discarding it")
