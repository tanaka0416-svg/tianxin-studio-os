from alembic import op
import sqlalchemy as sa


revision = "0002_task_metadata"
down_revision = "0001_legacy_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("department", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("assigned_ai", sa.Text(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("priority", sa.Text(), server_default="MEDIUM", nullable=False),
    )
    op.add_column("tasks", sa.Column("due_date", sa.Date(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Automatic downgrade is disabled; restore a verified backup instead.")
