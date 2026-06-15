"""Add Kimi, Alibaba, Huawei model prices

Revision ID: 004
Revises: 003
Create Date: 2026-06-15
"""
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Add new enum values by creating a new enum and swapping
    provider_enum = postgresql.ENUM(
        "deepseek", "volcengine", "kimi", "alibaba", "huawei",
        name="aiprovider", create_type=False,
    )
    provider_enum.create(bind, checkfirst=True)
    op.execute("ALTER TYPE aiprovider RENAME TO aiprovider_old")
    provider_enum.create(bind, checkfirst=False)
    for table in ("ai_provider_accounts", "ai_model_prices"):
        op.execute(f"""
            ALTER TABLE {table} ALTER COLUMN provider TYPE aiprovider
            USING provider::text::aiprovider
        """)
    op.execute("DROP TYPE aiprovider_old")

    now = datetime.now(timezone.utc)
    prices_table = sa.table(
        "ai_model_prices",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("provider", provider_enum),
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
    )
    # Kimi models
    kimi_models = [
        ("kimi-moonshot-v1-auto", 0.004, 0.012, 0.001, 0),
        ("kimi-k2-0905-preview", 0.004, 0.012, 0.001, 0),
        ("kimi-k2-thinking", 0.004, 0.012, 0.001, 0.016),
    ]
    # Alibaba models
    alibaba_models = [
        ("qwen3-235b-a22b", 0.008, 0.02, 0.001, 0),
        ("qwen-plus", 0.002, 0.006, 0.001, 0),
        ("qwen-turbo", 0.001, 0.002, 0.001, 0),
        ("qwen-max", 0.02, 0.06, 0.001, 0),
    ]
    # Huawei models (盘古)
    huawei_models = [
        ("pangu-nlp-large", 0.004, 0.012, 0.001, 0),
        ("pangu-nlp-chat", 0.004, 0.012, 0.001, 0),
    ]
    rows = []
    for model, inp, out, cache, reasoning in kimi_models:
        rows.append(dict(
            id=None, provider="kimi", model=model,
            input_price=inp, output_price=out, cached_input_price=cache,
            reasoning_price=reasoning, unit_tokens=1_000_000, currency="CNY",
            effective_from=date(2026, 6, 15), effective_to=None,
            created_by_id=None, created_at=now,
        ))
    for model, inp, out, cache, reasoning in alibaba_models:
        rows.append(dict(
            id=None, provider="alibaba", model=model,
            input_price=inp, output_price=out, cached_input_price=cache,
            reasoning_price=reasoning, unit_tokens=1_000_000, currency="CNY",
            effective_from=date(2026, 6, 15), effective_to=None,
            created_by_id=None, created_at=now,
        ))
    for model, inp, out, cache, reasoning in huawei_models:
        rows.append(dict(
            id=None, provider="huawei", model=model,
            input_price=inp, output_price=out, cached_input_price=cache,
            reasoning_price=reasoning, unit_tokens=1_000_000, currency="CNY",
            effective_from=date(2026, 6, 15), effective_to=None,
            created_by_id=None, created_at=now,
        ))
    op.bulk_insert(prices_table, rows)


def downgrade() -> None:
    op.execute("DELETE FROM ai_model_prices WHERE provider IN ('kimi', 'alibaba', 'huawei')")
