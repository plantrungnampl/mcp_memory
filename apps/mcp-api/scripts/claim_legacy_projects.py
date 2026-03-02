from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from viberecall_mcp.config import get_settings


async def run(owner_id: str, *, dry_run: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)

    async with engine.begin() as conn:
        if dry_run:
            result = await conn.execute(
                text(
                    """
                    select id, name, created_at
                    from projects
                    where owner_id is null
                    order by created_at desc, id desc
                    """
                )
            )
            rows = result.mappings().all()
            print(f"legacy_unowned_projects={len(rows)}")
            for row in rows:
                print(f"- {row['id']} | {row['name']} | {row['created_at']}")
            return

        result = await conn.execute(
            text(
                """
                update projects
                set owner_id = :owner_id
                where owner_id is null
                returning id, name, created_at
                """
            ),
            {"owner_id": owner_id},
        )
        rows = result.mappings().all()
        print(f"claimed_projects={len(rows)}")
        for row in rows:
            print(f"- {row['id']} | {row['name']} | {row['created_at']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Claim legacy unowned projects to a target owner.")
    parser.add_argument("--owner-id", required=True, help="Target owner_id for unowned projects")
    parser.add_argument("--dry-run", action="store_true", help="List affected rows without mutating data")
    args = parser.parse_args()

    asyncio.run(run(args.owner_id, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
