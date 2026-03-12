"""Template Registry — CRUD, search, and versioning for marketplace templates."""

import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import re

logger = logging.getLogger("shaprai.marketplace.registry")


@dataclass
class Template:
    """A marketplace template."""
    id: str
    name: str
    description: str
    author: str
    version: str
    tags: List[str]
    price_rtc: float
    download_count: int
    created_at: str
    updated_at: str
    content: Optional[str] = None  # Full content (only when purchased)
    preview: Optional[str] = None  # Truncated preview


class TemplateRegistry:
    """SQLite-backed template registry.

    Manages template CRUD operations, search, and versioning.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize registry.

        Args:
            db_path: Path to SQLite database (default: ~/.shaprai/marketplace.db)
        """
        if db_path is None:
            db_path = Path.home() / ".shaprai" / "marketplace.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    author TEXT NOT NULL,
                    version TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    price_rtc REAL NOT NULL,
                    download_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    content TEXT,  -- Full template content
                    preview TEXT,  -- Truncated preview
                    UNIQUE(name, version)
                )
            """)

            # Index for search
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_search
                ON templates(name, description, tags)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_templates_author
                ON templates(author)
            """)

            conn.commit()

    def _generate_id(self, name: str, version: str) -> str:
        """Generate unique template ID."""
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower())
        return f"{safe_name}@{version}"

    def publish(
        self,
        name: str,
        description: str,
        author: str,
        version: str,
        tags: List[str],
        price_rtc: float,
        content: str,
        preview_length: int = 500
    ) -> Template:
        """Publish a new template.

        Args:
            name: Template name
            description: Template description
            author: Creator identifier
            version: Semver version (e.g., "1.2.3")
            tags: List of tags
            price_rtc: Price in RTC tokens
            content: Full template content
            preview_length: Characters to show in preview

        Returns:
            Published Template

        Raises:
            ValueError: If version already exists
        """
        template_id = self._generate_id(name, version)
        now = datetime.utcnow().isoformat()

        # Create preview (truncated content)
        preview = content[:preview_length]
        if len(content) > preview_length:
            preview += "\n... [Preview truncated. Purchase to view full template.]"

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO templates
                    (id, name, description, author, version, tags, price_rtc,
                     download_count, created_at, updated_at, content, preview)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    template_id, name, description, author, version,
                    json.dumps(tags), price_rtc, 0, now, now, content, preview
                ))
                conn.commit()

                logger.info(f"Published template: {template_id}")

                return Template(
                    id=template_id,
                    name=name,
                    description=description,
                    author=author,
                    version=version,
                    tags=tags,
                    price_rtc=price_rtc,
                    download_count=0,
                    created_at=now,
                    updated_at=now,
                    preview=preview
                )

            except sqlite3.IntegrityError:
                raise ValueError(
                    f"Template {name}@{version} already exists. "
                    "Use a new version to update."
                )

    def get(self, template_id: str, include_content: bool = False) -> Optional[Template]:
        """Get template by ID.

        Args:
            template_id: Template identifier
            include_content: Whether to include full content

        Returns:
            Template or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM templates WHERE id = ?",
                (template_id,)
            ).fetchone()

            if row is None:
                return None

            return self._row_to_template(row, include_content)

    def search(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "downloads",  # downloads, price, newest
        limit: int = 50
    ) -> List[Template]:
        """Search templates.

        Args:
            query: Text search in name/description
            tag: Filter by tag
            author: Filter by author
            min_price: Minimum price
            max_price: Maximum price
            sort_by: Sort field
            limit: Max results

        Returns:
            List of matching templates
        """
        conditions = []
        params = []

        if query:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        if author:
            conditions.append("author = ?")
            params.append(author)

        if min_price is not None:
            conditions.append("price_rtc >= ?")
            params.append(min_price)

        if max_price is not None:
            conditions.append("price_rtc <= ?")
            params.append(max_price)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Sort
        sort_column = {
            "downloads": "download_count DESC",
            "price": "price_rtc ASC",
            "newest": "created_at DESC",
            "oldest": "created_at ASC"
        }.get(sort_by, "download_count DESC")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT * FROM templates
                WHERE {where_clause}
                ORDER BY {sort_column}
                LIMIT ?
                """,
                (*params, limit)
            ).fetchall()

            return [self._row_to_template(row, include_content=False) for row in rows]

    def list_by_author(self, author: str) -> List[Template]:
        """List all templates by an author.

        Args:
            author: Author identifier

        Returns:
            List of templates
        """
        return self.search(author=author, sort_by="newest")

    def increment_downloads(self, template_id: str):
        """Increment download counter.

        Args:
            template_id: Template ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE templates
                SET download_count = download_count + 1
                WHERE id = ?
            """, (template_id,))
            conn.commit()

    def get_versions(self, name: str) -> List[Template]:
        """Get all versions of a template.

        Args:
            name: Template name

        Returns:
            List of versions, sorted newest first
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM templates
                WHERE name = ?
                ORDER BY created_at DESC
            """, (name,)).fetchall()

            return [self._row_to_template(row, include_content=False) for row in rows]

    def delete(self, template_id: str) -> bool:
        """Delete a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM templates WHERE id = ?",
                (template_id,)
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Deleted template: {template_id}")
                return True
            return False

    def _row_to_template(
        self,
        row: sqlite3.Row,
        include_content: bool
    ) -> Template:
        """Convert database row to Template."""
        return Template(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            author=row["author"],
            version=row["version"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            price_rtc=row["price_rtc"],
            download_count=row["download_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            content=row["content"] if include_content else None,
            preview=row["preview"]
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics.

        Returns:
            Dict with stats
        """
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM templates"
            ).fetchone()[0]

            total_downloads = conn.execute(
                "SELECT COALESCE(SUM(download_count), 0) FROM templates"
            ).fetchone()[0]

            avg_price = conn.execute(
                "SELECT COALESCE(AVG(price_rtc), 0) FROM templates"
            ).fetchone()[0]

            authors = conn.execute(
                "SELECT COUNT(DISTINCT author) FROM templates"
            ).fetchone()[0]

            return {
                "total_templates": total,
                "total_downloads": total_downloads,
                "average_price_rtc": round(avg_price, 4),
                "unique_authors": authors
            }