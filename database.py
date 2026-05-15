import aiosqlite, json, os

DB_PATH = os.getenv('DB_PATH', './data/titan.db')

class Database:
    def __init__(self):
        self.path = DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id            INTEGER PRIMARY KEY,
                    prefix              TEXT DEFAULT '!',
                    log_channel         INTEGER,
                    transcript_channel  INTEGER,
                    ticket_category     INTEGER,
                    admin_roles         TEXT DEFAULT '[]',
                    mod_roles           TEXT DEFAULT '[]',
                    staff_roles         TEXT DEFAULT '[]',
                    dealer_roles        TEXT DEFAULT '[]',
                    ticket_counter      INTEGER DEFAULT 0,
                    vouch_channel       INTEGER,
                    rate_override       REAL,
                    rate_i2c            REAL DEFAULT 101,
                    rate_c2i_below      REAL DEFAULT 97.5,
                    rate_c2i_above      REAL DEFAULT 98.5
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
                    deal_amount_usd REAL,
                    deal_amount_inr REAL,
                    opened_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at       TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id   INTEGER NOT NULL,
                    author_id   INTEGER NOT NULL,
                    author_name TEXT,
                    content     TEXT,
                    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS exchanger_limits (
                    guild_id        INTEGER NOT NULL,
                    user_id         INTEGER NOT NULL,
                    limit_usd       REAL DEFAULT 0,
                    used_usd        REAL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS deals (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id        INTEGER NOT NULL,
                    ticket_id       INTEGER NOT NULL,
                    exchanger_id    INTEGER NOT NULL,
                    client_id       INTEGER NOT NULL,
                    pair            TEXT,
                    amount_usd      REAL,
                    amount_inr      REAL,
                    rate_used       REAL,
                    completed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_stats (
                    guild_id        INTEGER NOT NULL,
                    user_id         INTEGER NOT NULL,
                    role            TEXT NOT NULL,
                    total_deals     INTEGER DEFAULT 0,
                    total_usd       REAL DEFAULT 0,
                    total_inr       REAL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, role)
                );
            ''')
            await db.commit()

    # ── Config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM guild_config WHERE guild_id=?', (guild_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    await db.execute('INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)', (guild_id,))
                    await db.commit()
                    return {'guild_id': guild_id, 'prefix': '!', 'log_channel': None,
                            'transcript_channel': None, 'ticket_category': None,
                            'admin_roles': [], 'mod_roles': [], 'staff_roles': [], 'dealer_roles': [],
                            'ticket_counter': 0, 'vouch_channel': None, 'rate_override': None, 'rate_i2c': 101, 'rate_c2i_below': 97.5, 'rate_c2i_above': 98.5}
                d = dict(row)
                for k in ['admin_roles','mod_roles','staff_roles','dealer_roles']:
                    d[k] = json.loads(d[k] or '[]')
                return d

    async def set_config(self, guild_id: int, **kwargs):
        config = await self.get_config(guild_id)
        config.update(kwargs)
        for k in ['admin_roles','mod_roles','staff_roles','dealer_roles']:
            if isinstance(config[k], list):
                config[k] = json.dumps(config[k])
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO guild_config
                    (guild_id,prefix,log_channel,transcript_channel,ticket_category,
                     admin_roles,mod_roles,staff_roles,dealer_roles,ticket_counter,vouch_channel,rate_override,rate_i2c,rate_c2i_below,rate_c2i_above)
                VALUES
                    (:guild_id,:prefix,:log_channel,:transcript_channel,:ticket_category,
                     :admin_roles,:mod_roles,:staff_roles,:dealer_roles,:ticket_counter,:vouch_channel,:rate_override,:rate_i2c,:rate_c2i_below,:rate_c2i_above)
                ON CONFLICT(guild_id) DO UPDATE SET
                    prefix=excluded.prefix, log_channel=excluded.log_channel,
                    transcript_channel=excluded.transcript_channel, ticket_category=excluded.ticket_category,
                    admin_roles=excluded.admin_roles, mod_roles=excluded.mod_roles,
                    staff_roles=excluded.staff_roles, dealer_roles=excluded.dealer_roles,
                    ticket_counter=excluded.ticket_counter, vouch_channel=excluded.vouch_channel,
                    rate_override=excluded.rate_override,
                    rate_i2c=excluded.rate_i2c,
                    rate_c2i_below=excluded.rate_c2i_below,
                    rate_c2i_above=excluded.rate_c2i_above
            ''', config)
            await db.commit()

    async def increment_ticket_counter(self, guild_id: int) -> int:
        config = await self.get_config(guild_id)
        n = config['ticket_counter'] + 1
        await self.set_config(guild_id, ticket_counter=n)
        return n

    # ── Panels ────────────────────────────────────────────────────────────────

    async def create_panel(self, guild_id, channel_id, message_id, title, description, color, footer, thumbnail) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                'INSERT INTO panels (guild_id,channel_id,message_id,title,description,color,footer,thumbnail) VALUES (?,?,?,?,?,?,?,?)',
                (guild_id, channel_id, message_id, title, description, color, footer, thumbnail))
            await db.commit()
            return cur.lastrowid

    async def get_all_panels(self, guild_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM panels WHERE guild_id=?', (guild_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def delete_panel(self, panel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('DELETE FROM panels WHERE id=?', (panel_id,))
            await db.commit()

    async def update_panel_message(self, panel_id: int, message_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('UPDATE panels SET message_id=? WHERE id=?', (message_id, panel_id))
            await db.commit()

    # ── Tickets ───────────────────────────────────────────────────────────────

    async def create_ticket(self, guild_id, channel_id, user_id, category, ticket_number) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                'INSERT INTO tickets (guild_id,channel_id,user_id,category,ticket_number) VALUES (?,?,?,?,?)',
                (guild_id, channel_id, user_id, category, ticket_number))
            await db.commit()
            return cur.lastrowid

    async def get_ticket_by_channel(self, channel_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM tickets WHERE channel_id=?', (channel_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_open_tickets(self, guild_id: int, user_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
                (guild_id, user_id)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def claim_ticket(self, channel_id: int, staff_id: int, amount_usd: float = None, amount_inr: float = None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE tickets SET claimed_by=?, deal_amount_usd=?, deal_amount_inr=? WHERE channel_id=?',
                (staff_id, amount_usd, amount_inr, channel_id))
            await db.commit()

    async def close_ticket(self, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE tickets SET status='closed', closed_at=CURRENT_TIMESTAMP WHERE channel_id=?",
                (channel_id,))
            await db.commit()

    async def mark_ticket_done(self, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE tickets SET status='done' WHERE channel_id=?", (channel_id,))
            await db.commit()

    async def log_message(self, ticket_id, author_id, author_name, content):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'INSERT INTO ticket_messages (ticket_id,author_id,author_name,content) VALUES (?,?,?,?)',
                (ticket_id, author_id, author_name, content))
            await db.commit()

    async def get_transcript(self, ticket_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY timestamp ASC',
                (ticket_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Exchanger Limits ──────────────────────────────────────────────────────

    async def get_exchanger_limit(self, guild_id: int, user_id: int) -> dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM exchanger_limits WHERE guild_id=? AND user_id=?',
                (guild_id, user_id)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else {'guild_id': guild_id, 'user_id': user_id, 'limit_usd': 0, 'used_usd': 0}

    async def set_exchanger_limit(self, guild_id: int, user_id: int, limit_usd: float):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO exchanger_limits (guild_id, user_id, limit_usd, used_usd)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET limit_usd=excluded.limit_usd
            ''', (guild_id, user_id, limit_usd))
            await db.commit()

    async def add_used_limit(self, guild_id: int, user_id: int, amount_usd: float):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO exchanger_limits (guild_id, user_id, limit_usd, used_usd)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET used_usd=used_usd+excluded.used_usd
            ''', (guild_id, user_id, amount_usd))
            await db.commit()

    async def free_used_limit(self, guild_id: int, user_id: int, amount_usd: float):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                UPDATE exchanger_limits SET used_usd=MAX(0, used_usd-?) WHERE guild_id=? AND user_id=?
            ''', (amount_usd, guild_id, user_id))
            await db.commit()

    # ── Deals & Stats ─────────────────────────────────────────────────────────

    async def record_deal(self, guild_id, ticket_id, exchanger_id, client_id, pair, amount_usd, amount_inr, rate_used):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                INSERT INTO deals (guild_id,ticket_id,exchanger_id,client_id,pair,amount_usd,amount_inr,rate_used)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (guild_id, ticket_id, exchanger_id, client_id, pair, amount_usd, amount_inr, rate_used))
            # Update exchanger stats
            await db.execute('''
                INSERT INTO user_stats (guild_id,user_id,role,total_deals,total_usd,total_inr)
                VALUES (?,?,'exchanger',1,?,?)
                ON CONFLICT(guild_id,user_id,role) DO UPDATE SET
                    total_deals=total_deals+1, total_usd=total_usd+excluded.total_usd,
                    total_inr=total_inr+excluded.total_inr
            ''', (guild_id, exchanger_id, amount_usd, amount_inr))
            # Update client stats
            await db.execute('''
                INSERT INTO user_stats (guild_id,user_id,role,total_deals,total_usd,total_inr)
                VALUES (?,?,'client',1,?,?)
                ON CONFLICT(guild_id,user_id,role) DO UPDATE SET
                    total_deals=total_deals+1, total_usd=total_usd+excluded.total_usd,
                    total_inr=total_inr+excluded.total_inr
            ''', (guild_id, client_id, amount_usd, amount_inr))
            await db.commit()

    async def get_user_stats(self, guild_id: int, user_id: int) -> list:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM user_stats WHERE guild_id=? AND user_id=?',
                (guild_id, user_id)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_deal_count(self, guild_id: int, exchanger_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                'SELECT COUNT(*) FROM deals WHERE guild_id=? AND exchanger_id=?',
                (guild_id, exchanger_id)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0
