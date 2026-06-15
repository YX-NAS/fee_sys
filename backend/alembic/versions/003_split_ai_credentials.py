"""Split AI portal and API credentials

Revision ID: 003
Revises: 002
Create Date: 2026-06-15
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_provider_accounts", sa.Column("portal_username_encrypted", sa.Text(), nullable=True))
    op.add_column("ai_provider_accounts", sa.Column("portal_password_encrypted", sa.Text(), nullable=True))
    op.alter_column("ai_provider_accounts", "credentials_encrypted", existing_type=sa.Text(), nullable=True)

    op.create_table(
        "ai_provider_api_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(32), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_provider_api_credentials_provider_account_id",
        "ai_provider_api_credentials", ["provider_account_id"],
    )
    op.create_index(
        "ix_ai_provider_api_credential_account_default",
        "ai_provider_api_credentials", ["provider_account_id", "is_default"],
    )

    bind = op.get_bind()
    accounts = bind.execute(sa.text(
        "SELECT id, provider, credentials_encrypted FROM ai_provider_accounts "
        "WHERE credentials_encrypted IS NOT NULL"
    )).mappings()
    now = datetime.now(timezone.utc)
    for account in accounts:
        bind.execute(
            sa.text(
                "INSERT INTO ai_provider_api_credentials "
                "(id, provider_account_id, name, credential_type, credentials_encrypted, "
                "is_active, is_default, created_at, updated_at) "
                "VALUES (:id, :account_id, :name, :credential_type, :credentials, "
                "true, true, :created_at, :updated_at)"
            ),
            {
                "id": uuid.uuid4(),
                "account_id": account["id"],
                "name": "迁移的默认凭据",
                "credential_type": "api_key" if account["provider"] == "deepseek" else "ak_sk",
                "credentials": account["credentials_encrypted"],
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE ai_provider_accounts a SET credentials_encrypted = c.credentials_encrypted "
        "FROM ai_provider_api_credentials c "
        "WHERE c.provider_account_id = a.id AND c.is_default = true"
    ))
    op.drop_index("ix_ai_provider_api_credential_account_default", table_name="ai_provider_api_credentials")
    op.drop_index("ix_ai_provider_api_credentials_provider_account_id", table_name="ai_provider_api_credentials")
    op.drop_table("ai_provider_api_credentials")
    op.drop_column("ai_provider_accounts", "portal_password_encrypted")
    op.drop_column("ai_provider_accounts", "portal_username_encrypted")
    op.alter_column("ai_provider_accounts", "credentials_encrypted", existing_type=sa.Text(), nullable=False)
