"""Add Zhipu and SiliconFlow providers

Revision ID: 005
Revises: 004
Create Date: 2026-06-15
"""
import uuid as _uuid
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _make_rows():
    now = datetime.now(timezone.utc)
    models = [
        ("zhipu", "glm-4.5-flash", 0.5, 2, 0.1, 0),
        ("zhipu", "glm-4.5-air", 1, 2, 0.1, 0),
        ("zhipu", "glm-4-plus", 10, 10, 0.1, 0),
        ("siliconflow", "Qwen/Qwen3-235B-A22B", 4, 16, 0, 0),
        ("siliconflow", "Pro/deepseek-ai/DeepSeek-V3", 2, 8, 0, 0),
        ("siliconflow", "deepseek-ai/DeepSeek-R1", 4, 16, 0, 8),
    ]
    rows = []
    for provider, model, inp, out, cache, reasoning in models:
        rows.append({
            "id": _uuid.uuid4(),
            "provider": provider,
            "model": model,
            "input_price": inp / 1000.0,
            "output_price": out / 1000.0,
            "cached_input_price": cache / 1000.0,
            "reasoning_price": reasoning / 1000.0,
            "unit_tokens": 1_000_000,
            "currency": "CNY",
            "effective_from": date(2026, 6, 15),
            "effective_to": None,
            "created_by_id": None,
            "created_at": now,
        })
    return rows


def upgrade() -> None:
    bind = op.get_bind()
    provider_enum = postgresql.ENUM(
        "deepseek", "volcengine", "kimi", "alibaba", "huawei",
        "zhipu", "siliconflow",
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
    op.bulk_insert(prices_table, _make_rows())


def downgrade() -> None:
    op.execute("DELETE FROM ai_model_prices WHERE provider IN ('zhipu', 'siliconflow')")
