"""One-shot seeding: ChromaDB knowledge base + synthetic evaluation data.

Usage:
    python scripts/seed.py [--rows 200] [--skip-synthetic] [--skip-rag]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-synthetic", action="store_true")
    parser.add_argument("--skip-rag", action="store_true")
    args = parser.parse_args()

    if not args.skip_rag:
        from app.rag.ingest import ingest

        count = ingest()
        print(f"[rag] Ingested {count} knowledge chunks into ChromaDB.")

    if not args.skip_synthetic:
        from app.eval.synthetic import seed_database

        rows = seed_database(rows=args.rows, seed=args.seed)
        print(f"[synthetic] Seeded {rows} synthetic students into the database.")

    print("Done.")


if __name__ == "__main__":
    main()
