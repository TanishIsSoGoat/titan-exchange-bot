# 🏦 Titan Exchange — Ticket Bot

A fully-featured Discord ticket bot for Titan Exchange server.
Built with `discord.py` + `SQLite`. Deployable on Railway via GitHub.

---

## 📁 Project Structure

```
titan-exchange-bot/
├── bot.py              # Main entry point
├── database.py         # SQLite database manager
├── utils.py            # Shared helpers, embeds, transcript generator
├── requirements.txt
├── railway.toml        # Railway deployment config
├── .env.example        # Environment variable template
├── .gitignore
└── cogs/
    ├── tickets.py      # Ticket open/close/claim logic
    ├── panel.py        # Panel create/send/delete
    ├── setup.py        # Bot configuration commands
    └── admin.py        # Admin commands + help
```

---

## 🚀 Deployment Guide (Railway + GitHub)

### Step 1 — Discord Developer Portal
1. Go to https://discord.com/developers/applications
2. Create a new application → Bot tab → Reset Token → copy it
3. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
4. Go to OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (or at minimum: Manage Channels, Manage Roles, Read/Send Messages, Attach Files, Embed Links)
5. Invite the bot to your server

### Step 2 — GitHub
1. Create a new **private** GitHub repository
2. Push this entire folder to it:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 3 — Railway
1. Go to https://railway.app → New Project → Deploy from GitHub
2. Select your repository
3. Go to your project → **Variables** tab and add:
   - `DISCORD_TOKEN` = your bot token
   - `PREFIX` = `!`
   - `DB_PATH` = `/data/titan.db`
4. Go to **Volumes** tab → Add Volume → Mount path: `/data`
   *(This keeps the SQLite database persistent across deploys!)*
5. Deploy — bot should come online within 1-2 minutes ✅

---

## ⚙️ First-Time Setup (in Discord)

After the bot is online, run these in your server (you need Administrator):

```
/setup transcript #transcript-channel
/setup logs #ticket-logs
/setup category Tickets           ← name of your Discord category

/setup addrole Admin @YourAdminRole
/setup addrole mod @YourModRole
/setup addrole staff @SupportRole
/setup addrole dealer @DealerRole
```

Then create your ticket panel:
```
/panel create    ← opens a modal to fill in title, description, color
```

---

## 🎫 Ticket Panel Features

- **One panel, all categories** as buttons
- **6 categories**: Buy Crypto, Sell Crypto, Buy INR, Sell INR, Support, Dispute
- **Private channels** created per ticket
- **Claim** button for staff
- **Add/Remove user** to ticket
- **HTML transcript** saved on close
- **Panels survive bot restarts** (persistent views)

---

## 📋 All Commands

### Ticket Commands
| Command | Description |
|---------|-------------|
| `/close` or `!close` | Close current ticket |
| `/add @user` or `!add @user` | Add user to ticket |
| `/remove @user` or `!remove @user` | Remove user from ticket |

### Panel Commands
| Command | Description |
|---------|-------------|
| `/panel create` | Create panel via modal |
| `/panel list` | List all panels |
| `/panel delete <id>` | Delete a panel |
| `/panel send <id> #channel` | Send panel to another channel |

### Setup Commands
| Command | Description |
|---------|-------------|
| `/setup view` or `!setup` | View current config |
| `/setup transcript #ch` | Set transcript channel |
| `/setup logs #ch` | Set log channel |
| `/setup category <name>` | Set ticket category |
| `/setup addrole <group> @role` | Add role to group |
| `/setup removerole <group> @role` | Remove role from group |
| `/setup prefix <prefix>` | Change prefix |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/admin tickets` | View open ticket stats |
| `/admin resetcounter` | Reset ticket counter |
| `/admin forceclose #channel` | Force close a ticket |

---

## 🔐 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | required | Your bot token |
| `PREFIX` | `!` | Prefix for text commands |
| `DB_PATH` | `./data/titan.db` | Path to SQLite DB file |

---

## 💾 Database Backup

The SQLite database lives at the Railway Volume mount (`/data/titan.db`).
To back it up manually, download it from Railway's volume explorer or set up a cron job to copy it to an S3 bucket / Google Drive.
