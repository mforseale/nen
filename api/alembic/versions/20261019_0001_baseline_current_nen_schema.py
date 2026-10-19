"""Baseline current Nen schema

Revision ID: 20261019_0001
Revises: None
Create Date: 2026-10-19 19:47:55.509830
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20261019_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Frozen baseline: keep independent from current ORM models.
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)

    op.create_table('auth_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('auth_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_sessions_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('calendars',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'color')
    )
    with op.batch_alter_table('calendars', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_calendars_user_id'), ['user_id'], unique=False)

    op.create_table('friendships',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('low_id', sa.Integer(), nullable=False),
    sa.Column('high_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('low_id < high_id'),
    sa.ForeignKeyConstraint(['high_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['low_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('low_id', 'high_id')
    )
    with op.batch_alter_table('friendships', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_friendships_high_id'), ['high_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_friendships_low_id'), ['low_id'], unique=False)

    op.create_table('notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notes_user_id'), ['user_id'], unique=False)

    op.create_table('pacts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('goal', sa.Text(), nullable=True),
    sa.Column('rarity', sa.Enum('common', 'rare', 'epic', 'legendary', name='pactrarity'), nullable=False),
    sa.Column('status', sa.Enum('draft', 'active', 'completed', 'failed', 'cancelled', name='pactstatus'), nullable=False),
    sa.Column('visibility', sa.Enum('public', 'private', name='pactvisibility'), nullable=False),
    sa.Column('is_joint', sa.Boolean(), nullable=False),
    sa.Column('stake_amount', sa.Float(), nullable=True),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('creator_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pacts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pacts_id'), ['id'], unique=False)

    op.create_table('profile_avatars',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('media_type', sa.String(length=30), nullable=False),
    sa.Column('version', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('profile_posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('url', sa.String(length=2000), nullable=False),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('image', sa.LargeBinary(), nullable=True),
    sa.Column('image_type', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('profile_posts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_profile_posts_user_id'), ['user_id'], unique=False)

    op.create_table('profile_settings',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('bio', sa.Text(), nullable=False),
    sa.Column('accent', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('user_credentials',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('year_goals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('target', sa.Integer(), nullable=False),
    sa.Column('current', sa.Integer(), nullable=False),
    sa.Column('unit', sa.String(length=30), nullable=False),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('year_goals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_year_goals_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_year_goals_year'), ['year'], unique=False)

    op.create_table('calendar_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('calendar_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.ForeignKeyConstraint(['calendar_id'], ['calendars.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('calendar_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_calendar_entries_calendar_id'), ['calendar_id'], unique=False)

    op.create_table('calendar_styles',
    sa.Column('calendar_id', sa.Integer(), nullable=False),
    sa.Column('theme', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['calendar_id'], ['calendars.id'], ),
    sa.PrimaryKeyConstraint('calendar_id')
    )
    op.create_table('comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.String(length=80), nullable=True),
    sa.Column('pact_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comments_pact_id'), ['pact_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comments_template_id'), ['template_id'], unique=False)

    op.create_table('note_grants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('note_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('note_id', 'user_id')
    )
    with op.batch_alter_table('note_grants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_note_grants_note_id'), ['note_id'], unique=False)

    op.create_table('pact_checkins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pact_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pact_id', 'user_id', 'day')
    )
    with op.batch_alter_table('pact_checkins', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pact_checkins_pact_id'), ['pact_id'], unique=False)

    op.create_table('pact_details',
    sa.Column('pact_id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.String(length=80), nullable=True),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.PrimaryKeyConstraint('pact_id')
    )
    op.create_table('pact_participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pact_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pact_participants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pact_participants_id'), ['id'], unique=False)

    op.create_table('pact_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pact_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pact_id')
    )
    with op.batch_alter_table('pact_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pact_requests_recipient_id'), ['recipient_id'], unique=False)

    op.create_table('pact_topics',
    sa.Column('pact_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['pact_id'], ['pacts.id'], ),
    sa.PrimaryKeyConstraint('pact_id')
    )
    op.create_table('profile_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('media_type', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['profile_posts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('profile_files', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_profile_files_post_id'), ['post_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_profile_files_user_id'), ['user_id'], unique=False)

    op.create_table('calendar_entry_details',
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('start_time', sa.String(length=5), nullable=True),
    sa.Column('end_time', sa.String(length=5), nullable=True),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['entry_id'], ['calendar_entries.id'], ),
    sa.PrimaryKeyConstraint('entry_id')
    )


def downgrade() -> None:
    raise RuntimeError("The baseline cannot be dropped; restore a verified backup to a new database instead.")
