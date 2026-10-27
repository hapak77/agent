"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("adapter", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.Enum(
            "active", "disabled", "error", "unavailable", name="sourcestatus"
        ), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "duplicate_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(128), nullable=False, unique=True),
        sa.Column("canonical_order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("author_id", sa.String(255), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_contact", sa.String(512), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(128), nullable=True),
        sa.Column("duplicate_group_id", sa.Integer(), sa.ForeignKey("duplicate_groups.id")),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Enum(
            "new", "processing", "analyzed", "rejected", "ready_for_outreach",
            "contacted", "archived", name="orderstatus"
        ), nullable=False),
        sa.Column("contact_status", sa.Enum(
            "not_contacted", "queued", "sent", "failed", "skipped",
            "manual_contact_required", "replied", "paused", name="contactstatus"
        ), nullable=False),
        sa.Column("categories", sa.JSON()),
        sa.Column("budget_amount", sa.Float()),
        sa.Column("budget_currency", sa.String(16)),
        sa.Column("budget_unknown", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deadline_text", sa.String(255)),
        sa.Column("requirements", sa.Text()),
        sa.Column("expected_result", sa.Text()),
        sa.Column("order_kind", sa.Enum(
            "real_order", "discussion", "advertisement", "spam",
            "free_test", "vacancy", "uncertain", name="orderkind"
        )),
        sa.Column("complexity", sa.Float()),
        sa.Column("feasibility", sa.Float()),
        sa.Column("risk_score", sa.Float()),
        sa.Column("priority_score", sa.Float()),
        sa.Column("rating_explanation", sa.Text()),
        sa.Column("risks", sa.JSON()),
        sa.Column("passed_prefilter", sa.Boolean()),
        sa.Column("prefilter_reason", sa.String(255)),
        sa.Column("llm_summary", sa.Text()),
        sa.Column("contact_message", sa.Text()),
        sa.Column("extra_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "external_id", name="uq_order_source_external"),
    )
    op.create_index("ix_orders_priority", "orders", ["priority_score"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_discovered", "orders", ["discovered_at"])
    op.create_index("ix_orders_content_hash", "orders", ["content_hash"])
    op.create_index("ix_orders_semantic_fingerprint", "orders", ["semantic_fingerprint"])

    # FK from duplicate_groups.canonical_order_id → orders (deferred)
    with op.batch_alter_table("duplicate_groups") as batch:
        batch.create_foreign_key(
            "fk_dup_canonical_order", "orders", ["canonical_order_id"], ["id"]
        )

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), unique=True, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("raw_response", sa.JSON()),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "contact_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum(
            "not_contacted", "queued", "sent", "failed", "skipped",
            "manual_contact_required", "replied", "paused", name="contactstatus",
            create_type=False,
        ), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_message_id", sa.String(128)),
        sa.Column("reply_text", sa.Text()),
        sa.Column("reply_at", sa.DateTime(timezone=True)),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contact_order_status", "contact_attempts", ["order_id", "status"])
    op.create_index(
        "ix_contact_order_recipient", "contact_attempts", ["order_id", "channel", "recipient"]
    )

    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("source_key", sa.String(64)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "app_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value_json", sa.JSON()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("app_state")
    op.drop_table("error_logs")
    op.drop_table("contact_attempts")
    op.drop_table("analysis_results")
    with op.batch_alter_table("duplicate_groups") as batch:
        batch.drop_constraint("fk_dup_canonical_order", type_="foreignkey")
    op.drop_table("orders")
    op.drop_table("duplicate_groups")
    op.drop_table("sources")
