import aiosqlite
import json
import os

DB_PATH = os.getenv('DB_PATH', './data/titan.db')

class Database:
    def __init__(self):
        self.path = DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id    INTEGER PRIMARY KEY,
                    prefix      TEXT    DEFAULT '!',
                    log_channel INTEGER,
                    transcript_channel INTEGER,
                    ticket_category INTEGER,
                    closed_category INTEGER,
                    admin_roles TEXT DEFAULT '[]',
                    mod_roles   TEXT DEFAULT '[]',
                    staff_roles TEXT DEFAULT '[]',
                    dealer_roles TEXT DEFAULT '[]',
                    ticket_counter INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS panels (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id    INTEGER NOT NULL,
                    channel_id  INTEGER NOT NULL,
                    message_id  INTEGER NOT NULL,
                    title       TEXT,
                    description TEXT,
                    color       INTEGER DEFAULT 3447003,
                    footer      TEXT,
                    thumbnail   TEXT,
                    categories  TEXT DEFAULT '[]',
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id        INTEGER NOT NULL,
                    channel_id      INTEGER NOT NULL,
                    user_id         INTEGER NOT NULL,
                    category        TEXT,
                    status          TEXT DEFAULT 'open',
                    ticket_number   INTEGER,
                    claimed_by      INTEGER,
                    opened_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at       TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id   INTEGER NOT NULL,
                    author_id   INTEGER NOT NULL,
                    author_name TEXT,
                    content     TEXT,
                    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
                );
            ''')
            await db.commit()

    # ── Guild Config ──────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM guild_config WHERE guild_id = ?', (guild_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    await db.execute(
                        'INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)', (guild_id,)
                    )
                    await db.commit()
                    return {
                        'guild_id': guild_id, 'prefix': '!',
                        'log_channel': None, 'transcript_channel': None,
                        'ticket_category': None, 'closed_category': None,
                        'admin_roles': [], 'mod_roles': [], 'staff_roles': [], 'dealer_roles': [],
                        'ticket_counter': 0
                    }
                d = dict(row)
                for key in ['admin_roles', 'mod_roles', 'staff_roles', 'dealer_roles']:
                    d[key] = json.loads(d[key] or '[]')
                return d

    async def set_config(self, guild_id: int, **kwargs):
        config = await self.get_config(guild_id)
        config.update(kwargs)
        for key in ['admin_roles', 'mod_roles', 'staff_roles', 'dealer_roles']:
            if isinstance(config[key], list):
                config[key] = json.dumps(config[key])
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO guild_config
                    (guild_id, prefix, log_channel, transcript_channel, ticket_category,
                     closed_category, admin_roles, mod_roles, staff_roles, dealer_roles, ticket_counter)
                VALUES (:guild_id, :prefix, :log_channel, :transcript_channel, :ticket_category,
                        :closed_category, :admin_roles, :mod_roles, :staff_roles, :dealer_roles, :ticket_counter)
                ON CONFLICT(guild_id) DO UPDATE SET
                    prefix=excluded.prefix,
                    log_channel=excluded.log_channel,
                    transcript_channel=excluded.transcript_channel,
                    ticket_category=excluded.ticket_category,
                    closed_category=excluded.closed_category,
                    admin_roles=excluded.admin_roles,
                    mod_roles=excluded.mod_roles,
                    staff_roles=excluded.staff_roles,
                    dealer_roles=excluded.dealer_roles,
                    ticket_counter=excluded.ticket_counter
            ''', config)
            await db.commit()

    async def increment_ticket_counter(self, guild_id: int) -> int:
        config = await self.get_config(guild_id)
        new_count = config['ticket_counter'] + 1
        await self.set_config(guild_id, ticket_counter=new_count)
        return new_count

    # ── Panels ────────────────────────────────────────────────────────────────

    async def create_panel(self, guild_id, channel_id, message_id, title, description,
                           color, footer, thumbnail, categories) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('''
                INSERT INTO panels (guild_id, channel_id, message_id, title, description,
                                    color, footer, thumbnail, categories)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, channel_id, message_id, title, description,
                  color, footer, thumbnail, json.dumps(categories)))
            await db.commit()
            return cur.lastrowid

    async def get_panel(self, message_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM panels WHERE message_id = ?', (message_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                d['categories'] = json.loads(d['categories'] or '[]')
                return d

    async def get_all_panels(self, guild_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM panels WHERE guild_id = ?', (guild_id,)
            ) as cur:
                rows = await cur.fetchall()
                result = []
                for row in rows:
                    d = dict(row)
                    d['categories'] = json.loads(d['categories'] or '[]')
                    result.append(d)
                return result

    async def delete_panel(self, panel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('DELETE FROM panels WHERE id = ?', (panel_id,))
            await db.commit()

    async def update_panel_message(self, panel_id: int, message_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE panels SET message_id = ? WHERE id = ?', (message_id, panel_id)
            )
            await db.commit()

    # ── Tickets ───────────────────────────────────────────────────────────────

    async def create_ticket(self, guild_id, channel_id, user_id, category, ticket_number) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('''
                INSERT INTO tickets (guild_id, channel_id, user_id, category, ticket_number)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, channel_id, user_id, category, ticket_number))
            await db.commit()
            return cur.lastrowid

    async def get_ticket_by_channel(self, channel_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM tickets WHERE channel_id = ?', (channel_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def close_ticket(self, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (channel_id,))
            await db.commit()

    async def claim_ticket(self, channel_id: int, staff_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE tickets SET claimed_by = ? WHERE channel_id = ?', (staff_id, channel_id)
            )
            await db.commit()

    async def get_open_tickets(self, guild_id: int, user_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'
            ''', (guild_id, user_id)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Transcript Messages ───────────────────────────────────────────────────

    async def log_message(self, ticket_id, author_id, author_name, content):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO ticket_messages (ticket_id, author_id, author_name, content)
                VALUES (?, ?, ?, ?)
            ''', (ticket_id, author_id, author_name, content))
            await db.commit()

    async def get_transcript(self, ticket_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp ASC
            ''', (ticket_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]
