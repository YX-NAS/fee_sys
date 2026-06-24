"""Add severity to alert configs/events and align AI alert events with fee alert events.

Revision ID: 006
Revises: 005
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── alertseverity enum (shared by fee + AI) ──────────────────────────────
    severity_enum = postgresql.ENUM(
        "info", "warning", "critical", name="alertseverity", create_type=False,
    )
    severity_enum.create(bind, checkfirst=True)

    # alert_configs.severity
    op.add_column(
        "alert_configs",
        sa.Column("severity", sa.Enum(name="alertseverity"), nullable=True),
    )
    op.execute(
        "UPDATE alert_configs SET severity = CASE "
        "WHEN alert_type = 'balance_low' THEN 'critical' "
        "WHEN alert_type = 'recharge_due' THEN 'warning' "
        "ELSE 'warning' END"
    )
    op.alter_column("alert_configs", "severity", existing_type=sa.Enum(name="alertseverity"),
                    nullable=False, server_default="warning")

    # alert_events.severity
    op.add_column(
        "alert_events",
        sa.Column("severity", sa.Enum(name="alertseverity"), nullable=True),
    )
    op.execute(
        "UPDATE alert_events SET severity = CASE "
        "WHEN alert_type = 'balance_low' THEN 'critical' "
        "WHEN alert_type = 'recharge_due' THEN 'warning' "
        "ELSE 'warning' END"
    )
    op.alter_column("alert_events", "severity", existing_type=sa.Enum(name="alertseverity"),
                    nullable=False, server_default="warning")

    # ── ai_alert_rules.severity ──────────────────────────────────────────────
    op.add_column(
        "ai_alert_rules",
        sa.Column("severity", sa.Enum(name="alertseverity"), nullable=True),
    )
    op.execute(
        "UPDATE ai_alert_rules SET severity = CASE "
        "WHEN alert_type = 'balance_low' THEN 'critical' "
        "WHEN alert_type = 'sync_failed' THEN 'critical' "
        "WHEN alert_type = 'cost_spike' THEN 'warning' "
        "WHEN alert_type = 'no_usage' THEN 'info' "
        "ELSE 'warning' END"
    )
    op.alter_column("ai_alert_rules", "severity", existing_type=sa.Enum(name="alertseverity"),
                    nullable=False, server_default="warning")

    # ── ai_alert_events: align with alert_events ─────────────────────────────
    # severity
    op.add_column(
        "ai_alert_events",
        sa.Column("severity", sa.Enum(name="alertseverity"), nullable=True),
    )
    op.execute(
        "UPDATE ai_alert_events SET severity = CASE "
        "WHEN alert_type = 'balance_low' THEN 'critical' "
        "WHEN alert_type = 'sync_failed' THEN 'critical' "
        "WHEN alert_type = 'cost_spike' THEN 'warning' "
        "WHEN alert_type = 'no_usage' THEN 'info' "
        "ELSE 'warning' END"
    )
    op.alter_column("ai_alert_events", "severity", existing_type=sa.Enum(name="alertseverity"),
                    nullable=False, server_default="warning")

    # per-channel status + retry fields
    channel_enum = postgresql.ENUM(
        "pending", "sent", "failed", "skipped", name="channelstatus", create_type=False,
    )
    channel_enum.create(bind, checkfirst=True)

    op.add_column("ai_alert_events", sa.Column("inapp_status", sa.Enum(name="channelstatus"),
                                               nullable=True, server_default="pending"))
    op.add_column("ai_alert_events", sa.Column("webhook_status", sa.Enum(name="channelstatus"),
                                               nullable=True, server_default="skipped"))
    op.add_column("ai_alert_events", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_alert_events", sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill per-channel status from the old open/acknowledged status
    op.execute(
        "UPDATE ai_alert_events SET "
        "inapp_status = CASE WHEN status = 'acknowledged' THEN 'sent' ELSE 'sent' END, "
        "webhook_status = 'skipped' "
        "WHERE inapp_status IS NULL"
    )
    op.alter_column("ai_alert_events", "inapp_status", existing_type=sa.Enum(name="channelstatus"),
                    nullable=False, server_default="pending")
    op.alter_column("ai_alert_events", "webhook_status", existing_type=sa.Enum(name="channelstatus"),
                    nullable=False, server_default="skipped")

    # Migrate status enum: open/acknowledged -> alerteventstatus (pending/sent/failed/acknowledged)
    # Reuse the existing alerteventstatus type from alert_events.
    op.execute(
        "ALTER TABLE ai_alert_events ALTER COLUMN status TYPE alerteventstatus "
        "USING CASE status::text "
        "WHEN 'open' THEN 'sent'::text::alerteventstatus "
        "WHEN 'acknowledged' THEN 'acknowledged'::text::alerteventstatus "
        "ELSE 'sent'::text::alerteventstatus END"
    )
    op.alter_column("ai_alert_events", "status",
                    existing_type=postgresql.ENUM(name="alerteventstatus"),
                    nullable=False, server_default="pending")

    # Drop the now-unused aialerteventstatus enum
    op.execute("DROP TYPE IF EXISTS aialerteventstatus")

    op.create_index("ix_ai_alert_events_status_created", "ai_alert_events", ["status", "created_at"])


def downgrade() -> None:
    # Recreate aialerteventstatus and revert status
    aialert_enum = postgresql.ENUM("open", "acknowledged", name="aialerteventstatus", create_type=False)
    aialert_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE ai_alert_events ALTER COLUMN status TYPE aialerteventstatus "
        "USING CASE status::text "
        "WHEN 'acknowledged' THEN 'acknowledged'::text::aialerteventstatus "
        "ELSE 'open'::text::aialerteventstatus END"
    )

    op.drop_index("ix_ai_alert_events_status_created", table_name="ai_alert_events")
    op.drop_column("ai_alert_events", "last_retry_at")
    op.drop_column("ai_alert_events", "retry_count")
    op.drop_column("ai_alert_events", "webhook_status")
    op.drop_column("ai_alert_events", "inapp_status")
    op.drop_column("ai_alert_events", "severity")
    op.drop_column("ai_alert_rules", "severity")
    op.drop_column("alert_events", "severity")
    op.drop_column("alert_configs", "severity")
