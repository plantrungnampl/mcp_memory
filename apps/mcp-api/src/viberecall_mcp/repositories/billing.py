from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


def _is_missing_billing_schema_error(error: Exception) -> bool:
    message = str(error).lower()
    has_relation_hint = any(
        marker in message
        for marker in ("does not exist", "undefined table", "no such table", "relation")
    )
    targets_billing_tables = any(
        table_name in message
        for table_name in ("billing_contacts", "billing_payment_methods", "billing_invoices")
    )
    return has_relation_hint and targets_billing_tables


async def get_billing_contact(
    session: AsyncSession,
    *,
    project_id: str,
) -> dict | None:
    try:
        result = await session.execute(
            text(
                """
                select project_id, email, tax_id
                from billing_contacts
                where project_id = :project_id
                limit 1
                """
            ),
            {"project_id": project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None
    except SQLAlchemyError as error:
        if _is_missing_billing_schema_error(error):
            return None
        raise


async def get_default_payment_method(
    session: AsyncSession,
    *,
    project_id: str,
) -> dict | None:
    try:
        result = await session.execute(
            text(
                """
                select
                  payment_method_id,
                  project_id,
                  brand,
                  last4,
                  exp_month,
                  exp_year,
                  is_default
                from billing_payment_methods
                where project_id = :project_id
                order by is_default desc, created_at desc
                limit 1
                """
            ),
            {"project_id": project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None
    except SQLAlchemyError as error:
        if _is_missing_billing_schema_error(error):
            return None
        raise


async def list_recent_invoices(
    session: AsyncSession,
    *,
    project_id: str,
    limit: int = 20,
) -> list[dict]:
    safe_limit = max(1, min(limit, 100))
    try:
        result = await session.execute(
            text(
                """
                select
                  invoice_id,
                  project_id,
                  invoice_date,
                  description,
                  amount_cents,
                  currency,
                  status,
                  pdf_url
                from billing_invoices
                where project_id = :project_id
                order by invoice_date desc, invoice_id desc
                limit :limit
                """
            ),
            {
                "project_id": project_id,
                "limit": safe_limit,
            },
        )
        return [dict(row) for row in result.mappings().all()]
    except SQLAlchemyError as error:
        if _is_missing_billing_schema_error(error):
            return []
        raise
