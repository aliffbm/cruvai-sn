"""add toolkit ingestion models

Introduces governance for the AI Knowledge Repository toolkit:
- AgentGuidance trio (guidance/version/label) — mirrors AgentPrompt pattern
- AgentCapability — specialist delegation graph
- AgentPlaybook trio + AgentPlaybookRoute — ServiceNow archetype routing
- GuidanceAsset — content-addressed aux file metadata
- ToolkitIngestionRun — ingestion run audit trail
- AgentDefinition.direct_invokable column — promotes specialists to first-class

Revision ID: 7c1f4a2e9d01
Revises: 35fa009f15f0
Create Date: 2026-04-17 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7c1f4a2e9d01'
down_revision: Union[str, None] = '35fa009f15f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # AgentDefinition column add
    # -------------------------------------------------------------------
    op.add_column(
        'agent_definitions',
        sa.Column('direct_invokable', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # -------------------------------------------------------------------
    # AgentGuidance trio
    # -------------------------------------------------------------------
    op.create_table(
        'agent_guidance',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('guidance_type', sa.String(length=50), nullable=False, server_default='procedural'),
        sa.Column('trigger_criteria', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('agent_types', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('source_uri', sa.String(length=500), nullable=True),
        sa.Column('source_origin', sa.String(length=50), nullable=False, server_default='authored'),
        sa.Column('requires_rewrite', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('license_type', sa.String(length=100), nullable=True),
        sa.Column('original_license_text', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_orphaned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_guidance_org_slug'),
    )
    op.create_index(op.f('ix_agent_guidance_organization_id'), 'agent_guidance', ['organization_id'])

    op.create_table(
        'agent_guidance_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('guidance_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('frontmatter', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sections', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('asset_manifest', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('authorship', sa.String(length=30), nullable=False, server_default='authored'),
        sa.Column('derived_from_version_id', sa.UUID(), nullable=True),
        sa.Column('rewrite_summary', sa.Text(), nullable=True),
        sa.Column('change_notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['guidance_id'], ['agent_guidance.id']),
        sa.ForeignKeyConstraint(['derived_from_version_id'], ['agent_guidance_versions.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guidance_id', 'version_number', name='uq_guidance_version'),
    )
    op.create_index('ix_guidance_version_content_hash', 'agent_guidance_versions', ['content_hash'])
    op.create_index(op.f('ix_agent_guidance_versions_guidance_id'), 'agent_guidance_versions', ['guidance_id'])

    op.create_table(
        'agent_guidance_labels',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('guidance_id', sa.UUID(), nullable=False),
        sa.Column('version_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('traffic_weight', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('activated_by_id', sa.UUID(), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['guidance_id'], ['agent_guidance.id']),
        sa.ForeignKeyConstraint(['version_id'], ['agent_guidance_versions.id']),
        sa.ForeignKeyConstraint(['activated_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guidance_id', 'label', name='uq_guidance_label'),
    )
    op.create_index(op.f('ix_agent_guidance_labels_guidance_id'), 'agent_guidance_labels', ['guidance_id'])

    # -------------------------------------------------------------------
    # AgentCapability — delegation graph
    # -------------------------------------------------------------------
    op.create_table(
        'agent_capabilities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('primary_agent_id', sa.UUID(), nullable=False),
        sa.Column('specialist_agent_id', sa.UUID(), nullable=False),
        sa.Column('delegation_context', sa.Text(), nullable=True),
        sa.Column('trigger_keywords', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('invocation_mode', sa.String(length=20), nullable=False, server_default='sub_agent'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['primary_agent_id'], ['agent_definitions.id']),
        sa.ForeignKeyConstraint(['specialist_agent_id'], ['agent_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('primary_agent_id', 'specialist_agent_id', name='uq_capability_pair'),
        sa.CheckConstraint('primary_agent_id <> specialist_agent_id', name='ck_capability_no_self'),
    )
    op.create_index(op.f('ix_agent_capabilities_primary_agent_id'), 'agent_capabilities', ['primary_agent_id'])
    op.create_index(op.f('ix_agent_capabilities_specialist_agent_id'), 'agent_capabilities', ['specialist_agent_id'])

    # -------------------------------------------------------------------
    # AgentPlaybook trio + routes
    # -------------------------------------------------------------------
    op.create_table(
        'agent_playbooks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_uri', sa.String(length=500), nullable=True),
        sa.Column('source_origin', sa.String(length=50), nullable=False, server_default='authored'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_orphaned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_playbook_org_slug'),
    )
    op.create_index(op.f('ix_agent_playbooks_organization_id'), 'agent_playbooks', ['organization_id'])

    op.create_table(
        'agent_playbook_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('playbook_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('stack_manifest', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('load_bearing_skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('change_notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['playbook_id'], ['agent_playbooks.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('playbook_id', 'version_number', name='uq_playbook_version'),
    )
    op.create_index('ix_playbook_version_content_hash', 'agent_playbook_versions', ['content_hash'])
    op.create_index(op.f('ix_agent_playbook_versions_playbook_id'), 'agent_playbook_versions', ['playbook_id'])

    op.create_table(
        'agent_playbook_labels',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('playbook_id', sa.UUID(), nullable=False),
        sa.Column('version_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('traffic_weight', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('activated_by_id', sa.UUID(), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['playbook_id'], ['agent_playbooks.id']),
        sa.ForeignKeyConstraint(['version_id'], ['agent_playbook_versions.id']),
        sa.ForeignKeyConstraint(['activated_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('playbook_id', 'label', name='uq_playbook_label'),
    )
    op.create_index(op.f('ix_agent_playbook_labels_playbook_id'), 'agent_playbook_labels', ['playbook_id'])

    op.create_table(
        'agent_playbook_routes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('playbook_id', sa.UUID(), nullable=False),
        sa.Column('task_pattern', sa.String(length=500), nullable=False),
        sa.Column('match_type', sa.String(length=20), nullable=False, server_default='keywords'),
        sa.Column('primary_agent_id', sa.UUID(), nullable=True),
        sa.Column('supporting_agent_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('required_guidance_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['playbook_id'], ['agent_playbooks.id']),
        sa.ForeignKeyConstraint(['primary_agent_id'], ['agent_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_playbook_route_priority', 'agent_playbook_routes', ['playbook_id', 'priority'])
    op.create_index(op.f('ix_agent_playbook_routes_playbook_id'), 'agent_playbook_routes', ['playbook_id'])

    # -------------------------------------------------------------------
    # GuidanceAsset
    # -------------------------------------------------------------------
    op.create_table(
        'guidance_assets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('guidance_version_id', sa.UUID(), nullable=False),
        sa.Column('relative_path', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_backend', sa.String(length=20), nullable=False, server_default='filesystem'),
        sa.Column('object_key', sa.String(length=1000), nullable=False),
        sa.Column('is_text', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['guidance_version_id'], ['agent_guidance_versions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guidance_version_id', 'relative_path', name='uq_guidance_asset_path'),
    )
    op.create_index('ix_guidance_asset_sha256', 'guidance_assets', ['sha256'])
    op.create_index(op.f('ix_guidance_assets_guidance_version_id'), 'guidance_assets', ['guidance_version_id'])

    # -------------------------------------------------------------------
    # ToolkitIngestionRun
    # -------------------------------------------------------------------
    op.create_table(
        'toolkit_ingestion_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_root', sa.String(length=500), nullable=True),
        sa.Column('source_commit', sa.String(length=64), nullable=True),
        sa.Column('triggered_by_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='running'),
        sa.Column('stats', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['triggered_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('toolkit_ingestion_runs')

    op.drop_index('ix_guidance_assets_guidance_version_id', table_name='guidance_assets')
    op.drop_index('ix_guidance_asset_sha256', table_name='guidance_assets')
    op.drop_table('guidance_assets')

    op.drop_index('ix_agent_playbook_routes_playbook_id', table_name='agent_playbook_routes')
    op.drop_index('ix_playbook_route_priority', table_name='agent_playbook_routes')
    op.drop_table('agent_playbook_routes')

    op.drop_index('ix_agent_playbook_labels_playbook_id', table_name='agent_playbook_labels')
    op.drop_table('agent_playbook_labels')

    op.drop_index('ix_agent_playbook_versions_playbook_id', table_name='agent_playbook_versions')
    op.drop_index('ix_playbook_version_content_hash', table_name='agent_playbook_versions')
    op.drop_table('agent_playbook_versions')

    op.drop_index('ix_agent_playbooks_organization_id', table_name='agent_playbooks')
    op.drop_table('agent_playbooks')

    op.drop_index('ix_agent_capabilities_specialist_agent_id', table_name='agent_capabilities')
    op.drop_index('ix_agent_capabilities_primary_agent_id', table_name='agent_capabilities')
    op.drop_table('agent_capabilities')

    op.drop_index('ix_agent_guidance_labels_guidance_id', table_name='agent_guidance_labels')
    op.drop_table('agent_guidance_labels')

    op.drop_index('ix_agent_guidance_versions_guidance_id', table_name='agent_guidance_versions')
    op.drop_index('ix_guidance_version_content_hash', table_name='agent_guidance_versions')
    op.drop_table('agent_guidance_versions')

    op.drop_index('ix_agent_guidance_organization_id', table_name='agent_guidance')
    op.drop_table('agent_guidance')

    op.drop_column('agent_definitions', 'direct_invokable')
