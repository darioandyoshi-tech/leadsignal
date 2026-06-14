
# A generic, async-first generic config stub for Alembic
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass  # Schema managed by SQLAlchemy create_all for MVP; migrations added before production


def downgrade():
    pass
