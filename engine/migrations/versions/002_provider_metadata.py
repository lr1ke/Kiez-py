"""Record the actual narrative adapter independently of its model name."""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None
SQL = "ALTER TABLE chronicles ADD COLUMN provider text; UPDATE chronicles SET provider='editorial' WHERE demo_dataset IS NOT NULL;"


def upgrade():
    for statement in SQL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Destructive schema rollback requires an explicit data migration.")
