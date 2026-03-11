# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs
"""Template registry with CRUD, search, and versioning."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import semver


@dataclass
class Template:
    """Template metadata and content."""
    name: str
    version: str
    author: str
    description: str
    price_rtc: int
    tags: List[str]
    content: str
    download_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemplateRegistry:
    """SQLite-backed template registry."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".shaprai" / "marketplace.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    author TEXT NOT NULL,
                    description TEXT,
                    price_rtc INTEGER DEFAULT 0,
                    tags TEXT,  -- JSON array
                    content TEXT NOT NULL,
                    download_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(name, version)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_author ON templates(author)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_tags ON templates(tags)
            """)

    def publish(self, template: Template) -> bool:
        """Publish a new template version. Returns False if version exists."""
        # Validate semver
        try:
            semver.VersionInfo.parse(template.version)
        except ValueError:
            raise ValueError(f"Invalid semver version: {template.version}")

        # Check for existing version
        if self.get(template.name, template.version):
            raise ValueError(f"Template {template.name}@{template.version} already exists")

        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO templates
                (name, version, author, description, price_rtc, tags, content, download_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.name,
                    template.version,
                    template.author,
                    template.description,
                    template.price_rtc,
                    json.dumps(template.tags),
                    template.content,
                    template.download_count,
                    now,
                    now,
                ),
            )
        return True

    def get(self, name: str, version: str) -> Optional[Template]:
        """Get a specific template version."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM templates WHERE name = ? AND version = ?",
                (name, version),
            ).fetchone()
            if row:
                return self._row_to_template(row)
            return None

    def get_latest(self, name: str) -> Optional[Template]:
        """Get the latest version of a template."""
        versions = self.list_versions(name)
        if not versions:
            return None
        # Sort by semver and get latest
        versions.sort(key=lambda v: semver.VersionInfo.parse(v), reverse=True)
        return self.get(name, versions[0])

    def list_versions(self, name: str) -> List[str]:
        """List all versions of a template."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT version FROM templates WHERE name = ? ORDER BY created_at DESC",
                (name,),
            ).fetchall()
            return [row[0] for row in rows]

    def search(
        self,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        query: Optional[str] = None,
        sort: str = "downloads",
        limit: int = 20,
    ) -> List[Template]:
        """Search templates by tag, author, or query."""
        sql = "SELECT * FROM templates WHERE 1=1"
        params = []

        if tag:
            sql += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        if author:
            sql += " AND author = ?"
            params.append(author)

        if query:
            sql += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        # Sort
        if sort == "downloads":
            sql += " ORDER BY download_count DESC"
        elif sort == "recent":
            sql += " ORDER BY created_at DESC"
        elif sort == "price":
            sql += " ORDER BY price_rtc ASC"

        sql += f" LIMIT {limit}"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_template(row) for row in rows]

    def increment_downloads(self, name: str, version: str) -> None:
        """Increment download count for a template."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE templates SET download_count = download_count + 1 WHERE name = ? AND version = ?",
                (name, version),
            )

    def list_by_author(self, author: str) -> List[Template]:
        """List all templates by an author."""
        return self.search(author=author, sort="recent")

    def delete(self, name: str, version: str) -> bool:
        """Delete a specific template version."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM templates WHERE name = ? AND version = ?",
                (name, version),
            )
            return cursor.rowcount > 0

    def _row_to_template(self, row: sqlite3.Row) -> Template:
        """Convert database row to Template object."""
        return Template(
            name=row["name"],
            version=row["version"],
            author=row["author"],
            description=row["description"] or "",
            price_rtc=row["price_rtc"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            content=row["content"],
            download_count=row["download_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
