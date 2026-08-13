"""Add download_events table and rom download counters

Revision ID: 0108_download_statistics
Revises: (independent branch - see the note below)
Create Date: 2026-07-29 00:00:00.000000

INDEPENDENT ALEMBIC BRANCH. This is deliberate, and changing it back will
silently corrupt the schema on the next RomM upgrade.

The patch shipped this chained off 0107_roms_dedup_cover_index, which exists in
5.1.1-beta but not in the 5.1.0 release this tree is built from - 5.1.0 ends at
0103. Simply repointing down_revision at 0103 works today and breaks later:

    - now:     db advances 0103 -> 0108, fine
    - upgrade: upstream adds 0104..0107 and beyond, all chained off 0103
    - alembic: db is at 0108, which it computes as the head, so it applies
               NOTHING and upstream's migrations are skipped in silence

That failure has no error message. The schema just quietly lacks whatever those
migrations did.

So this migration is its own branch instead. It has no upstream parent, and
depends_on only orders it after the roms table exists. Upstream's chain advances
on its own branch and ours stays where it is, so a RomM upgrade never has to
reconcile the two - which is the entire maintenance cost this fork would
otherwise carry forever.

This requires alembic to be invoked with "heads" rather than "head"; both call
sites in this tree are patched to match (backend/main.py and
docker/init_scripts/init).

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0108_download_statistics"
down_revision = None
branch_labels = ("download_stats",)

# Ordering only, not lineage: this migration alters "roms", so that table has to
# exist first. 0001 creates it and is immutable, so this dependency stays
# satisfiable no matter how far upstream moves.
depends_on = ("0001_initial_models",)

DOWNLOAD_SOURCES = ("webui", "basic_auth", "client_token", "oauth", "anonymous")
DOWNLOAD_KINDS = ("rom", "file")


def upgrade() -> None:
    op.create_table(
        "download_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("rom_id", sa.Integer(), nullable=True),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("rom_name", sa.String(length=450), nullable=False),
        sa.Column("platform_name", sa.String(length=400), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                *DOWNLOAD_SOURCES,
                native_enum=False,
                length=20,
                name="download_source",
            ),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                *DOWNLOAD_KINDS,
                native_enum=False,
                length=10,
                name="download_kind",
            ),
            nullable=False,
        ),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("downloaded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("download_events") as batch_op:
        batch_op.create_index(
            "ix_download_events_rom_time",
            ["rom_id", "downloaded_at"],
        )
        batch_op.create_index(
            "ix_download_events_user_time",
            ["user_id", "downloaded_at"],
        )
        batch_op.create_index(
            "ix_download_events_time",
            ["downloaded_at"],
        )

    with op.batch_alter_table("roms") as batch_op:
        batch_op.add_column(
            sa.Column(
                "download_count",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_downloaded_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_roms_download_count",
            ["download_count"],
        )


def downgrade() -> None:
    with op.batch_alter_table("roms") as batch_op:
        batch_op.drop_index("ix_roms_download_count")
        batch_op.drop_column("last_downloaded_at")
        batch_op.drop_column("download_count")

    with op.batch_alter_table("download_events") as batch_op:
        batch_op.drop_index("ix_download_events_time")
        batch_op.drop_index("ix_download_events_user_time")
        batch_op.drop_index("ix_download_events_rom_time")
    op.drop_table("download_events")
