import discord
import aiohttp
import io

CATEGORY_INFO = {
    'i2c': {'label': 'INR → Crypto', 'emoji': '💸', 'short': 'I2C'},
    'c2i': {'label': 'Crypto → INR', 'emoji': '💰', 'short': 'C2I'},
    'support': {'label': 'Support', 'emoji': '🎧', 'short': 'Support'},
    'dispute': {'label': 'Dispute / Issue', 'emoji': '⚠️', 'short': 'Dispute'},
}

def get_category_info(value: str) -> dict:
    return CATEGORY_INFO.get(value, {'label': value, 'emoji': '🎫', 'short': value})

async def fetch_live_rate() -> float | None:
    """Fetch live USD/INR rate from exchangerate-api (free, no key needed)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://open.er-api.com/v6/latest/USD',
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['rates'].get('INR')
    except Exception:
        pass
    # Fallback
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.frankfurter.app/latest?from=USD&to=INR',
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['rates'].get('INR')
    except Exception:
        pass
    return None

async def get_rate(db, guild_id: int) -> float:
    """Get rate — use override if set, else fetch live."""
    config = await db.get_config(guild_id)
    if config.get('rate_override'):
        return float(config['rate_override'])
    live = await fetch_live_rate()
    return live or 84.0  # absolute fallback

async def has_staff_role(member: discord.Member, config: dict) -> bool:
    ids = {r.id for r in member.roles}
    all_staff = (config.get('admin_roles',[]) + config.get('mod_roles',[]) +
                 config.get('staff_roles',[]) + config.get('dealer_roles',[]))
    return bool(ids & set(all_staff)) or member.guild_permissions.administrator

async def has_admin_or_mod(member: discord.Member, config: dict) -> bool:
    ids = {r.id for r in member.roles}
    roles = config.get('admin_roles',[]) + config.get('mod_roles',[])
    return bool(ids & set(roles)) or member.guild_permissions.administrator

async def has_admin_role(member: discord.Member, config: dict) -> bool:
    ids = {r.id for r in member.roles}
    return bool(ids & set(config.get('admin_roles',[]))) or member.guild_permissions.administrator

def is_exchanger_role(member: discord.Member, config: dict) -> bool:
    ids = {r.id for r in member.roles}
    return bool(ids & set(config.get('dealer_roles',[])))

def hex_to_int(hex_str: str) -> int:
    try:
        return int(hex_str.strip().lstrip('#'), 16)
    except ValueError:
        return 0x2F3136

def build_ticket_embed(category: str, user: discord.Member, ticket_number: int,
                       claimed_by: discord.Member = None, modal_answers: dict = None) -> discord.Embed:
    info = get_category_info(category)
    colors = {'i2c': 0x2ECC71, 'c2i': 0xE74C3C, 'support': 0x9B59B6, 'dispute': 0xFF6B35}
    color = colors.get(category, 0x5865F2)
    embed = discord.Embed(
        title=f"{info['emoji']} {info['label']} — Ticket #{ticket_number:04d}",
        color=color
    )
    embed.add_field(name='👤 Client', value=user.mention, inline=True)
    embed.add_field(name='📋 Category', value=info['label'], inline=True)
    if claimed_by:
        embed.add_field(name='👷 Claimed By', value=claimed_by.mention, inline=True)
    else:
        embed.add_field(name='👷 Status', value='`Unclaimed`', inline=True)
    if modal_answers:
        for k, v in modal_answers.items():
            embed.add_field(name=k, value=f'`{v}`', inline=True)
    embed.add_field(
        name='📌 Instructions',
        value='> Staff will assist you shortly.\n> Do **not** ping staff — be patient.',
        inline=False
    )
    embed.set_footer(text='Titan Exchange | /close to close ticket (staff only)')
    return embed

async def generate_html_transcript(ticket: dict, messages: list, guild: discord.Guild) -> str:
    info = get_category_info(ticket.get('category',''))
    rows = ''.join(f'''
        <div class="message">
            <span class="author">{m["author_name"]}</span>
            <span class="time">{m["timestamp"]}</span>
            <div class="content">{str(m["content"]).replace("<","&lt;").replace(">","&gt;")}</div>
        </div>''' for m in messages)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Ticket #{ticket['ticket_number']:04d}</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#1e1f22;color:#dcddde;margin:0;padding:0}}
.header{{background:#2b2d31;padding:20px 30px;border-bottom:3px solid #5865F2}}
.header h1{{margin:0;color:#fff;font-size:1.4em}}
.header p{{margin:4px 0 0;color:#b9bbbe;font-size:.9em}}
.messages{{padding:20px 30px;max-width:900px;margin:auto}}
.message{{padding:10px 14px;margin:6px 0;background:#2b2d31;border-radius:8px}}
.author{{font-weight:bold;color:#5865F2;margin-right:10px}}
.time{{font-size:.75em;color:#72767d}}
.content{{margin-top:4px;white-space:pre-wrap;word-break:break-word}}
.footer{{text-align:center;padding:20px;color:#72767d;font-size:.8em}}
</style></head><body>
<div class="header">
  <h1>{info['emoji']} Ticket #{ticket['ticket_number']:04d} — {info['label']}</h1>
  <p>Server: {guild.name} | Status: {ticket['status'].upper()} | Opened: {ticket['opened_at']}</p>
</div>
<div class="messages">{rows or '<p style="color:#72767d">No messages logged.</p>'}</div>
<div class="footer">Titan Exchange Transcript</div>
</body></html>"""
