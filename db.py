import aiosqlite
import json

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id TEXT PRIMARY KEY,
                guild_id  TEXT NOT NULL,
                channel_id TEXT NOT NULL DEFAULT '',
                title     TEXT NOT NULL DEFAULT 'Reaction Roles',
                description TEXT NOT NULL DEFAULT '',
                color     INTEGER NOT NULL DEFAULT 2830407,
                roles     TEXT NOT NULL DEFAULT '[]',
                is_draft  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS stickies (
                channel_id      TEXT PRIMARY KEY,
                guild_id        TEXT NOT NULL,
                content         TEXT NOT NULL,
                last_message_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS autothread (
                channel_id TEXT PRIMARY KEY,
                guild_id   TEXT NOT NULL
            );

        """)
        await db.commit()


# ── Reaction Roles ─────────────────────────────────────────

async def get_all_panels():
    """Return all non-draft panels (for restoring persistent views)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reaction_roles WHERE is_draft = 0"
        )
        rows = await cursor.fetchall()
        return {row["message_id"]: dict(row) for row in rows}


async def get_drafts(guild_id: str):
    """Return all draft panels for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reaction_roles WHERE guild_id = ? AND is_draft = 1",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        return {row["message_id"]: dict(row) for row in rows}


async def get_panel(message_id: str):
    """Return a single panel or draft by message_id, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reaction_roles WHERE message_id = ?", (message_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_panel(message_id: str, guild_id: str, **kwargs):
    """Insert or replace a panel/draft row.

    Known kwargs: channel_id, title, description, color, roles (list), is_draft (bool)
    """
    row = {"message_id": message_id, "guild_id": guild_id}
    row.setdefault("channel_id", kwargs.get("channel_id", ""))
    row.setdefault("title", kwargs.get("title", "Reaction Roles"))
    row.setdefault("description", kwargs.get("description", ""))
    row.setdefault("color", kwargs.get("color", 0x2b2d31))
    row.setdefault("roles", json.dumps(kwargs.get("roles", kwargs.get("role_ids", []))))
    row.setdefault("is_draft", 1 if kwargs.get("is_draft", True) else 0)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reaction_roles
               (message_id, guild_id, channel_id, title, description, color, roles, is_draft)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(message_id) DO UPDATE SET
               guild_id=excluded.guild_id, channel_id=excluded.channel_id,
               title=excluded.title, description=excluded.description,
               color=excluded.color, roles=excluded.roles, is_draft=excluded.is_draft""",
            (message_id, guild_id, row["channel_id"], row["title"],
             row["description"], row["color"], row["roles"], row["is_draft"]),
        )
        await db.commit()


async def delete_panel(message_id: str):
    """Delete a panel or draft by message_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ?", (message_id,)
        )
        await db.commit()


# ── Stickies ───────────────────────────────────────────────

async def get_all_stickies():
    """Return all sticky entries keyed by channel_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM stickies")
        rows = await cursor.fetchall()
        return {row["channel_id"]: dict(row) for row in rows}


async def get_sticky(channel_id: str):
    """Return a single sticky row or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM stickies WHERE channel_id = ?", (channel_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_sticky(channel_id: str, guild_id: str, content: str, last_message_id: str):
    """Insert or update a sticky entry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO stickies (channel_id, guild_id, content, last_message_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(channel_id) DO UPDATE SET
               guild_id=excluded.guild_id, content=excluded.content,
               last_message_id=excluded.last_message_id""",
            (channel_id, guild_id, content, last_message_id),
        )
        await db.commit()


async def delete_sticky(channel_id: str):
    """Remove a sticky entry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM stickies WHERE channel_id = ?", (channel_id,)
        )
        await db.commit()


# ── AutoThread ─────────────────────────────────────────────

async def get_all_autothread():
    """Return all autothread entries keyed by channel_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM autothread")
        rows = await cursor.fetchall()
        return {row["channel_id"]: dict(row) for row in rows}


async def get_autothread(channel_id: str):
    """Return a single autothread row or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM autothread WHERE channel_id = ?", (channel_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_autothread(channel_id: str, guild_id: str):
    """Enable autothread for a channel."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO autothread (channel_id, guild_id) VALUES (?, ?)",
            (channel_id, guild_id),
        )
        await db.commit()


async def delete_autothread(channel_id: str):
    """Disable autothread for a channel."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM autothread WHERE channel_id = ?", (channel_id,)
        )
        await db.commit()

