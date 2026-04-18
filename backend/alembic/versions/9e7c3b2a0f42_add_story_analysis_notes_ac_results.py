"""add story analysis + notes + ac results

Phase 2 review workflow:
  - story_analyses: AI Agent Analyzer outputs (versioned, attributed)
  - story_notes: append-only audit trail
  - story_ac_results: per-AC verification outcome (F13)

Revision ID: 9e7c3b2a0f42
Revises: 8d2a5b1c4e90
Create Date: 2026-04-17 19:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9e7c3b2a0f42'
down_revision: Union[str, None] = '8d2a5b1c4e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------- story_analyses ----------------
    op.create_table(
        'story_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('story_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='draft'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('design_rationale', sa.Text(), nullable=True),
        sa.Column('oob_reuse', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('design_patterns_applied', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('proposed_artifacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('acceptance_criteria_mapping', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('specialist_consults', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('applicable_guidance', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('risks', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('dependencies_on_other_stories', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('estimated_story_points', sa.Integer(), nullable=True),
        sa.Column('authored_by_agent_slug', sa.String(length=100), nullable=False),
        sa.Column('authored_by_job_id', sa.UUID(), nullable=True),
        sa.Column('authored_by_model', sa.String(length=100), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_by_id', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['story_id'], ['user_stories.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['authored_by_job_id'], ['agent_jobs.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('story_id', 'version_number', name='uq_analysis_story_version'),
    )
    op.create_index('ix_analysis_content_hash', 'story_analyses', ['content_hash'])
    op.create_index(op.f('ix_story_analyses_story_id'), 'story_analyses', ['story_id'])
    op.create_index(op.f('ix_story_analyses_organization_id'), 'story_analyses', ['organization_id'])

    # ---------------- story_notes ----------------
    op.create_table(
        'story_notes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('story_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('note_type', sa.String(length=40), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('diff', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('related_id', sa.UUID(), nullable=True),
        sa.Column('author_user_id', sa.UUID(), nullable=True),
        sa.Column('author_agent_slug', sa.String(length=100), nullable=True),
        sa.Column('author_job_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['story_id'], ['user_stories.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['author_job_id'], ['agent_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_story_note_story_created', 'story_notes', ['story_id', 'created_at'])
    op.create_index(op.f('ix_story_notes_story_id'), 'story_notes', ['story_id'])
    op.create_index(op.f('ix_story_notes_organization_id'), 'story_notes', ['organization_id'])

    # ---------------- story_ac_results ----------------
    op.create_table(
        'story_ac_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('story_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('criterion_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('evidence', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('evaluated_by_agent_slug', sa.String(length=100), nullable=True),
        sa.Column('evaluated_by_model', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['story_id'], ['user_stories.id']),
        sa.ForeignKeyConstraint(['job_id'], ['agent_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ac_result_story_job', 'story_ac_results', ['story_id', 'job_id'])
    op.create_index(op.f('ix_story_ac_results_story_id'), 'story_ac_results', ['story_id'])
    op.create_index(op.f('ix_story_ac_results_job_id'), 'story_ac_results', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_story_ac_results_job_id', table_name='story_ac_results')
    op.drop_index('ix_story_ac_results_story_id', table_name='story_ac_results')
    op.drop_index('ix_ac_result_story_job', table_name='story_ac_results')
    op.drop_table('story_ac_results')

    op.drop_index('ix_story_notes_organization_id', table_name='story_notes')
    op.drop_index('ix_story_notes_story_id', table_name='story_notes')
    op.drop_index('ix_story_note_story_created', table_name='story_notes')
    op.drop_table('story_notes')

    op.drop_index('ix_story_analyses_organization_id', table_name='story_analyses')
    op.drop_index('ix_story_analyses_story_id', table_name='story_analyses')
    op.drop_index('ix_analysis_content_hash', table_name='story_analyses')
    op.drop_table('story_analyses')
