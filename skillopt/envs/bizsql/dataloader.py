"""BizSQL task dataloader.

Each split directory (``train/``, ``val/``, ``test/``) holds one JSON array of
items shaped::

    {"id": "bizsql-042", "question": "Total revenue from EU customers ...",
     "db_path": "data/bizsql/business.sqlite",
     "schema_ddl_ref": "data/bizsql/schema.sql",
     "difficulty": "medium",
     "gold_sql": "SELECT ...",      # kept for the article trace; NOT used for scoring
     "gold_result": [[12345.67]]}   # scoring compares against this result set

The default :class:`SplitDataLoader.load_split_items` (first ``*.json`` in the
split dir -> JSON array) already matches this layout, so this subclass only
names the loader and reuses the generic split logic.
"""
from __future__ import annotations

import json

from skillopt.datasets.base import SplitDataLoader


def _load_items(path: str) -> list[dict]:
    """Load items from a JSON array or JSONL file."""
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return []
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or list(data.values())
    except json.JSONDecodeError:
        pass
    items: list[dict] = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


class BizsqlDataLoader(SplitDataLoader):
    """Business Text-to-SQL dataloader (split_dir or ratio mode)."""

    def load_raw_items(self, data_path: str) -> list[dict]:
        return _load_items(data_path)
