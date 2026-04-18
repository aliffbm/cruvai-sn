"""add figma linking fields

Adds story-level Figma file URL so the Portal agent can pull the design,
and a project-level Figma connector reference so we know which credentials
to use.

Revision ID: 8d2a5b1c4e90
Revises: 7c1f4a2e9d01
Create Date: 2026-04-17 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8d2a5b1c4e90'
down_revision: Union[str, None] = '7c1f4a2e9d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_stories',
        sa.Column('figma_file_url', sa.String(length=1000), nullable=True),
    )
    op.add_column(
        'projects',
        sa.Column('figma_connector_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_projects_figma_connector',
        source_table='projects',
        referent_table='connectors',
        local_cols=['figma_connector_id'],
        remote_cols=['id'],
    )
    op.create_index(
        op.f('ix_projects_figma_connector_id'),
        'projects', ['figma_connector_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_projects_figma_connector_id'), table_name='projects')
    op.drop_constraint('fk_projects_figma_connector', 'projects', type_='foreignkey')
    op.drop_column('projects', 'figma_connector_id')
    op.drop_column('user_stories', 'figma_file_url')
