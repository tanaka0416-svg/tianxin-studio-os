from alembic import op
import sqlalchemy as sa


revision = "0003_task_archiving"
down_revision = "0002_task_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError("Automatic downgrade is disabled; restore a verified backup instead.")
