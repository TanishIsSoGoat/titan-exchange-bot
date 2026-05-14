import discord
import json

# ── Default ticket categories ─────────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    {"label": "Buy Crypto",      "emoji": "📈", "value": "buy_crypto",   "description": "Buy cryptocurrency"},
    {"label": "Sell Crypto",     "emoji": "📉", "value": "sell_crypto",  "description": "Sell cryptocurrency"},
    {"label": "Buy INR",         "emoji": "💰", "value": "buy_inr",      "description": "Buy INR"},
    {"label": "Sell INR",        "emoji": "💵", "value": "sell_inr",     "description": "Sell INR"},
    {"label": "Support",         "emoji": "🎧", "value": "support",      "description": "General support"},
    {"label": "Dispute / Issue", "emoji": "⚠️", "value": "dispute",      "description": "Report a dispute or issue"},
]

CATEGORY_COLORS = {
    "buy_crypto":  0x2ECC71,
    "sell_crypto": 0xE74C3C,
    "buy_inr":     0xF1C40F,
    "sell_inr":    0x3498DB,
    "support":     0x9B59B6,
    "dispute":     0xFF6B35,
}

def get_category_info(value: str) -> dict:
    for c in DEFAULT_CATEGORIES:
        if c['value'] == value:
            return c
    return {"label": value, "emoji": "🎫", "value": value, "description": ""}

async def has_staff_role(member: discord.Member, config: dict) -> bool:
    """Check if a member has any staff role (admin, mod, staff, dealer)."""
    member_role_ids = {r.id for r in member.roles}
    all_staff = (
        config.get('admin_roles', []) +
        config.get('mod_roles', []) +
        config.get('staff_roles', []) +
        config.get('dealer_roles', [])
    )
    return bool(member_role_ids & set(all_staff)) or member.guild_permissions.administrator

async def has_admin_role(member: discord.Member, config: dict) -> bool:
    member_role_ids = {r.id for r in member.roles}
    return (
        bool(member_role_ids & set(config.get('admin_roles', []))) or
        member.guild_permissions.administrator
    )

def build_ticket_embed(category_value: str, user: discord.Member, ticket_number: int,
                       claimed_by: discord.Member = None) -> discord.Embed:
    info = get_category_info(category_value)
    color = CATEGORY_COLORS.get(category_value, 0x2F3136)
    embed = discord.Embed(
        title=f"{info['emoji']} {info['label']} — Ticket #{ticket_number:04d}",
        description=(
            f"**Opened by:** {user.mention}\n"
            f"**Category:** {info['label']}\n"
            f"{'**Claimed by:** ' + claimed_by.mention if claimed_by else '**Status:** Unclaimed'}\n\n"
            f"> Please describe your request and a staff member will assist you shortly.\n"
            f"> Do **not** ping staff — be patient and wait."
        ),
        color=color
    )
    embed.set_footer(text="Titan Exchange | Close ticket with /close or !close")
    embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
    return embed

def build_panel_embed(title: str, description: str, color: int,
                      footer: str = None, thumbnail: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    else:
        embed.set_footer(text="Titan Exchange | Click a button below to open a ticket")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed

def hex_to_int(hex_str: str) -> int:
    hex_str = hex_str.strip().lstrip('#')
    try:
        return int(hex_str, 16)
    except ValueError:
        return 0x2F3136

async def generate_html_transcript(ticket: dict, messages: list, guild: discord.Guild) -> str:
    info = get_category_info(ticket.get('category', ''))
    rows = ""
    for msg in messages:
        rows += f"""
        <div class="message">
            <span class="author">{discord.utils.escape_mentions(msg['author_name'])}</span>
            <span class="time">{msg['timestamp']}</span>
            <div class="content">{discord.utils.escape_mentions(str(msg['content']))}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ticket #{ticket['ticket_number']:04d} Transcript</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1e1f22; color: #dcddde; margin: 0; padding: 0; }}
  .header {{ background: #2b2d31; padding: 20px 30px; border-bottom: 3px solid #5865F2; }}
  .header h1 {{ margin: 0; color: #fff; font-size: 1.4em; }}
  .header p {{ margin: 4px 0 0; color: #b9bbbe; font-size: 0.9em; }}
  .messages {{ padding: 20px 30px; max-width: 900px; margin: auto; }}
  .message {{ padding: 10px 14px; margin: 6px 0; background: #2b2d31; border-radius: 8px; }}
  .author {{ font-weight: bold; color: #5865F2; margin-right: 10px; }}
  .time {{ font-size: 0.75em; color: #72767d; }}
  .content {{ margin-top: 4px; white-space: pre-wrap; word-break: break-word; }}
  .footer {{ text-align: center; padding: 20px; color: #72767d; font-size: 0.8em; }}
</style>
</head>
<body>
<div class="header">
  <h1>{info['emoji']} Ticket #{ticket['ticket_number']:04d} — {info['label']}</h1>
  <p>Server: {guild.name} &nbsp;|&nbsp; Status: {ticket['status'].upper()} &nbsp;|&nbsp; Opened: {ticket['opened_at']}</p>
</div>
<div class="messages">{rows if rows else '<p style="color:#72767d">No messages logged.</p>'}</div>
<div class="footer">Titan Exchange Transcript &mdash; Generated automatically</div>
</body>
</html>"""
