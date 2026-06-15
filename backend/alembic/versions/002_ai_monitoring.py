"""AI provider cost monitoring

Revision ID: 002
Revises: 001
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import date, datetime, timezone

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

provider = postgresql.ENUM("deepseek", "volcengine", name="aiprovider", create_type=False)
account_status = postgresql.ENUM("active", "inactive", "error", name="aiaccountstatus", create_type=False)
sync_status = postgresql.ENUM("never", "running", "success", "failed", name="aisyncstatus", create_type=False)
cost_source = postgresql.ENUM("provider", "calculated", name="aicostsource", create_type=False)
key_status = postgresql.ENUM("active", "disabled", name="aigatewaykeystatus", create_type=False)
request_status = postgresql.ENUM("success", "failed", "incomplete", name="airequeststatus", create_type=False)
alert_type = postgresql.ENUM("balance_low", "sync_failed", name="aialerttype", create_type=False)
alert_status = postgresql.ENUM("open", "acknowledged", name="aialerteventstatus", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (provider, account_status, sync_status, cost_source, key_status, request_status, alert_type, alert_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "ai_provider_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", provider, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("credentials_encrypted", sa.Text, nullable=False),
        sa.Column("provider_account_ref", sa.String(256)),
        sa.Column("base_url", sa.String(512)),
        sa.Column("status", account_status, nullable=False, server_default="active"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sync_status, nullable=False, server_default="never"),
        sa.Column("last_sync_error", sa.Text),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_provider_accounts_provider", "ai_provider_accounts", ["provider"])

    op.create_table(
        "ai_gateway_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(24), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", key_status, nullable=False, server_default="active"),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=False, server_default="60"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_gateway_keys_provider_account_id", "ai_gateway_keys", ["provider_account_id"])
    op.create_index("ix_ai_gateway_keys_key_prefix", "ai_gateway_keys", ["key_prefix"])

    op.create_table(
        "ai_gateway_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gateway_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_gateway_keys.id", ondelete="SET NULL")),
        sa.Column("provider_request_id", sa.String(256)),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("calculated_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("status", request_status, nullable=False),
        sa.Column("http_status", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("error_code", sa.String(128)),
        sa.Column("usage_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_gateway_requests_provider_account_id", "ai_gateway_requests", ["provider_account_id"])
    op.create_index("ix_ai_gateway_requests_model", "ai_gateway_requests", ["model"])
    op.create_index("ix_ai_gateway_requests_status", "ai_gateway_requests", ["status"])
    op.create_index("ix_ai_gateway_requests_usage_date", "ai_gateway_requests", ["usage_date"])
    op.create_index("ix_ai_gateway_request_account_date", "ai_gateway_requests", ["provider_account_id", "usage_date"])

    op.create_table(
        "ai_daily_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage_date", sa.Date, nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("request_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("provider_reported_cost", sa.Numeric(18, 8)),
        sa.Column("calculated_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("cost_source", cost_source, nullable=False, server_default="calculated"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_account_id", "usage_date", "model", name="uq_ai_daily_account_date_model"),
    )
    op.create_index("ix_ai_daily_usage_provider_account_id", "ai_daily_usage", ["provider_account_id"])
    op.create_index("ix_ai_daily_usage_usage_date", "ai_daily_usage", ["usage_date"])
    op.create_index("ix_ai_daily_usage_date_provider", "ai_daily_usage", ["usage_date", "provider_account_id"])

    op.create_table(
        "ai_balance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_balance", sa.Numeric(18, 8), nullable=False),
        sa.Column("credit_granted", sa.Numeric(18, 8)),
        sa.Column("credit_used", sa.Numeric(18, 8)),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
    )
    op.create_index("ix_ai_balance_snapshots_provider_account_id", "ai_balance_snapshots", ["provider_account_id"])
    op.create_index("ix_ai_balance_snapshots_snapshot_time", "ai_balance_snapshots", ["snapshot_time"])

    op.create_table(
        "ai_model_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", provider, nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("input_price", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("output_price", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("cached_input_price", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("reasoning_price", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("unit_tokens", sa.BigInteger, nullable=False, server_default="1000000"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model", "effective_from", name="uq_ai_price_provider_model_from"),
    )
    op.create_index("ix_ai_model_prices_provider", "ai_model_prices", ["provider"])
    op.create_index("ix_ai_model_prices_model", "ai_model_prices", ["model"])
    op.bulk_insert(
        sa.table(
            "ai_model_prices",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("provider", provider),
            sa.column("model", sa.String),
            sa.column("input_price", sa.Numeric),
            sa.column("output_price", sa.Numeric),
            sa.column("cached_input_price", sa.Numeric),
            sa.column("reasoning_price", sa.Numeric),
            sa.column("unit_tokens", sa.BigInteger),
            sa.column("currency", sa.String),
            sa.column("effective_from", sa.Date),
            sa.column("effective_to", sa.Date),
            sa.column("created_by_id", postgresql.UUID(as_uuid=True)),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": "0c086505-b552-463a-90cc-cafad3d1ec4f", "provider": "deepseek",
                "model": model, "input_price": input_price, "output_price": output_price,
                "cached_input_price": cached_price, "reasoning_price": 0,
                "unit_tokens": 1_000_000, "currency": "CNY",
                "effective_from": date(2026, 6, 15), "effective_to": None,
                "created_by_id": None, "created_at": datetime.now(timezone.utc),
            }
            for model, input_price, cached_price, output_price in [
                ("deepseek-v4-flash", 1, 0.02, 2),
            ]
        ] + [
            {
                "id": "1f488aa3-1500-4717-9f89-e3dfe4415188", "provider": "deepseek",
                "model": "deepseek-v4-pro", "input_price": 3, "output_price": 6,
                "cached_input_price": 0.025, "reasoning_price": 0,
                "unit_tokens": 1_000_000, "currency": "CNY",
                "effective_from": date(2026, 6, 15), "effective_to": None,
                "created_by_id": None, "created_at": datetime.now(timezone.utc),
            },
            {
                "id": "69c0d770-65bd-4374-8708-e515041c1176", "provider": "deepseek",
                "model": "deepseek-chat", "input_price": 1, "output_price": 2,
                "cached_input_price": 0.02, "reasoning_price": 0,
                "unit_tokens": 1_000_000, "currency": "CNY",
                "effective_from": date(2026, 6, 15), "effective_to": date(2026, 7, 24),
                "created_by_id": None, "created_at": datetime.now(timezone.utc),
            },
            {
                "id": "2154bdd7-59c3-47a8-a4ed-c2d580294738", "provider": "deepseek",
                "model": "deepseek-reasoner", "input_price": 1, "output_price": 2,
                "cached_input_price": 0.02, "reasoning_price": 0,
                "unit_tokens": 1_000_000, "currency": "CNY",
                "effective_from": date(2026, 6, 15), "effective_to": date(2026, 7, 24),
                "created_by_id": None, "created_at": datetime.now(timezone.utc),
            },
        ],
    )

    op.create_table(
        "ai_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sync_type", sa.String(32), nullable=False),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("records_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ai_sync_runs_provider_account_id", "ai_sync_runs", ["provider_account_id"])

    op.create_table(
        "ai_alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", alert_type, nullable=False),
        sa.Column("threshold_amount", sa.Numeric(18, 8)),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="2"),
        sa.Column("cooldown_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("notify_inapp", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_webhook", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("webhook_type", sa.String(32)),
        sa.Column("webhook_url_encrypted", sa.Text),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_account_id", "alert_type", name="uq_ai_alert_account_type"),
    )
    op.create_index("ix_ai_alert_rules_provider_account_id", "ai_alert_rules", ["provider_account_id"])

    op.create_table(
        "ai_alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_alert_rules.id", ondelete="SET NULL")),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_provider_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", alert_type, nullable=False),
        sa.Column("triggered_value", sa.Numeric(18, 8)),
        sa.Column("threshold_value", sa.Numeric(18, 8)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", alert_status, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_ai_alert_events_provider_account_id", "ai_alert_events", ["provider_account_id"])


def downgrade() -> None:
    for table in ("ai_alert_events", "ai_alert_rules", "ai_sync_runs", "ai_model_prices",
                  "ai_balance_snapshots", "ai_daily_usage", "ai_gateway_requests",
                  "ai_gateway_keys", "ai_provider_accounts"):
        op.drop_table(table)
    bind = op.get_bind()
    for enum in reversed((provider, account_status, sync_status, cost_source, key_status, request_status, alert_type, alert_status)):
        enum.drop(bind, checkfirst=True)
