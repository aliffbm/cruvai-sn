"""CLI entrypoint: `python -m app.ingestion.toolkit_ingest --root ~/.claude`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.toolkit_ingest.runner import run_ingestion
from app.services.storage.factory import get_storage_backend


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingestion.toolkit_ingest",
        description="Ingest the ~/.claude/ toolkit into Cruvai's control plane.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(settings.toolkit_root or "~/.claude"),
        help="Path to the toolkit root (default: $TOOLKIT_ROOT or ~/.claude)",
    )
    parser.add_argument(
        "--org-id",
        type=str,
        default=None,
        help="Organization UUID to scope ingestion to. Omit for system/OOB (org_id=NULL).",
    )
    parser.add_argument(
        "--triggered-by",
        type=str,
        default=None,
        help="User UUID who triggered this run (for audit trail).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and report stats without writing to DB.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = args.root.expanduser().resolve()

    org_id = uuid.UUID(args.org_id) if args.org_id else None
    triggered_by_id = uuid.UUID(args.triggered_by) if args.triggered_by else None

    storage = get_storage_backend()

    engine = create_engine(settings.database_url_sync, future=True)
    with Session(engine, expire_on_commit=False) as db:
        stats = run_ingestion(
            db,
            toolkit_root=root,
            storage=storage,
            organization_id=org_id,
            triggered_by_id=triggered_by_id,
            dry_run=args.dry_run,
        )

    print(json.dumps(stats.as_dict(), indent=2, default=str))
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
