"""Persist project platform bindings and chapter-level mappings."""

from alembic import op
import sqlalchemy as sa


revision = "0008_platform_chapter_mapping"
down_revision = "0007_automation_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("novel_projects", sa.Column("platform_book_id", sa.String(length=255), nullable=True))
    op.add_column("novel_projects", sa.Column("platform_book_title", sa.String(length=255), nullable=True))
    op.add_column("publish_tasks", sa.Column("local_chapter_number", sa.Integer(), nullable=True))
    op.add_column("publish_tasks", sa.Column("platform_book_id", sa.String(length=255), nullable=True))
    op.add_column("publish_tasks", sa.Column("platform_chapter_number", sa.Integer(), nullable=True))
    op.add_column("publish_tasks", sa.Column("platform_chapter_title", sa.String(length=255), nullable=True))
    op.add_column("publish_tasks", sa.Column("content_fingerprint", sa.String(length=64), nullable=True))
    op.execute("UPDATE publish_tasks SET local_chapter_number = 0 WHERE local_chapter_number IS NULL")
    op.alter_column("publish_tasks", "local_chapter_number", nullable=False)


def downgrade() -> None:
    op.drop_column("publish_tasks", "content_fingerprint")
    op.drop_column("publish_tasks", "platform_chapter_title")
    op.drop_column("publish_tasks", "platform_chapter_number")
    op.drop_column("publish_tasks", "platform_book_id")
    op.drop_column("publish_tasks", "local_chapter_number")
    op.drop_column("novel_projects", "platform_book_title")
    op.drop_column("novel_projects", "platform_book_id")
