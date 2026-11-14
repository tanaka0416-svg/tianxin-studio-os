from alembic import op
import sqlalchemy as sa


revision = "0001_legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'RETURNED', 'DONE')",
            name="ck_tasks_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "redaction_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("original_length", sa.Integer(), nullable=False),
        sa.Column("redaction_type", sa.String(length=32), nullable=False),
        sa.Column("start_position", sa.Integer(), nullable=False),
        sa.Column("end_position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    raise RuntimeError("Automatic downgrade is disabled; restore a verified backup instead.")
