"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(256), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.Enum("admin", "operator", "viewer", name="userrole"), nullable=False, server_default="viewer"),
        sa.Column("status", sa.Enum("active", "inactive", name="userstatus"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("account_type", sa.Enum("cloud", "subscription", "prepaid", "other", name="accounttype"), nullable=False, server_default="other"),
        sa.Column("status", sa.Enum("active", "inactive", "archived", name="accountstatus"), nullable=False, server_default="active"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.String(512), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_status", "accounts", ["status"])
    op.create_index("ix_accounts_status_deleted", "accounts", ["status", "deleted_at"])

    op.create_table(
        "fee_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_type", sa.Enum("recharge", "consume", "adjustment", "refund", name="transactiontype"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 4), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=True, unique=True),
        sa.Column("transaction_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_fee_transactions_account_id", "fee_transactions", ["account_id"])
    op.create_index("ix_fee_txn_account_time", "fee_transactions", ["account_id", "transaction_time"])
    op.create_index("ix_fee_txn_category_time", "fee_transactions", ["category", "transaction_time"])

    op.create_table(
        "alert_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", sa.Enum("balance_low", "recharge_due", name="alerttype"), nullable=False),
        sa.Column("threshold_amount", sa.Numeric(14, 4), nullable=True),
        sa.Column("recharge_cycle_days", sa.Integer, nullable=True),
        sa.Column("last_recharge_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("notify_inapp", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_webhook", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("webhook_type", sa.String(32), nullable=True),
        sa.Column("webhook_url_encrypted", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "alert_type", name="uq_alert_config_account_type"),
    )
    op.create_index("ix_alert_configs_account_id", "alert_configs", ["account_id"])

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", sa.Enum("balance_low", "recharge_due", name="alerttype"), nullable=False),
        sa.Column("triggered_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("threshold_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("status", sa.Enum("pending", "sent", "failed", "acknowledged", name="alerteventstatus"), nullable=False, server_default="pending"),
        sa.Column("inapp_status", sa.Enum("pending", "sent", "failed", "skipped", name="channelstatus"), nullable=False, server_default="pending"),
        sa.Column("webhook_status", sa.Enum("pending", "sent", "failed", "skipped", name="channelstatus"), nullable=False, server_default="skipped"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_alert_events_account_id", "alert_events", ["account_id"])
    op.create_index("ix_alert_events_status_created", "alert_events", ["status", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])

    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("budget_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "year", "month", name="uq_budget_account_year_month"),
    )
    op.create_index("ix_budgets_account_id", "budgets", ["account_id"])


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_table("notifications")
    op.drop_table("alert_events")
    op.drop_table("alert_configs")
    op.drop_table("fee_transactions")
    op.drop_table("accounts")
    op.drop_table("users")
    for enum_name in ("userrole", "userstatus", "accounttype", "accountstatus",
                      "transactiontype", "alerttype", "alerteventstatus", "channelstatus"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
