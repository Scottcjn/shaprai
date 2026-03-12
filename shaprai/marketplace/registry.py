# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Template registry for the marketplace.

Provides SQLite-backed storage for template listings with:
- Semver versioning
- Search and filtering
- Purchase tracking
- Download counting
- Preview generation (truncated)
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path.home() / ".shaprai" / "marketplace.db"


@dataclass
class TemplateVersion:
    """Represents a specific version of a template."""
    name: str
    version: str
    author: str
    description: str
    config: Dict[str, Any]
    price_rtc: float
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    download_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TemplateListing:
    """Represents a template listing with all versions."""
    name: str
    author: str
    latest_version: str
    versions: List[str] = field(default_factory=list)
    total_downloads: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Purchase:
    """Represents a template purchase record."""
    id: str
    template_name: str
    template_version: str
    buyer_wallet: str
    price_rtc: float
    creator_rtc: float
    protocol_rtc: float
    relay_rtc: float
    relay_node: Optional[str]
    purchased_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class MarketplaceRegistry:
    """SQLite-backed template registry for the marketplace."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS templates (
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    author TEXT NOT NULL,
                    description TEXT NOT NULL,
                    config TEXT NOT NULL,
                    price_rtc REAL NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    download_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (name, version)
                );
                CREATE INDEX IF NOT EXISTS idx_templates_author ON templates(author);
                CREATE INDEX IF NOT EXISTS idx_templates_created ON templates(created_at);
                CREATE TABLE IF NOT EXISTS purchases (
                    id TEXT PRIMARY KEY,
                    template_name TEXT NOT NULL,
                    template_version TEXT NOT NULL,
                    buyer_wallet TEXT NOT NULL,
                    price_rtc REAL NOT NULL,
                    creator_rtc REAL NOT NULL,
                    protocol_rtc REAL NOT NULL,
                    relay_rtc REAL NOT NULL,
                    relay_node TEXT,
                    purchased_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_purchases_buyer ON purchases(buyer_wallet);
            """)
            conn.commit()

    def publish(self, template: Dict[str, Any], author: str, price_rtc: float = 0) -> TemplateVersion:
        from shaprai.marketplace.validator import TemplateValidator
        validator = TemplateValidator()
        result = validator.validate(template)
        if not result.valid:
            raise ValueError(f"Template validation failed: {result.errors}")

        name = template["name"]
        version = template["version"]

        if self.exists(name, version):
            raise ValueError(f"Template '{name}@{version}' already exists.")

        template_version = TemplateVersion(
            name=name, version=version, author=author,
            description=template.get("description", ""),
            config=template, price_rtc=price_rtc,
            tags=template.get("tags", []),
            created_at=time.time(), download_count=0,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO templates (name, version, author, description, config, price_rtc, tags, created_at, download_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (template_version.name, template_version.version, template_version.author,
                 template_version.description, json.dumps(template_version.config),
                 template_version.price_rtc, json.dumps(template_version.tags),
                 template_version.created_at, template_version.download_count),
            )
            conn.commit()

        logger.info("Published template: %s@%s by %s", name, version, author)
        return template_version

    def get(self, template_ref: str) -> Optional[TemplateVersion]:
        if "@" in template_ref:
            name, version = template_ref.split("@", 1)
        else:
            listing = self.get_listing(template_ref)
            if not listing:
                return None
            name, version = template_ref, listing.latest_version

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM templates WHERE name = ? AND version = ?", (name, version))
            row = cursor.fetchone()
            return self._row_to_template_version(row) if row else None

    def get_listing(self, name: str) -> Optional[TemplateListing]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM templates WHERE name = ? ORDER BY created_at DESC", (name,))
            rows = cursor.fetchall()
            if not rows:
                return None

            versions, all_tags, total_downloads = [], set(), 0
            for i, row in enumerate(rows):
                if i == 0:
                    latest_version, author = row["version"], row["author"]
                versions.append(row["version"])
                total_downloads += row["download_count"]
                for tag in json.loads(row["tags"]):
                    all_tags.add(tag)

            return TemplateListing(name=name, author=author, latest_version=latest_version,
                                   versions=versions, total_downloads=total_downloads, tags=list(all_tags))

    def delete(self, name: str, version: Optional[str] = None) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            if version:
                cursor = conn.execute("DELETE FROM templates WHERE name = ? AND version = ?", (name, version))
            else:
                cursor = conn.execute("DELETE FROM templates WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def exists(self, name: str, version: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM templates WHERE name = ? AND version = ?", (name, version))
            return cursor.fetchone() is not None

    def search(self, query: Optional[str] = None, tag: Optional[str] = None,
               author: Optional[str] = None, sort: str = "downloads",
               limit: int = 50, offset: int = 0) -> List[TemplateListing]:
        conditions, params = [], []
        if query:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if author:
            conditions.append("author = ?")
            params.append(author)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sort_map = {"downloads": "total_downloads DESC", "created": "created_at DESC", "name": "name ASC", "price": "price_rtc ASC"}
        order_by = sort_map.get(sort, "total_downloads DESC")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query_sql = f"""
                SELECT name, author, MAX(created_at) as latest_created,
                       GROUP_CONCAT(version, ',') as versions,
                       SUM(download_count) as total_downloads,
                       GROUP_CONCAT(tags, '|||') as all_tags
                FROM templates WHERE {where_clause}
                GROUP BY name, author ORDER BY {order_by} LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor = conn.execute(query_sql, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                versions = row["versions"].split(",") if row["versions"] else []
                tags = set()
                for tag_str in (row["all_tags"] or "").split("|||"):
                    for t in json.loads(tag_str):
                        tags.add(t)
                results.append(TemplateListing(
                    name=row["name"], author=row["author"],
                    latest_version=versions[0] if versions else "",
                    versions=versions, total_downloads=row["total_downloads"] or 0,
                    tags=list(tags),
                ))
            return results

    def list_templates(self, author: Optional[str] = None, limit: int = 100) -> List[TemplateListing]:
        return self.search(author=author, limit=limit)

    def buy(self, template_ref: str, buyer_wallet: str, relay_node: Optional[str] = None) -> Tuple[Purchase, TemplateVersion]:
        from shaprai.marketplace.pricing import calculate_revenue_split
        import uuid

        template = self.get(template_ref)
        if not template:
            raise ValueError(f"Template not found: {template_ref}")

        existing = self._get_purchase(buyer_wallet, template.name, template.version)
        if existing and template.price_rtc > 0:
            raise ValueError(f"Already purchased: {template.name}@{template.version}")

        split = calculate_revenue_split(template.price_rtc, creator_wallet=template.author, relay_node=relay_node)
        purchase = Purchase(
            id=str(uuid.uuid4()), template_name=template.name, template_version=template.version,
            buyer_wallet=buyer_wallet, price_rtc=split.total_rtc,
            creator_rtc=split.creator_rtc, protocol_rtc=split.protocol_rtc,
            relay_rtc=split.relay_rtc, relay_node=relay_node,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO purchases (id, template_name, template_version, buyer_wallet, price_rtc, creator_rtc, protocol_rtc, relay_rtc, relay_node, purchased_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (purchase.id, purchase.template_name, purchase.template_version, purchase.buyer_wallet,
                 purchase.price_rtc, purchase.creator_rtc, purchase.protocol_rtc, purchase.relay_rtc,
                 purchase.relay_node, purchase.purchased_at),
            )
            conn.execute("UPDATE templates SET download_count = download_count + 1 WHERE name = ? AND version = ?",
                         (template.name, template.version))
            conn.commit()

        logger.info("Template purchased: %s@%s by %s", template.name, template.version, buyer_wallet)
        template.download_count += 1
        return purchase, template

    def _get_purchase(self, buyer_wallet: str, template_name: str, template_version: str) -> Optional[Purchase]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM purchases WHERE buyer_wallet = ? AND template_name = ? AND template_version = ?",
                (buyer_wallet, template_name, template_version),
            )
            row = cursor.fetchone()
            if row:
                return Purchase(id=row["id"], template_name=row["template_name"],
                               template_version=row["template_version"], buyer_wallet=row["buyer_wallet"],
                               price_rtc=row["price_rtc"], creator_rtc=row["creator_rtc"],
                               protocol_rtc=row["protocol_rtc"], relay_rtc=row["relay_rtc"],
                               relay_node=row["relay_node"], purchased_at=row["purchased_at"])
            return None

    def get_purchases(self, buyer_wallet: str) -> List[Purchase]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM purchases WHERE buyer_wallet = ? ORDER BY purchased_at DESC", (buyer_wallet,))
            return [Purchase(id=r["id"], template_name=r["template_name"], template_version=r["template_version"],
                            buyer_wallet=r["buyer_wallet"], price_rtc=r["price_rtc"], creator_rtc=r["creator_rtc"],
                            protocol_rtc=r["protocol_rtc"], relay_rtc=r["relay_rtc"], relay_node=r["relay_node"],
                            purchased_at=r["purchased_at"]) for r in cursor.fetchall()]

    def preview(self, template_ref: str) -> Optional[Dict[str, Any]]:
        template = self.get(template_ref)
        if not template:
            return None

        config_preview = {}
        for key in ["name", "version", "model", "personality", "capabilities", "platforms"]:
            if key in template.config:
                value = template.config[key]
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                elif isinstance(value, dict):
                    value = {k: "..." for k in value.keys()}
                config_preview[key] = value

        return {
            "name": template.name, "version": template.version, "author": template.author,
            "description": template.description, "price_rtc": template.price_rtc,
            "tags": template.tags, "download_count": template.download_count,
            "config_preview": config_preview, "full_config_requires_purchase": template.price_rtc > 0,
        }

    def _row_to_template_version(self, row: sqlite3.Row) -> TemplateVersion:
        return TemplateVersion(
            name=row["name"], version=row["version"], author=row["author"],
            description=row["description"], config=json.loads(row["config"]),
            price_rtc=row["price_rtc"], tags=json.loads(row["tags"]),
            created_at=row["created_at"], download_count=row["download_count"],
        )