"""initial schema: users, resumes, resume_uploads, export_jobs

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JOB_STATUS = sa.Enum("pending", "processing", "done", "failed", name="jobstatus")
EXPORT_TYPE = sa.Enum("ats", "cinematic", name="exporttype")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("photo_url", sa.String(1024)),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("profile_json", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "resume_uploads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("file_url", sa.String(1024), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("parsed_json", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_resume_uploads_user_id", "resume_uploads", ["user_id"])

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("resume_id", sa.Integer, sa.ForeignKey("resumes.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("type", EXPORT_TYPE, nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("output_url", sa.String(1024)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_export_jobs_resume_id", "export_jobs", ["resume_id"])


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("resume_uploads")
    op.drop_table("resumes")
    op.drop_table("users")
