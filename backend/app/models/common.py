from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Portable JSON type: compiles to JSONB on PostgreSQL (indexable, efficient) and
# falls back to generic JSON elsewhere (e.g. SQLite in tests), so models don't
# hard-fail outside of Postgres. Shared by any model with a JSON column.
PortableJSON = JSON().with_variant(JSONB, "postgresql")
