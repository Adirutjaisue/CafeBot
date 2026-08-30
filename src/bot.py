# -*- coding: utf-8 -*-
"""
บอทประจำเซิร์ฟเวอร์ Gamers' Café (Event Scheduling & Smart Auto-Balancing Edition - Fixed Fast Response)
"""
import asyncio
import sys
import io
import json
import os
import re
import time
import math
import random
import datetime
import feedparser
from bs4 import BeautifulSoup
import discord
from aiohttp import web
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput

try:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not TOKEN:
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as ef:
            for line in ef:
                if line.startswith("DISCORD_BOT_TOKEN="):
                    TOKEN = line.split("=", 1)[1].strip()

TARGET_GUILD_ID = 1437091922341658797

WELCOME_CHANNEL_ID = 1543479670509543447 # ห้อง #ต้อนรับ
CHAT_CHANNEL_ID = 1543479676268318830   # ห้อง #คุยเล่น
PHOTO_CHANNEL_ID = 1543479679615377408  # ห้อง #รูปภาพ
NEWS_CHANNEL_ID = 1543479691304767588   # ห้อง #ข่าวเกม
RULES_CHANNEL_ID = 1438175870081695744  # ห้อง #กฎ
AFK_CHANNEL_ID = 1543479716105683056    # ห้อง 💤 พักสายตา
MARKET_CHANNEL_ID = 1543512266442539059 # ห้อง 🛒・ตลาดซื้อขาย
PARTY_CHANNEL_ID = 1543565062038364251  # ห้อง ⚔️・จัดตี้เกม
REPORT_LOG_CHANNEL_ID = 1543479721302560828 # ห้อง #แจ้งปัญหา

UNVERIFIED_ROLE_NAME = "🔒・ยังไม่ได้ตั้งชื่อ"
MEMBER_ROLE_NAME = "Cafe Member"
BIRTHDAY_ROLE_NAME = "🎂・Birthday"
GOOD_TRADER_ROLE = "⭐・พ่อค้าเครดิตดี"
TOP_TRADER_ROLE = "👑・พ่อค้าดีเด่น"

def get_member_role(guild: discord.Guild):
    """ค้นหายศสมาชิก (รองรับทั้ง 'Cafe Member', '☕・Cafe Member')"""
    if not guild:
        return None
    for r in guild.roles:
        if r.name in ["Cafe Member", "☕・Cafe Member", "Member", "CafeMember"]:
            return r
    for r in guild.roles:
        if "cafe member" in r.name.lower():
            return r
    return None

def get_unverified_role(guild: discord.Guild):
    """ค้นหายศยังไม่ได้ตั้งชื่อ"""
    if not guild:
        return None
    for r in guild.roles:
        if "ยังไม่ได้ตั้งชื่อ" in r.name:
            return r
    for r in guild.roles:
        if "unverified" in r.name.lower():
            return r
    return None

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(CURR_DIR, "database")):
    ROOT_DIR = CURR_DIR
else:
    ROOT_DIR = os.path.dirname(CURR_DIR)

DB_DIR = os.path.join(ROOT_DIR, "database")
MEDIA_DIR = os.path.join(ROOT_DIR, "media")
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

CACHE_FILE = os.path.join(DB_DIR, "news_cache.json")
LEVELS_FILE = os.path.join(DB_DIR, "levels.json")
ECONOMY_FILE = os.path.join(DB_DIR, "economy.json")
BIRTHDAYS_FILE = os.path.join(DB_DIR, "birthdays.json")
PHOTO_MAP_FILE = os.path.join(DB_DIR, "images_map.json")
REPUTATION_FILE = os.path.join(DB_DIR, "reputation.json")
PARTIES_FILE = os.path.join(DB_DIR, "parties.json")
EVENTS_FILE = os.path.join(DB_DIR, "events.json")
BANNER_PATH = os.path.join(MEDIA_DIR, "banner.jpg")

THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

temp_party_rooms = set()
xp_cooldowns = {}
verification_dm_map = {} # เก็บ [m1.id, m2.id] สำหรับลบข้อความต้อนรับใน DM หลังกรอกเสร็จหรือตอนออกจากเซิร์ฟเวอร์

async def delete_user_verification_dms(user_id: int):
    """
    🧹 ลบข้อความชวนกรอกชื่อใน DM เมื่อผู้ใช้กรอกเสร็จแล้ว หรือเมื่อผู้ใช้ออกจากเซิร์ฟเวอร์
    """
    uid_str = str(user_id)
    if uid_str in verification_dm_map:
        msg_ids = verification_dm_map[uid_str]
        try:
            user_obj = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user_obj:
                dm_ch = getattr(user_obj, "dm_channel", None) or await user_obj.create_dm()
                for mid in msg_ids:
                    try:
                        m_to_del = await dm_ch.fetch_message(mid)
                        if m_to_del:
                            await m_to_del.delete()
                    except Exception:
                        pass
        except Exception:
            pass
        del verification_dm_map[uid_str]

GAME_ROLE_MAPPING = {
    "ragnarok": "🗡️・Ragnarok",
    "rag": "🗡️・Ragnarok",
    "ro": "🗡️・Ragnarok",
    "valorant": "🎯・Valorant",
    "val": "🎯・Valorant",
    "rov": "⚔️・RoV",
    "minecraft": "🧱・Minecraft",
    "mc": "🧱・Minecraft",
    "roblox": "🎲・Roblox",
    "apex": "🔫・Apex Legends",
    "genshin": "✨・Genshin Impact"
}

RAGNAROK_JOBS = {
    "knight": {"name": "Knight / Lord Knight", "emoji": "⚔️", "role": "⚔️・Knight / LK", "desc": "สายดาบ/หอก ชนบอส ถึกทน ดาเมจหนัก"},
    "crusader": {"name": "Crusader / Paladin", "emoji": "🛡️", "role": "🛡️・Crusader / Paladin", "desc": "สายโล่ศักดิ์สิทธิ์ โคตรถึก คุ้มกันเพื่อน"},
    "wizard": {"name": "Wizard / High Wizard", "emoji": "🧙‍♂️", "role": "🧙‍♂️・High Wizard", "desc": "สายเวทมนตร์หมู่ ถล่มมอนสเตอร์ทั้งจอ"},
    "sage": {"name": "Sage / Professor", "emoji": "📖", "role": "📖・Sage / Professor", "desc": "สายเคลือบธาตุ ตัดเวท เติม SP ป่วนบอส"},
    "hunter": {"name": "Hunter / Sniper", "emoji": "🏹", "role": "🏹・Hunter / Sniper", "desc": "สายธนู ยิงไกล ดาเมจคริรัว วางแทรป"},
    "bard_dancer": {"name": "Bard / Dancer / Clown", "emoji": "🎶", "role": "🎶・Bard / Dancer", "desc": "สายร้องเพลง/เต้น บัฟความเร็วและสกิลตี้"},
    "assassin": {"name": "Assassin / SinX", "emoji": "🗡️", "role": "🗡️・Assassin / SinX", "desc": "สายมีด/กาตาร์ ล่องหน คริรัว ซัดทีเดียวดับ"},
    "rogue": {"name": "Rogue / Stalker", "emoji": "🎭", "role": "🎭・Rogue / Stalker", "desc": "สายปลดเกราะ คัดลอกสกิล โคตรพริ้ว"},
    "priest": {"name": "Priest / High Priest", "emoji": "✨", "role": "✨・Priest / High Priest", "desc": "สายซัพพอร์ต ฮีล บัฟ ชุบชีวิต ขาดไม่ได้"},
    "monk": {"name": "Monk / Champion", "emoji": "🥋", "role": "🥋・Monk / Champion", "desc": "สายหมัดอาชูร่า หมัดเดียวปิดชีพทุกอย่าง"},
    "blacksmith": {"name": "Blacksmith / Whitesmith", "emoji": "🔨", "role": "🔨・Whitesmith", "desc": "สายตีดาบ ฟันไว ตีบวก ปาเงินแรง"},
    "alchemist": {"name": "Alchemist / Creator", "emoji": "🧪", "role": "🧪・Alchemist / Creator", "desc": "สายปาขวด ปายา เรียกลูกสมุนพืช"},
    "gunslinger_ninja": {"name": "Gunslinger / Ninja", "emoji": "🔫", "role": "🔫・Gunslinger / Ninja", "desc": "สายปืน ยิงไว / นินจาคาถาและดาวกระจาย"},
    "doram": {"name": "Doram (เผ่าแมว)", "emoji": "🐱", "role": "🐱・Doram (แมว)", "desc": "เผ่าแมวน้อย สกิลพืช/สัตว์/เวท ครบเครื่อง"}
}

RO_JOB_KEYWORD_MAPPING = {
    "knight": ["knight", "lord knight", "lk", "ไนท์", "ลอร์ดไนท์", "ดาบ", "หอก", "rk", "rune knight"],
    "crusader": ["crusader", "paladin", "pala", "ครู", "ครูเซเดอร์", "พาลา", "พาลาดิน", "โล่", "rg", "royal guard"],
    "wizard": ["wizard", "high wizard", "hw", "วิ", "วิสาด", "ไฮวิ", "เวท", "wl", "warlock"],
    "sage": ["sage", "professor", "prof", "เสจ", "พรอฟ", "โปรฟ", "sorcerer"],
    "hunter": ["hunter", "sniper", "snip", "ฮัน", "ฮันเตอร์", "สไน", "สไนเปอร์", "ธนู", "ranger", "เรนเจอร์"],
    "bard_dancer": ["bard", "dancer", "clown", "gypsy", "แดน", "แดนเซอร์", "บาร์ด", "ตัวเต้น", "ตัวร้อง", "minstrel", "wanderer"],
    "assassin": ["assassin", "assassin cross", "sinx", "sin", "แอส", "แอสครอส", "ซิน", "มีด", "กาตาร์", "gx", "guillotine cross"],
    "rogue": ["rogue", "stalker", "sc", "shadow chaser", "โร้ค", "สโต๊ก", "สตอเกอร์", "ตัวปลด"],
    "priest": ["priest", "high priest", "hp", "พรีส", "ไฮพรีส", "พระ", "ฮีล", "ab", "archbishop"],
    "monk": ["monk", "champion", "champ", "ม้อง", "มอง", "แชมป์", "แชมเปี้ยน", "อาชู", "sura", "สุระ"],
    "blacksmith": ["blacksmith", "whitesmith", "ws", "bs", "ช่าง", "ตีดาบ", "พ่อค้า", "ไวท์สมิท", "nc", "mechanic"],
    "alchemist": ["alchemist", "creator", "gene", "genetic", "เคมิส", "อัลเคมิส", "ครีเอเตอร์", "ปายา"],
    "gunslinger_ninja": ["gunslinger", "ninja", "gun", "ปืน", "นินจา", "ดาวกระจาย", "rebellion", "kagerou", "oboro"],
    "doram": ["doram", "summoner", "แมว", "เผ่าแมว", "โดรัม"]
}

def resolve_ro_job(text: str):
    if not text:
        return None, None, None
    clean = text.lower().strip()
    for jkey, keywords in RO_JOB_KEYWORD_MAPPING.items():
        for kw in keywords:
            if kw in clean:
                info = RAGNAROK_JOBS.get(jkey)
                if info:
                    return jkey, info["name"], info["emoji"]
    return None, None, None

def check_is_ragnarok_player(text: str) -> bool:
    """
    🎮 ตรวจสอบว่าผู้ใช้เล่น Ragnarok ทุกเวอร์ชัน (RO, RO M, ROX, ROM, ROW, ROO, Landverse, Origin, ฯลฯ)
    """
    if not text:
        return False
    t = text.lower().strip()
    ro_keywords = [
        "ragnarok", "rag", "landverse", "origin", "rox", "rom", "row", "roo", "roc", "rol",
        "ro m", "ro x", "ro w", "ro o", "ro c", "ro-m", "ro-x", "ro-w", "ro-o",
        "ggh", "gravity", "แร็ค", "แรค", "แรก", "แร็ก", "แรคนารอค", "แร็คนาร็อก", "แร็คนาร็อค", "แลนด์เวอร์ส"
    ]
    if any(kw in t for kw in ro_keywords):
        return True
    words = re.findall(r'\b[a-zA-Z0-9_]+\b', t)
    if any(w in words for w in ["ro", "rag", "ragnarok", "rox", "rom", "row", "roo", "roc"]):
        return True
    return False

SHOP_ITEMS = {
    "1": {"name": "🌸・Sakura Pink", "price": 500, "desc": "ยศสีชื่อชมพูซากุระ"},
    "2": {"name": "🌊・Ocean Blue", "price": 500, "desc": "ยศสีฟ้าน้ำทะเล"},
    "3": {"name": "🍀・Neon Green", "price": 500, "desc": "ยศสีเขียวนีออน"},
    "4": {"name": "⚡・Cyber Yellow", "price": 500, "desc": "ยศสีเหลืองไซเบอร์"},
    "5": {"name": "🔥・Crimson Red", "price": 500, "desc": "ยศสีแดงเพลิง"},
    "6": {"name": "☕・Cafe VIP", "price": 1500, "desc": "ยศฉายาแขกคนพิเศษของร้าน"},
    "7": {"name": "👑・Gamer Lord", "price": 3000, "desc": "ยศฉายาระดับตำนาน จอมราชันย์"}
}

# ----------------- 🛡️ Anti-Scam & Phishing Blacklists -----------------
SCAM_DOMAINS_PATTERNS = [
    r"dlscord\.", r"discorcl\.", r"discrod\.", r"discorde\.", r"discord-nitro\.",
    r"discord-app\.", r"discord-gift\.", r"discordgift\.", r"discordpromo\.",
    r"steamcommunlty\.", r"steamcomminuty\.", r"steamcommunityy\.", r"steam-giveaway\.",
    r"steamgift\.", r"steam-wallet\.", r"grabify\.link", r"iplogger\.org",
    r"2no\.co", r"yip\.su", r"iplis\.ru", r"ezstat\.ru", r"blasze\.com",
    r"free-nitro\.", r"nitro-free\.", r"nitro-gift\.", r"steam-promo\."
]

SCAM_KEYWORDS = [
    "free nitro", "nitro for free", "claim nitro", "nitro airdrop", "nitro gift",
    "steam gift card", "free steam", "claim 3 months", "discord nitro for free",
    "แจกไนโตรฟรี", "รับไนโตรฟรี", "แจกสกินฟรี", "แจกรหัสฟรี", "แจก gift card"
]

def check_is_scam(content: str):
    lower_content = content.lower()
    for pat in SCAM_DOMAINS_PATTERNS:
        if re.search(pat, lower_content):
            clean_pat = pat.replace(r'\.', '.')
            return True, f"ตรวจพบโดเมนอันตราย/ฟิชชิ่ง (`{clean_pat}`)"

    has_url = bool(re.search(r"https?://[^\s]+", lower_content))
    if has_url:
        for kw in SCAM_KEYWORDS:
            if kw in lower_content:
                return True, f"ตรวจพบคีย์เวิร์ดสแกมหลอกลวงพร้อมแนบลิงก์ (`{kw}`)"

    return False, ""

# ----------------- ⚔️ ระบบกิจกรรมนัดตี้ (Scheduled Events) -----------------
def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"counter": 1, "events": {}}
    return {"counter": 1, "events": {}}

def save_events(data):
    try:
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

events_db = load_events()

# ----------------- ⭐ ระบบบันทึกเครดิต -----------------
def load_reputation():
    if os.path.exists(REPUTATION_FILE):
        try:
            with open(REPUTATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_reputation(data):
    try:
        with open(REPUTATION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

user_reputation_db = load_reputation()

def get_user_rep_data(user_id_str):
    if user_id_str not in user_reputation_db:
        user_reputation_db[user_id_str] = {
            "voters": {}
        }
        save_reputation(user_reputation_db)
    
    data = user_reputation_db[user_id_str]
    if "voters" not in data:
        data["voters"] = {}
        save_reputation(user_reputation_db)
    return data

def calc_rep_counts(user_id_str):
    data = get_user_rep_data(user_id_str)
    voters = data.get("voters", {})
    pos = sum(1 for v in voters.values() if v.get("type") == "+1")
    neg = sum(1 for v in voters.values() if v.get("type") == "-1")
    score = pos - neg
    return score, list(voters.values())

def find_member_by_query(guild: discord.Guild, query: str):
    query = query.strip().lower()
    if query.startswith("<@") and query.endswith(">"):
        clean_id = query.replace("<@", "").replace("!", "").replace(">", "")
        if clean_id.isdigit():
            return guild.get_member(int(clean_id))

    if query.isdigit():
        m = guild.get_member(int(query))
        if m:
            return m

    for m in guild.members:
        if m.name.lower() == query or m.display_name.lower() == query:
            return m
        if query in m.display_name.lower() or query in m.name.lower():
            return m
    return None

async def update_seller_roles(guild: discord.Guild, member: discord.Member, score: int):
    good_role = discord.utils.get(guild.roles, name=GOOD_TRADER_ROLE) or discord.utils.get(guild.roles, name="⭐・พ่อค้าผ่านการยืนยัน")
    top_role = discord.utils.get(guild.roles, name=TOP_TRADER_ROLE) or discord.utils.get(guild.roles, name="👑・พ่อค้า VIP เครดิตดีเด่น")

    if score >= 15 and top_role:
        if top_role not in member.roles:
            try:
                await member.add_roles(top_role)
            except Exception:
                pass
    elif score >= 5 and good_role:
        if good_role not in member.roles:
            try:
                await member.add_roles(good_role)
            except Exception:
                pass
    elif score < 5:
        if good_role and good_role in member.roles:
            try:
                await member.remove_roles(good_role)
            except Exception:
                pass
        if top_role and top_role in member.roles:
            try:
                await member.remove_roles(top_role)
            except Exception:
                pass

# ----------------- ระบบบันทึกวันเกิด Birthdays -----------------
def load_birthdays():
    if os.path.exists(BIRTHDAYS_FILE):
        try:
            with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_birthdays(data):
    try:
        with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

user_birthdays_db = load_birthdays()

# ----------------- ระบบบันทึกเศรษฐกิจ Economy -----------------
def load_economy():
    if os.path.exists(ECONOMY_FILE):
        try:
            with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_economy(data):
    try:
        with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

user_economy_db = load_economy()

def get_user_coins(user_id_str):
    if user_id_str not in user_economy_db:
        user_economy_db[user_id_str] = {"coins": 200, "last_daily": 0}
        save_economy(user_economy_db)
    return user_economy_db[user_id_str].get("coins", 0)

def add_user_coins(user_id_str, amount):
    if user_id_str not in user_economy_db:
        user_economy_db[user_id_str] = {"coins": 200, "last_daily": 0}
    user_economy_db[user_id_str]["coins"] = user_economy_db[user_id_str].get("coins", 0) + amount
    save_economy(user_economy_db)
    return user_economy_db[user_id_str]["coins"]

# ----------------- ระบบบันทึกแมปรูปภาพ -----------------
def load_photo_map():
    if os.path.exists(PHOTO_MAP_FILE):
        try:
            with open(PHOTO_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_photo_map(data):
    try:
        with open(PHOTO_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

photo_message_map = load_photo_map()

# ----------------- ระบบจัดการฐานข้อมูล Level & XP -----------------
def load_user_levels():
    if os.path.exists(LEVELS_FILE):
        try:
            with open(LEVELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_levels(data):
    try:
        with open(LEVELS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

user_levels_db = load_user_levels()

def xp_for_level(lvl):
    return 100 * (lvl - 1) * lvl

def get_level_from_xp(xp):
    lvl = 1
    while xp >= xp_for_level(lvl + 1):
        lvl += 1
    return lvl

def format_nickname_with_level(base_name, level, job_emoji=""):
    emoji_prefix = f"{job_emoji} " if job_emoji else ""
    tag = f" [Lv.{level}]"
    available_len = 32 - len(tag) - len(emoji_prefix)
    clean_base = base_name[:max(5, available_len)].strip()
    return f"{emoji_prefix}{clean_base}{tag}"

def extract_base_name(display_name):
    name = display_name
    # ตัดแท็กเลเวลออก
    if name.startswith("[Lv.") and "]" in name:
        name = name.split("]", 1)[1].strip()
    if " [Lv." in name:
        name = name.split(" [Lv.")[0].strip()
    # ตัดอิโมจิอาชีพนำหน้าออก
    for info in RAGNAROK_JOBS.values():
        em = info["emoji"]
        if name.startswith(em):
            name = name[len(em):].strip()
    return name

def add_user_xp(user_id_str, base_name, xp_gain):
    if user_id_str not in user_levels_db:
        user_levels_db[user_id_str] = {
            "xp": 0,
            "level": 1,
            "base_name": base_name or "Gamer"
        }

    data = user_levels_db[user_id_str]
    if base_name:
        data["base_name"] = base_name

    old_lvl = data.get("level", 1)
    data["xp"] = data.get("xp", 0) + xp_gain
    new_lvl = get_level_from_xp(data["xp"])
    data["level"] = new_lvl

    save_user_levels(user_levels_db)
    is_level_up = new_lvl > old_lvl
    return is_level_up, new_lvl, data["xp"], data["base_name"]

def load_posted_news():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_posted_news(posted_set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_set), f, ensure_ascii=False)
    except Exception:
        pass

posted_news_links = load_posted_news()

# ==================== ⚔️ ระบบกิจกรรมนัดตี้ & จัดสมดุล 8 นาทีก่อนเริ่ม ====================

def render_event_announcement_embed(ev_data):
    ev_id = ev_data.get("event_id", 1)
    title = ev_data.get("title", "กิจกรรมกิลด์")
    game = ev_data.get("game", "ROM / ROX")
    time_str = ev_data.get("time_str", "20:00")
    party_size = ev_data.get("party_size", 6)
    creator_id = ev_data.get("creator_id")
    participants = ev_data.get("participants", {})
    status = ev_data.get("status", "open")

    total_joined = len(participants)
    healers = sum(1 for p in participants.values() if p.get("role") == "healer")
    tanks = sum(1 for p in participants.values() if p.get("role") == "tank")
    dps_count = sum(1 for p in participants.values() if p.get("role") == "dps")

    if status == "balanced":
        status_label = "✅ **ปิดรับสมัครและจัดตี้เรียบร้อยแล้ว** 🚀"
        color = discord.Color.brand_green()
        groups = ev_data.get("groups", [])
        if groups:
            group_lines = []
            for g_idx, grp in enumerate(groups, 1):
                m_lines = []
                for m in grp:
                    icon = "💖" if m["role"] == "healer" else ("🛡️" if m["role"] == "tank" else "🗡️")
                    role_label = "พระ" if m["role"] == "healer" else ("แทงค์" if m["role"] == "tank" else "DPS")
                    m_lines.append(f"• {icon} <@{m['user_id']}> (`{m.get('ign', m['name'])}` - {role_label})")
                group_lines.append(f"🏰 **[กลุ่มปาร์ตี้ที่ #{g_idx}] ({len(grp)}/{party_size} คน):**\n" + "\n".join(m_lines))
            groups_section = "\n\n───────────────────────────\n\n" + "\n\n".join(group_lines)
        else:
            groups_section = ""

        desc = (
            f"• 🎮 **เกม:** `{game}`\n"
            f"• ⏰ **เวลากิจกรรม:** **`{time_str} น.`**\n"
            f"• 👥 **ขนาดปาร์ตี้ต่อ 1 กลุ่ม:** **`{party_size} คน/ตี้`**\n"
            f"• 👑 **ผู้สร้างกิจกรรม:** <@{creator_id}>\n"
            f"• 📌 **สถานะ:** {status_label}\n\n"
            "───────────────────────────\n"
            f"📊 **ยอดสมาชิกร่วมกิจกรรมทั้งหมด (`{total_joined}` คน)**"
            + groups_section
            + "\n\n📩 *บอทได้ส่งสรุปตี้และห้องเสียงไปในแชทส่วนตัว (DM) ของทุกคนเรียบร้อยแล้วครับ!*"
        )
    else:
        status_label = f"⏳ **เปิดรับสมัครอยู่ (สรุปตี้ก่อนเริ่ม 8 นาที หรือกดจัดตี้ทันที)**"
        color = discord.Color.from_rgb(255, 107, 129)
        desc = (
            f"• 🎮 **เกม:** `{game}`\n"
            f"• ⏰ **เวลากิจกรรม:** **`{time_str} น.`**\n"
            f"• 👥 **ขนาดปาร์ตี้ต่อ 1 กลุ่ม:** **`{party_size} คน/ตี้`**\n"
            f"• 👑 **ผู้สร้างกิจกรรม:** <@{creator_id}>\n"
            f"• 📌 **สถานะ:** {status_label}\n\n"
            "───────────────────────────\n"
            f"📊 **ยอดสมาชิกลงชื่อปัจจุบัน (`{total_joined}` คน):**\n"
            f"• 💖 **พระ / ซัพพอร์ต (Healer):** `{healers}` คน\n"
            f"• 🛡️ **แทงค์ / ไนท์ (Tank):** `{tanks}` คน\n"
            f"• 🗡️ **ดาเมจ (DPS):** `{dps_count}` คน\n\n"
            "───────────────────────────\n"
            "⏰ **ระบบจะสรุปตี้ก่อนเริ่ม 8 นาที หรือผู้สร้างกดปุ่ม [⚡ จัดตี้ทันที] ด้านล่างได้เลยครับ:**"
        )

    embed = discord.Embed(
        title=f"📢 [กิจกรรมนัดตี้] {title} • {time_str} น.",
        description=desc,
        color=color
    )
    embed.set_footer(text=f"Gamers' Café Event System • Event #{ev_id}")
    return embed

async def update_event_messages(guild, ev_data):
    """
    🔄 อัปเดตการ์ดกิจกรรมในห้อง #จัดตี้เกม และ #คุยเล่น แบบเรียลไทม์เมื่อมียอดคนลงชื่อเพิ่ม หรือเมื่อจัดตี้เสร็จ
    """
    if not guild or not ev_data:
        return
    embed = render_event_announcement_embed(ev_data)
    is_closed = ev_data.get("status") == "balanced"
    view = EventActionView(ev_data.get("event_id", 1), is_closed=is_closed)
    
    # 1. อัปเดตห้อง #⚔️・จัดตี้เกม
    party_mid = ev_data.get("party_msg_id") or ev_data.get("channel_msg_id")
    if party_mid:
        party_ch = guild.get_channel(PARTY_CHANNEL_ID)
        if party_ch:
            try:
                msg = await party_ch.fetch_message(party_mid)
                if msg:
                    await msg.edit(embed=embed, view=view)
            except Exception:
                pass

    # 2. อัปเดตห้อง #💬・คุยเล่น
    chat_mid = ev_data.get("chat_msg_id")
    if chat_mid:
        chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
        if chat_ch:
            try:
                msg = await chat_ch.fetch_message(chat_mid)
                if msg:
                    await msg.edit(embed=embed, view=view)
            except Exception:
                pass

class EventSignUpModal(Modal, title="⚔️ ลงชื่อเข้าร่วมกิจกรรม"):
    def __init__(self, event_id: int, default_role: str = "ดาเมจ", default_ign: str = ""):
        super().__init__()
        self.event_id = event_id

        self.role_input = TextInput(
            label="1. ตำแหน่งของคุณ (พระ / แทงค์ / ดาเมจ)",
            placeholder="พิมพ์: พระ หรือ แทงค์/ไนท์ หรือ ดาเมจ",
            default=default_role,
            min_length=1,
            max_length=20,
            required=True
        )
        self.ign_input = TextInput(
            label="2. ชื่อในเกม (In-Game Name / IGN)",
            placeholder="เช่น Yuna, KarnZaa, NONT#TH1",
            default=default_ign or "Gamer",
            min_length=1,
            max_length=25,
            required=True
        )
        self.add_item(self.role_input)
        self.add_item(self.ign_input)

    async def on_submit(self, interaction: discord.Interaction):
        role_raw = self.role_input.value.strip().lower()
        user_ign = self.ign_input.value.strip()
        guild = bot.get_guild(TARGET_GUILD_ID)

        if "พระ" in role_raw or "heal" in role_raw or "bishop" in role_raw or "ซัพ" in role_raw:
            my_role = "healer"
            role_th = "💖 พระ / ซัพพอร์ต (Healer)"
        elif "แทงค์" in role_raw or "tank" in role_raw or "knight" in role_raw or "ชน" in role_raw or "ไนท์" in role_raw:
            my_role = "tank"
            role_th = "🛡️ ไนท์ / แทงค์ (Tank)"
        else:
            my_role = "dps"
            role_th = "🗡️ ดาเมจ (DPS)"

        ev_id_str = str(self.event_id)
        ev_data = events_db.get("events", {}).get(ev_id_str)
        if not ev_data:
            await interaction.response.send_message("❌ ไม่พบข้อมูลกิจกรรมนี้ในระบบ", ephemeral=True)
            return

        if ev_data.get("status") == "balanced":
            await interaction.response.send_message("⚠️ กิจกรรมนี้ปิดรับสมัครและจัดตี้ไปแล้วครับ!", ephemeral=True)
            return

        # 🚫 ตรวจสอบการลงชื่อซ้ำ
        uid_str = str(interaction.user.id)
        participants = ev_data.get("participants", {})
        if uid_str in participants:
            existing = participants[uid_str]
            role_map = {"healer": "💖 พระ / ซัพพอร์ต", "tank": "🛡️ ไนท์ / แทงค์", "dps": "🗡️ ดาเมจ"}
            ex_role_th = role_map.get(existing.get("role"), existing.get("role"))
            await interaction.response.send_message(
                f"⚠️ **คุณได้ลงชื่อเข้าร่วมกิจกรรม [{ev_data.get('title')}] ไว้แล้วครับ!**\n\n"
                f"• 👤 **ตำแหน่งที่ลงไว้:** `{ex_role_th}`\n"
                f"• 🎮 **ชื่อในเกม (IGN):** `{existing.get('ign', '-')}`\n\n"
                f"💡 *ระบบไม่อนุญาตให้ลงชื่อซ้ำครับ รอระบบจัดกลุ่มตี้ก่อนเริ่มกิจกรรม 8 นาทีได้เลยครับ!*",
                ephemeral=True
            )
            return

        # 🔍 ตรวจสอบและอัปเดตชื่อใน Server ให้ตรงกับชื่อในเกม (IGN)
        member = guild.get_member(interaction.user.id) if guild else None
        nick_change_msg = ""
        if member:
            current_display = member.display_name
            # เช็คว่าชื่อในเกมตรงกับชื่อเล่นในเซิร์ฟเวอร์หรือไม่
            if user_ign.lower() not in current_display.lower():
                uid = str(member.id)
                current_data = user_levels_db.get(uid, {"xp": 0, "level": 1})
                current_lvl = current_data.get("level", 1)

                raw_base = extract_base_name(current_display)
                first_nick = raw_base.split("•")[0].strip() if "•" in raw_base else raw_base
                new_base_name = f"{first_nick} • {user_ign}"
                
                current_data["base_name"] = new_base_name
                user_levels_db[uid] = current_data
                save_user_levels(user_levels_db)

                job_em = current_data.get("job_emoji", "")
                final_name = format_nickname_with_level(new_base_name, current_lvl, job_em)
                try:
                    await member.edit(nick=final_name)
                    nick_change_msg = f"\n✨ **บอทได้อัปเดตชื่อในเซิร์ฟเวอร์ของคุณให้ตรงกับชื่อในเกมเป็น:** `{final_name}`"
                    print(f"[+] อัปเดตชื่อ {member.name} เป็น '{final_name}' ตาม IGN '{user_ign}'")
                except Exception:
                    pass

        # บันทึกผู้เข้าร่วม
        participants[uid_str] = {
            "user_id": interaction.user.id,
            "name": interaction.user.display_name,
            "ign": user_ign,
            "role": my_role,
            "signed_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        ev_data["participants"] = participants
        save_events(events_db)

        # 🔄 อัปเดตยอดสะสมบนการ์ดในทุกห้องแบบเรียลไทม์
        if guild:
            await update_event_messages(guild, ev_data)

        await interaction.response.send_message(
            f"✅ **ลงชื่อเข้าร่วมกิจกรรม [{ev_data.get('title')}] สำเร็จ!**\n"
            f"• 👤 **ตำแหน่งของคุณ:** `{role_th}`\n"
            f"• 🎮 **ชื่อในเกม (IGN):** `{user_ign}`{nick_change_msg}\n\n"
            f"⏰ **บอทจะทำการจัดกลุ่มให้สมดุลและแจ้งเตือนคุณก่อนเริ่มกิจกรรม 8 นาทีครับ!** ⚔️",
            ephemeral=True
        )
        print(f"[⚔️ Event Sign-up] {interaction.user.name} ลงชื่อกิจกรรม #{self.event_id} ({my_role} | IGN: {user_ign})")

class EventActionView(View):
    def __init__(self, event_id: int, is_closed: bool = False):
        super().__init__(timeout=None)
        self.event_id = event_id

        if not is_closed:
            self.add_item(Button(
                label="⚔️ ลงชื่อเข้าร่วมกิจกรรม",
                style=discord.ButtonStyle.success,
                custom_id=f"btn_ev_signup_{event_id}",
                emoji="📝"
            ))
            self.add_item(Button(
                label="⚡ จัดตี้ทันที",
                style=discord.ButtonStyle.primary,
                custom_id=f"btn_ev_instant_balance_{event_id}",
                emoji="🚀"
            ))
        self.add_item(Button(
            label="📋 ดูรายชื่อคนที่ลงแล้ว",
            style=discord.ButtonStyle.secondary,
            custom_id=f"btn_ev_view_roster_{event_id}",
            emoji="👥"
        ))

class CreateEventModal(Modal, title="📢 สร้างกิจกรรมนัดตี้ & ประกาศทุกคน"):
    title_input = TextInput(
        label="1. ชื่อกิจกรรม / ดันเจี้ยน",
        placeholder="เช่น ล่าบอส 100 ชั้น, KVM กิลด์, หอคอยประจำสัปดาห์",
        min_length=2,
        max_length=60,
        required=True
    )
    time_input = TextInput(
        label="2. เวลากิจกรรมวันนี้ (HH:MM เช่น 20:00)",
        placeholder="เช่น 20:00 หรือ 21:30 หรือ 19:45",
        min_length=3,
        max_length=10,
        required=True
    )
    size_input = TextInput(
        label="3. จำนวนสมาชิกต่อตี้ (Party Size)",
        placeholder="ใส่ตัวเลข เช่น 6 หรือ 5 หรือ 12",
        default="6",
        min_length=1,
        max_length=3,
        required=True
    )
    game_input = TextInput(
        label="4. เกมที่เล่น (Game)",
        placeholder="เช่น ROM / ROX, Ragnarok, ทั่วไป",
        default="ROM / ROX",
        min_length=2,
        max_length=30,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # ⚡ Def immediate response เพื่อป้องกัน Interaction Timeout 3 วินาที
        await interaction.response.defer(ephemeral=True)

        ev_title = self.title_input.value.strip()
        ev_time_str = self.time_input.value.strip().replace(".", ":")
        ev_size_raw = self.size_input.value.strip()
        ev_game = self.game_input.value.strip()

        try:
            ev_size = int(ev_size_raw)
            if ev_size < 2 or ev_size > 30:
                ev_size = 6
        except ValueError:
            ev_size = 6

        now = datetime.datetime.now()
        time_parts = ev_time_str.split(":")
        try:
            ev_hour = int(time_parts[0])
            ev_minute = int(time_parts[1])
            target_dt = now.replace(hour=ev_hour, minute=ev_minute, second=0, microsecond=0)
            if target_dt < now:
                target_dt += datetime.timedelta(days=1)
        except Exception:
            target_dt = now + datetime.timedelta(hours=2)
            ev_time_str = target_dt.strftime("%H:%M")

        ev_timestamp = target_dt.timestamp()
        balance_timestamp = ev_timestamp - (8 * 60)

        ev_id = events_db.get("counter", 1)
        events_db["counter"] = ev_id + 1

        ev_data = {
            "event_id": ev_id,
            "title": ev_title,
            "game": ev_game,
            "time_str": ev_time_str,
            "event_timestamp": ev_timestamp,
            "balance_timestamp": balance_timestamp,
            "party_size": ev_size,
            "creator_id": interaction.user.id,
            "status": "open",
            "participants": {},
            "created_at": now.strftime("%d/%m/%Y %H:%M")
        }
        events_db["events"][str(ev_id)] = ev_data
        save_events(events_db)

        guild = interaction.guild
        embed = render_event_announcement_embed(ev_data)

        # 1. ส่งประกาศลงห้อง #⚔️・จัดตี้เกม
        party_ch = guild.get_channel(PARTY_CHANNEL_ID)
        ch_msg_id = None
        if party_ch:
            m1 = await party_ch.send(
                content=f"📢 **ประกาศกิจกรรมใหม่!** โดย {interaction.user.mention} (เริ่ม `{ev_time_str} น.`)",
                embed=embed,
                view=EventActionView(ev_id)
            )
            ch_msg_id = m1.id

        # 2. ส่งประกาศลงห้อง #คุยเล่น
        chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
        chat_msg_id = None
        if chat_ch:
            m2 = await chat_ch.send(
                content=f"⚔️ **มีนัดตี้กิจกรรม [{ev_title}] วันนี้เวลา `{ev_time_str} น.`!** กดปุ่มลงชื่อด้านล่างได้เลยครับ @everyone",
                embed=embed,
                view=EventActionView(ev_id)
            )
            chat_msg_id = m2.id

        ev_data["party_msg_id"] = ch_msg_id
        ev_data["channel_msg_id"] = ch_msg_id
        ev_data["chat_msg_id"] = chat_msg_id
        save_events(events_db)

        # 3. ส่งข้อความ DM หาผู้ใช้ทุกคนในเซิร์ฟเวอร์แบบ Asynchronous Background
        dm_count = 0
        for m in guild.members:
            if m.bot:
                continue
            dm_embed = discord.Embed(
                title=f"⚔️ [Gamers' Café] ชวนร่วมกิจกรรม: {ev_title}",
                description=(
                    f"สวัสดีครับคุณ **{m.display_name}**! 🎮✨\n\n"
                    f"วันนี้มีนัดจัดปาร์ตี้กิจกรรม **{ev_title}** (`{ev_game}`)\n"
                    f"⏰ **เวลากิจกรรม:** **`{ev_time_str} น.`**\n"
                    f"👥 **ขนาดปาร์ตี้:** **`{ev_size} คน/ตี้`** (จัดสมดุลพระ/แทงค์/ดาเมจ)\n\n"
                    "───────────────────────────\n"
                    "⏰ **ระบบจะสรุปตี้และแจ้งกลุ่มให้ทราบก่อนเริ่ม 8 นาที**\n"
                    "👇 **คลิกปุ่มด้านล่างนี้เพื่อลงชื่อเข้าร่วมได้ทันที:**"
                ),
                color=discord.Color.brand_green()
            )
            dm_embed.set_footer(text=f"Gamers' Café Event #{ev_id}")
            try:
                await m.send(embed=dm_embed, view=EventActionView(ev_id))
                dm_count += 1
                await asyncio.sleep(0.1)
            except Exception:
                pass

        await interaction.followup.send(
            f"🎉 **ประกาศกิจกรรม [{ev_title}] สำเร็จแล้ว!**\n"
            f"• 📢 โพสต์ลงในห้อง <#{CHAT_CHANNEL_ID}> และ <#{PARTY_CHANNEL_ID}>\n"
            f"• 📩 ส่งข้อความ DM ไปหาเพื่อนๆ ในเซิร์ฟเวอร์ `{dm_count}` คน\n"
            f"• ⏰ **บอทจะสรุปตี้อัตโนมัติก่อนเริ่ม 8 นาที (เวลา {datetime.datetime.fromtimestamp(balance_timestamp).strftime('%H:%M')} น.) ครับ!** 🚀"
        )
        print(f"[📢 Event Created] {interaction.user.name} สร้างกิจกรรม #{ev_id}: {ev_title} ({ev_time_str} น.)")

# ----------------- 🧠 ฟังก์ชันคำนวณจัดตี้ให้สมดุล (Smart Role Balancing Algorithm) -----------------
async def execute_smart_party_balance(guild: discord.Guild, ev_data):
    ev_id = ev_data.get("event_id", 1)
    title = ev_data.get("title", "กิจกรรม")
    game = ev_data.get("game", "ROM / ROX")
    party_size = ev_data.get("party_size", 6)
    participants = list(ev_data.get("participants", {}).values())

    if not participants:
        print(f"[i] กิจกรรม #{ev_id} ไม่มีผู้เข้าร่วม ข้ามการจัดตี้")
        ev_data["status"] = "balanced"
        save_events(events_db)
        return

    healers = [p for p in participants if p["role"] == "healer"]
    tanks = [p for p in participants if p["role"] == "tank"]
    dps_list = [p for p in participants if p["role"] == "dps"]

    total_players = len(participants)
    num_groups = max(1, math.ceil(total_players / party_size))

    groups = [[] for _ in range(num_groups)]

    random.shuffle(healers)
    for idx, h in enumerate(healers):
        groups[idx % num_groups].append(h)

    random.shuffle(tanks)
    for idx, t in enumerate(tanks):
        groups[idx % num_groups].append(t)

    random.shuffle(dps_list)
    for d in dps_list:
        min_group = min(groups, key=lambda g: len(g))
        min_group.append(d)

    ev_data["status"] = "balanced"
    ev_data["groups"] = groups
    save_events(events_db)

    voice_cat = discord.utils.get(guild.categories, name="VOICE CHATS")
    group_summary_lines = []

    for g_idx, grp in enumerate(groups, 1):
        g_name = f"🔊 ตี้ {g_idx}: {title}"
        created_vc = None
        try:
            created_vc = await guild.create_voice_channel(
                name=g_name,
                category=voice_cat,
                user_limit=party_size
            )
            temp_party_rooms.add(created_vc.id)
            print(f"[+] สร้างห้องเสียงตี้กิจกรรม: {g_name}")
        except Exception:
            pass

        vc_link = f"[👉 เข้าห้องเสียง: {g_name}]({created_vc.jump_url})" if created_vc else ""

        m_lines = []
        for m in grp:
            icon = "💖" if m["role"] == "healer" else ("🛡️" if m["role"] == "tank" else "🗡️")
            role_name = "พระ" if m["role"] == "healer" else ("แทงค์" if m["role"] == "tank" else "DPS")
            m_lines.append(f"{icon} <@{m['user_id']}> (`{m.get('ign', m['name'])}` - {role_name})")

        grp_text = f"**🏰 [กลุ่มที่ #{g_idx}] ({len(grp)}/{party_size} คน):**\n" + "\n".join(m_lines)
        if vc_link:
            grp_text += f"\n{vc_link}"
        group_summary_lines.append(grp_text)

        for m in grp:
            member_obj = guild.get_member(m["user_id"])
            if not member_obj:
                continue

            my_role_th = "💖 พระ / ซัพพอร์ต (Healer)" if m["role"] == "healer" else ("🛡️ ไนท์ / แทงค์ (Tank)" if m["role"] == "tank" else "🗡️ ดาเมจ (DPS)")
            dm_embed = discord.Embed(
                title=f"⏰ [แจ้งเตือนก่อนเริ่ม 8 นาที] สรุปปาร์ตี้กิจกรรม: {title}",
                description=(
                    f"สวัสดีครับคุณ **{member_obj.display_name}**! 🚀\n"
                    f"กิจกรรม **{title}** กำลังจะเริ่มในอีก **8 นาที** แล้วครับ!\n\n"
                    "───────────────────────────\n"
                    f"• 🏷️ **กลุ่มของคุณ:** **`กลุ่มที่ #{g_idx}`**\n"
                    f"• 👤 **ตำแหน่งที่คุณเล่น:** **`{my_role_th}`**\n"
                    f"• 🎮 **ชื่อในเกม (IGN):** `{m.get('ign', member_obj.display_name)}`\n\n"
                    "───────────────────────────\n"
                    "👥 **รายชื่อเพื่อนร่วมตี้ของคุณ:**\n"
                    + "\n".join(m_lines)
                    + (f"\n\n───────────────────────────\n🔊 **ห้องเสียงของกลุ่มคุณ:**\n{vc_link}" if vc_link else "")
                ),
                color=discord.Color.gold()
            )
            dm_embed.set_footer(text=f"Gamers' Café Event Matching • กลุ่มที่ #{g_idx}")
            try:
                await member_obj.send(embed=dm_embed)
            except Exception:
                pass

    summary_embed = discord.Embed(
        title=f"📋 [สรุปผลการจัดปาร์ตี้] {title} (ก่อนเริ่ม 8 นาที)",
        description=(
            f"🎉 **บอทได้จัดสายอาชีพและกลุ่มให้สมดุลเรียบร้อยแล้วครับ!** ⚔️\n\n"
            + "\n\n───────────────────────────\n\n".join(group_summary_lines)
            + "\n\n📩 *บอทได้ส่งข้อความแชทส่วนตัว (DM) แจ้งทุกคนพร้อมระบุห้องเสียงแล้วครับ!*"
        ),
        color=discord.Color.brand_green()
    )
    summary_embed.set_footer(text=f"Gamers' Café Auto-Balancing • Event #{ev_id}")

    chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
    if chat_ch:
        await chat_ch.send(content=f"🔔 **สรุปผลจัดตี้กิจกรรม [{title}] เรียบร้อยแล้วครับ!** @everyone", embed=summary_embed)

    party_ch = guild.get_channel(PARTY_CHANNEL_ID)
    if party_ch:
        await party_ch.send(embed=summary_embed)

    print(f"[✅ Auto-Balancing] จัดตี้กิจกรรม #{ev_id} สำเร็จ ({num_groups} กลุ่ม • รวม {total_players} คน)")

@tasks.loop(seconds=30)
async def event_scheduler_loop():
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild:
        return

    now_ts = time.time()
    for ev_id_str, ev_data in list(events_db.get("events", {}).items()):
        if ev_data.get("status") == "open":
            balance_ts = ev_data.get("balance_timestamp", 0)
            if now_ts >= balance_ts:
                try:
                    await execute_smart_party_balance(guild, ev_data)
                except Exception as e:
                    print(f"[!] เกิดข้อผิดพลาดในการจัดตี้กิจกรรม #{ev_id_str}: {e}")

# ==================== GUI View Components ====================

class PartyHubView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 ดูกิจกรรมที่เปิดรับสมัครอยู่",
        style=discord.ButtonStyle.primary,
        custom_id="btn_hub_view_active_events",
        emoji="🔍",
        row=0
    )
    async def btn_view_events(self, interaction: discord.Interaction, button: Button):
        active_evs = [ev for ev in events_db.get("events", {}).values() if ev.get("status") == "open"]
        if not active_evs:
            await interaction.response.send_message("ℹ️ **ขณะนี้ยังไม่มีกิจกรรมที่เปิดรับสมัครอยู่ครับ**\n👉 สร้างกิจกรรมใหม่ได้ที่เมนู **'Events (กิจกรรม)'** ด้านบนสุดของเซิร์ฟเวอร์ได้เลยครับ!", ephemeral=True)
            return

        lines = []
        for ev in active_evs:
            eid = ev.get("event_id")
            title = ev.get("title")
            time_str = ev.get("time_str")
            joined = len(ev.get("participants", {}))
            size = ev.get("party_size", 6)
            lines.append(f"• ⚔️ **[กิจกรรม #{eid}] {title}** — ⏰ `{time_str} น.` (ลงชื่อแล้ว `{joined}` คน • ตี้ละ `{size}` คน)")

        embed = discord.Embed(
            title="📋 รายการกิจกรรมที่เปิดรับสมัครอยู่",
            description="\n\n".join(lines) + "\n\n💡 *ระบบจะปิดรับสมัครและสรุปตี้ให้ก่อนเวลาเริ่ม 8 นาทีครับ*",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ItemBuyView(View):
    def __init__(self, item_id: str = "1", price: int = 500):
        super().__init__(timeout=None)
        btn_buy = Button(
            label=f"🛍️ แลกซื้อยศนี้ ({price:,} Coins)",
            style=discord.ButtonStyle.success,
            custom_id=f"btn_forum_buy_{item_id}"
        )
        self.add_item(btn_buy)
        btn_wallet = Button(
            label="💰 เช็คเหรียญของฉัน",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_forum_check_wallet"
        )
        self.add_item(btn_wallet)

class DailyClaimView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🎁 รับเหรียญรายวันฟรี", style=discord.ButtonStyle.success, custom_id="btn_direct_claim_daily", emoji="🪙"))
        self.add_item(Button(label="💰 เช็คยอดเหรียญของฉัน", style=discord.ButtonStyle.secondary, custom_id="btn_direct_check_balance", emoji="👛"))

class ROJobSelect(discord.ui.Select):
    def __init__(self, target_user_id: int = 0):
        options = []
        for jkey, info in RAGNAROK_JOBS.items():
            options.append(discord.SelectOption(
                label=info["name"],
                value=jkey,
                description=info["desc"][:50],
                emoji=info["emoji"]
            ))
        super().__init__(
            placeholder="🎮 คลิกที่นี่เพื่อเลือกอาชีพ Ragnarok ของคุณ...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_ro_job_choice"
        )
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction):
        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            await interaction.response.send_message("❌ ไม่พบเซิร์ฟเวอร์", ephemeral=True)
            return

        try:
            member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        except Exception:
            member = None

        if not member:
            await interaction.response.send_message("❌ ไม่พบข้อมูลสมาชิกในเซิร์ฟเวอร์", ephemeral=True)
            return

        selected_key = self.values[0]
        job_info = RAGNAROK_JOBS.get(selected_key)
        if not job_info:
            return

        job_emoji = job_info["emoji"]
        job_name = job_info["name"]
        job_role_name = job_info["role"]

        # 1. บันทึกข้อมูลลง Database
        uid = str(member.id)
        u_data = user_levels_db.get(uid, {"xp": 0, "level": 1, "base_name": extract_base_name(member.display_name)})
        u_data["ro_job"] = selected_key
        u_data["job_emoji"] = job_emoji
        user_levels_db[uid] = u_data
        save_user_levels(user_levels_db)

        # 2. มอบยศเกมหลัก Ragnarok
        ro_main_role = discord.utils.get(guild.roles, name="🗡️・Ragnarok") or discord.utils.find(lambda r: "ragnarok" in r.name.lower(), guild.roles)
        if ro_main_role and ro_main_role not in member.roles:
            try:
                await member.add_roles(ro_main_role)
            except Exception:
                pass

        # 3. ลบยศอาชีพเก่าอื่นๆ ของ RO ออก
        all_ro_role_names = {info["role"] for info in RAGNAROK_JOBS.values()}
        old_ro_roles = [r for r in member.roles if r.name in all_ro_role_names and r.name != job_role_name]
        if old_ro_roles:
            try:
                await member.remove_roles(*old_ro_roles)
            except Exception:
                pass

        # 4. มอบยศอาชีพใหม่ (สร้างยศอัตโนมัติหากยังไม่มี)
        job_role = discord.utils.get(guild.roles, name=job_role_name)
        if not job_role:
            try:
                job_role = await guild.create_role(name=job_role_name, color=discord.Color.blue(), reason="Auto-created Ragnarok Job Role")
            except Exception:
                pass
        if job_role and job_role not in member.roles:
            try:
                await member.add_roles(job_role)
            except Exception:
                pass

        # 5. เปลี่ยนชื่อเล่นให้มีอิโมจิอาชีพนำหน้า
        base_name = u_data.get("base_name") or extract_base_name(member.display_name)
        current_lvl = u_data.get("level", 1)
        final_nick = format_nickname_with_level(base_name, current_lvl, job_emoji)
        try:
            await member.edit(nick=final_nick)
        except Exception:
            pass

        embed = discord.Embed(
            title=f"⚔️ เลือกอาชีพ Ragnarok สำเร็จ! {job_emoji}",
            description=(
                f"ยินดีด้วยครับคุณ {member.mention}! ✨\n\n"
                f"🏷️ **อาชีพที่เลือก:** `{job_name}` ({job_emoji})\n"
                f"👑 **ยศที่ได้รับ:** {job_role.mention if job_role else f'`{job_role_name}`'}\n"
                f"👤 **ชื่อใหม่ในเซิร์ฟเวอร์:** `{final_nick}`\n\n"
                f"💡 *สามารถเปลี่ยนอาชีพได้ตลอดเวลาโดยพิมพ์คำสั่ง `!rojob` ในห้องคุยเล่นครับ*"
            ),
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"[+] {member.name} เลือกอาชีพ Ragnarok: {job_name} ({job_emoji}) -> ชื่อ: {final_nick}")

class ROJobSelectView(View):
    def __init__(self, target_user_id: int = 0):
        super().__init__(timeout=None)
        self.add_item(ROJobSelect(target_user_id))

class ROJobButton(Button):
    def __init__(self, job_key: str, info: dict, row: int):
        label = info["name"].split("/")[0].strip()
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            emoji=info["emoji"],
            custom_id=f"btn_rojob_direct_{job_key}",
            row=row
        )
        self.job_key = job_key
        self.job_info = info

    async def callback(self, interaction: discord.Interaction):
        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            await interaction.response.send_message("❌ ไม่พบเซิร์ฟเวอร์", ephemeral=True)
            return

        try:
            member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        except Exception:
            member = None

        if not member:
            await interaction.response.send_message("❌ ไม่พบข้อมูลสมาชิกในเซิร์ฟเวอร์", ephemeral=True)
            return

        job_emoji = self.job_info["emoji"]
        job_name = self.job_info["name"]
        job_role_name = self.job_info["role"]

        # 1. บันทึกข้อมูลลง Database
        uid = str(member.id)
        u_data = user_levels_db.get(uid, {"xp": 0, "level": 1, "base_name": extract_base_name(member.display_name)})
        u_data["ro_job"] = self.job_key
        u_data["job_emoji"] = job_emoji
        user_levels_db[uid] = u_data
        save_user_levels(user_levels_db)

        # 2. มอบยศเกมหลัก Ragnarok
        ro_main_role = discord.utils.get(guild.roles, name="🗡️・Ragnarok") or discord.utils.find(lambda r: "ragnarok" in r.name.lower(), guild.roles)
        if ro_main_role and ro_main_role not in member.roles:
            try:
                await member.add_roles(ro_main_role)
            except Exception:
                pass

        # 3. ลบยศอาชีพเก่าอื่นๆ ของ RO ออก
        all_ro_role_names = {info["role"] for info in RAGNAROK_JOBS.values()}
        old_ro_roles = [r for r in member.roles if r.name in all_ro_role_names and r.name != job_role_name]
        if old_ro_roles:
            try:
                await member.remove_roles(*old_ro_roles)
            except Exception:
                pass

        # 4. มอบยศอาชีพใหม่ (สร้างยศอัตโนมัติหากยังไม่มี)
        job_role = discord.utils.get(guild.roles, name=job_role_name)
        if not job_role:
            try:
                job_role = await guild.create_role(name=job_role_name, color=discord.Color.blue(), reason="Auto-created Ragnarok Job Role")
            except Exception:
                pass
        if job_role and job_role not in member.roles:
            try:
                await member.add_roles(job_role)
            except Exception:
                pass

        # 5. เปลี่ยนชื่อเล่นให้มีอิโมจิอาชีพนำหน้า
        base_name = u_data.get("base_name") or extract_base_name(member.display_name)
        current_lvl = u_data.get("level", 1)
        final_nick = format_nickname_with_level(base_name, current_lvl, job_emoji)
        try:
            await member.edit(nick=final_nick)
        except Exception:
            pass

        embed = discord.Embed(
            title=f"⚔️ เลือกอาชีพ Ragnarok สำเร็จ! {job_emoji}",
            description=(
                f"ยินดีด้วยครับคุณ {member.mention}! ✨\n\n"
                f"🏷️ **อาชีพที่เลือก:** `{job_name}` ({job_emoji})\n"
                f"👑 **ยศที่ได้รับ:** {job_role.mention if job_role else f'`{job_role_name}`'}\n"
                f"👤 **ชื่อใหม่ในเซิร์ฟเวอร์:** `{final_nick}`\n\n"
                f"💡 *สามารถกดปุ่มเปลี่ยนอาชีพได้ตลอดเวลาครับ!*"
            ),
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"[+] {member.name} กดปุ่มเลือกอาชีพ: {job_name} ({job_emoji}) -> ชื่อ: {final_nick}")

class QuickGameRoleButton(Button):
    def __init__(self, game_key: str, role_name: str, emoji: str, row: int):
        super().__init__(
            label=role_name.split("・")[-1],
            style=discord.ButtonStyle.secondary,
            emoji=emoji,
            custom_id=f"btn_quick_role_{game_key}",
            row=row
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            await interaction.response.send_message("❌ ไม่พบเซิร์ฟเวอร์", ephemeral=True)
            return
        try:
            member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        except Exception:
            member = None
        if not member:
            await interaction.response.send_message("❌ ไม่พบสมาชิกในเซิร์ฟเวอร์", ephemeral=True)
            return
        role = discord.utils.get(guild.roles, name=self.role_name) or discord.utils.find(lambda r: self.label.lower() in r.name.lower(), guild.roles)
        if not role:
            try:
                role = await guild.create_role(name=self.role_name, reason="Auto-created Game Role")
            except Exception:
                pass
        if role:
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.response.send_message(f"➖ ยกเลิกยศ `{role.name}` เรียบร้อยแล้วครับ", ephemeral=True)
            else:
                await member.add_roles(role)
                await interaction.response.send_message(f"➕ รับยศ `{role.name}` เรียบร้อยแล้วครับ! 🎉", ephemeral=True)

class RolesOnlyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        ro_jobs_list = list(RAGNAROK_JOBS.items())
        # Row 0 (5 jobs)
        for jkey, info in ro_jobs_list[0:5]:
            self.add_item(ROJobButton(jkey, info, row=0))
        # Row 1 (5 jobs)
        for jkey, info in ro_jobs_list[5:10]:
            self.add_item(ROJobButton(jkey, info, row=1))
        # Row 2 (4 jobs)
        for jkey, info in ro_jobs_list[10:14]:
            self.add_item(ROJobButton(jkey, info, row=2))

        # Row 3: ปุ่มรับยศเกมอื่นๆ
        self.add_item(QuickGameRoleButton("val", "🎯・Valorant", "🎯", 3))
        self.add_item(QuickGameRoleButton("rov", "⚔️・RoV", "⚔️", 3))
        self.add_item(QuickGameRoleButton("mc", "🧱・Minecraft", "🧱", 3))
        self.add_item(QuickGameRoleButton("roblox", "🎲・Roblox", "🎲", 3))
        self.add_item(QuickGameRoleButton("genshin", "✨・Genshin Impact", "✨", 3))

class DMRegisterView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # Row 0: ปุ่มตั้งชื่อเล่น
        self.add_item(Button(label="🟢 ตั้งชื่อเล่น & ปลดล็อคห้อง (คลิกที่นี่)", style=discord.ButtonStyle.success, custom_id="btn_dm_profile_modal_spaced", row=0))
        
        # Rows 1-3: ปุ่มเลือกอาชีพ RO ครบทุกสาย
        ro_jobs_list = list(RAGNAROK_JOBS.items())
        # Row 1 (5 jobs)
        for jkey, info in ro_jobs_list[0:5]:
            self.add_item(ROJobButton(jkey, info, row=1))
        # Row 2 (5 jobs)
        for jkey, info in ro_jobs_list[5:10]:
            self.add_item(ROJobButton(jkey, info, row=2))
        # Row 3 (4 jobs)
        for jkey, info in ro_jobs_list[10:14]:
            self.add_item(ROJobButton(jkey, info, row=3))

        # Row 4: ปุ่มรับยศเกมอื่นๆ
        self.add_item(QuickGameRoleButton("val", "🎯・Valorant", "🎯", 4))
        self.add_item(QuickGameRoleButton("rov", "⚔️・RoV", "⚔️", 4))
        self.add_item(QuickGameRoleButton("mc", "🧱・Minecraft", "🧱", 4))
        self.add_item(QuickGameRoleButton("roblox", "🎲・Roblox", "🎲", 4))
        self.add_item(QuickGameRoleButton("genshin", "✨・Genshin Impact", "✨", 4))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get("custom_id") == "btn_dm_profile_modal_spaced":
            await interaction.response.send_modal(GamerProfileModal())
            return False
        return True

class GamerProfileModal(Modal, title="📝 ตั้งชื่อเล่น & ข้อมูลเกม"):
    nickname_input = TextInput(
        label="1. ชื่อเล่นของคุณ (Nickname)",
        placeholder="เช่น โจ้, กานต์, นนท์, Ploy",
        min_length=1,
        max_length=20,
        required=True
    )
    ign_input = TextInput(
        label="2. ชื่อในเกม (In-Game Name / IGN)",
        placeholder="เช่น Yuna, KarnZaa, NONT#TH1",
        min_length=1,
        max_length=20,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_nick = self.nickname_input.value.strip()
        user_ign = self.ign_input.value.strip()

        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            await interaction.response.send_message("❌ ไม่พบเซิร์ฟเวอร์", ephemeral=True)
            return

        try:
            member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        except Exception:
            member = None

        if not member:
            await interaction.response.send_message("❌ คุณไม่ได้อยู่ในเซิร์ฟเวอร์", ephemeral=True)
            return

        if user_ign:
            base_name = f"{user_nick} • {user_ign}"
        else:
            base_name = user_nick

        uid = str(member.id)
        current_data = user_levels_db.get(uid, {"xp": 0, "level": 1})
        current_lvl = current_data.get("level", 1)
        current_data["base_name"] = base_name

        user_levels_db[uid] = current_data
        save_user_levels(user_levels_db)

        starting_coins = add_user_coins(uid, 100)
        final_name = format_nickname_with_level(base_name, current_lvl, current_data.get("job_emoji", ""))

        try:
            await member.edit(nick=final_name)
        except Exception:
            pass

        # ปลดยศ 'ยังไม่ได้ตั้งชื่อ' ออกทั้งหมด
        unverified_role = get_unverified_role(guild)
        if unverified_role and unverified_role in member.roles:
            try:
                await member.remove_roles(unverified_role, reason="ลงทะเบียนโปรไฟล์เสร็จสิ้น")
                print(f"[+] ปลดยศ {unverified_role.name} จาก {member.name} สำเร็จ")
            except Exception as e:
                print(f"[!] ไม่สามารถปลดยศ unverified จาก {member.name}: {e}")

        # มอบยศ 'Cafe Member'
        member_role = get_member_role(guild)
        if not member_role:
            try:
                member_role = await guild.create_role(name=MEMBER_ROLE_NAME, color=discord.Color.from_rgb(255, 107, 129), reason="Auto-created member role")
            except Exception:
                pass

        if member_role and member_role not in member.roles:
            try:
                await member.add_roles(member_role, reason="ลงทะเบียนโปรไฟล์เสร็จสิ้น")
                print(f"[+] มอบยศ {member_role.name} ให้กับ {member.name} สำเร็จ!")
            except Exception as e:
                print(f"[!] ไม่สามารถมอบยศ {member_role.name} ให้ {member.name}: {e}")

        role_display_name = f"`{member_role.name}`" if member_role else "`Cafe Member`"
        reply_msg = (
            f"✅ **ตั้งค่าโปรไฟล์สำเร็จแล้วครับ!** 🎉\n\n"
            f"• 👤 **ชื่อของคุณในเซิร์ฟเวอร์:** `{final_name}`\n"
            f"• ⭐ **เลเวลเริ่มต้น:** `Lv.{current_lvl}`\n"
            f"• 🪙 **เหรียญขวัญถุงต้อนรับ:** `+{starting_coins:,} ☕ Coins`\n"
            f"• 👑 **ยศที่ได้รับ:** {role_display_name}\n\n"
            f"🔓 **ปลดล็อคห้องทั้งหมดในเซิร์ฟเวอร์ Gamers’ Café เรียบร้อยแล้ว**\n"
            f"👇 **กดเลือกอาชีพ Ragnarok หรือเลือกเกมที่คุณเล่นที่ปุ่มด้านล่างนี้ได้เลยครับ:**"
        )
        await interaction.response.send_message(reply_msg, view=RolesOnlyView())
        print(f"[+] สมาชิก {member.name} กรอกผ่าน Modal ใน DM: '{final_name}' (พร้อมปุ่มเลือกอาชีพ & เกม)")

# ==================== ⭐ GUI Modals เครดิต ====================

class PositiveRepModal(Modal, title="⭐ ให้เครดิตคนขาย"):
    seller_input = TextInput(
        label="1. ชื่อคนขาย หรือ แท็ก (@ชื่อ)",
        placeholder="เช่น Yuna หรือ @Yuna",
        min_length=1,
        max_length=50,
        required=True
    )
    review_input = TextInput(
        label="2. คำชม / ข้อความรีวิว",
        placeholder="เช่น ส่งไวมาก, ของตรงปก, คุยง่ายใจดี",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=200,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        seller_query = self.seller_input.value.strip()
        review_text = self.review_input.value.strip() or "ซื้อขายเรียบร้อย ส่งของจริง 100%"
        guild = interaction.guild
        seller = find_member_by_query(guild, seller_query)

        if not seller:
            await interaction.response.send_message(
                f"❌ **ไม่พบสมาชิกชื่อ `{seller_query}` ในเซิร์ฟเวอร์ครับ!**",
                ephemeral=True
            )
            return

        if seller.id == interaction.user.id:
            await interaction.response.send_message("❌ **ไม่สามารถให้เครดิตตัวเองได้ครับ!**", ephemeral=True)
            return

        if seller.bot:
            await interaction.response.send_message("❌ ไม่สามารถให้เครดิตบอทได้ครับ!", ephemeral=True)
            return

        target_uid = str(seller.id)
        voter_uid = str(interaction.user.id)
        r_data = get_user_rep_data(target_uid)
        voters = r_data.get("voters", {})

        if voter_uid in voters:
            await interaction.response.send_message(
                f"⚠️ **คุณเคยให้เครดิตคุณ {seller.mention} ไปแล้วครับ!**\n"
                f"💡 *ระบบจำกัด **1 คน ต่อ 1 ผู้ใช้** เพื่อความโปร่งใสครับ*",
                ephemeral=True
            )
            return

        voters[voter_uid] = {
            "from_id": interaction.user.id,
            "from_name": interaction.user.display_name,
            "type": "+1",
            "comment": review_text,
            "time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        r_data["voters"] = voters
        save_reputation(user_reputation_db)

        score, _ = calc_rep_counts(target_uid)
        await update_seller_roles(guild, seller, score)

        embed = discord.Embed(
            title="⭐ บันทึกเครดิตสำเร็จ!",
            description=(
                f"👤 **ผู้ซื้อ:** {interaction.user.mention}\n"
                f"🛍️ **คนขาย:** {seller.mention}\n\n"
                "───────────────────────────\n\n"
                f"💬 **รีวิว:** *\"{review_text}\"*\n\n"
                f"⭐ **เครดิตสะสมทั้งหมด:** **`{score}` คะแนน**"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=seller.display_avatar.url)
        embed.set_footer(text="Gamers' Café Community Reputation System")
        await interaction.response.send_message(embed=embed)
        print(f"[⭐ Rep] {interaction.user.name} ให้เครดิต {seller.name}: {review_text}")

class NegativeRepModal(Modal, title="⚠️ รายงานปัญหาคนขาย"):
    seller_input = TextInput(
        label="1. ชื่อคนขาย หรือ แท็ก (@ชื่อ)",
        placeholder="เช่น Yuna หรือ @Yuna",
        min_length=1,
        max_length=50,
        required=True
    )
    reason_input = TextInput(
        label="2. ปัญหาที่พบ",
        placeholder="เช่น ไม่ส่งของ, รหัสไม่ตรงปก, ติดต่อไม่ได้",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        seller_query = self.seller_input.value.strip()
        reason_text = self.reason_input.value.strip()
        guild = interaction.guild
        seller = find_member_by_query(guild, seller_query)

        if not seller:
            await interaction.response.send_message(f"❌ **ไม่พบสมาชิกชื่อ `{seller_query}` ในเซิร์ฟเวอร์ครับ!**", ephemeral=True)
            return

        if seller.id == interaction.user.id:
            await interaction.response.send_message("❌ ไม่สามารถรายงานตัวเองได้ครับ!", ephemeral=True)
            return

        target_uid = str(seller.id)
        voter_uid = str(interaction.user.id)
        r_data = get_user_rep_data(target_uid)
        voters = r_data.get("voters", {})

        if voter_uid in voters:
            await interaction.response.send_message(
                f"⚠️ **คุณเคยส่งคะแนนให้คุณ {seller.mention} ไปแล้วครับ!**",
                ephemeral=True
            )
            return

        voters[voter_uid] = {
            "from_id": interaction.user.id,
            "from_name": interaction.user.display_name,
            "type": "-1",
            "comment": reason_text,
            "time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        r_data["voters"] = voters
        save_reputation(user_reputation_db)

        score, _ = calc_rep_counts(target_uid)
        await update_seller_roles(guild, seller, score)

        embed = discord.Embed(
            title="⚠️ บันทึกรายงานปัญหาเรียบร้อย!",
            description=(
                f"👤 **ผู้รายงาน:** {interaction.user.mention}\n"
                f"🛍️ **ผู้ถูกรายงาน:** {seller.mention}\n\n"
                "───────────────────────────\n\n"
                f"⚠️ **ปัญหาที่แจ้ง:** *\"{reason_text}\"*\n\n"
                f"📉 **เครดิตคงเหลือ:** **`{score}` คะแนน**"
            ),
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=seller.display_avatar.url)
        embed.set_footer(text="Gamers' Café Marketplace Security")
        await interaction.response.send_message(embed=embed)

        report_ch = guild.get_channel(REPORT_LOG_CHANNEL_ID)
        if report_ch:
            await report_ch.send(content="🚨 มีการรายงานคนขายติดลบในตลาด:", embed=embed)

class CheckRepModal(Modal, title="🔍 เช็คเครดิตคนขาย"):
    seller_input = TextInput(
        label="ระบุชื่อคนขาย หรือ แท็ก (@ชื่อ)",
        placeholder="เช่น Yuna หรือ @Yuna",
        min_length=1,
        max_length=50,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        seller_query = self.seller_input.value.strip()
        guild = interaction.guild
        seller = find_member_by_query(guild, seller_query)

        if not seller:
            await interaction.response.send_message(
                f"❌ **ไม่พบสมาชิกชื่อ `{seller_query}` ในเซิร์ฟเวอร์ครับ!**",
                ephemeral=True
            )
            return

        target_uid = str(seller.id)
        score, reviews = calc_rep_counts(target_uid)

        if score >= 15:
            status_text = "👑 **พ่อค้าดีเด่น (Top Trusted Merchant)**"
            badge_icon = "👑"
            color = discord.Color.gold()
        elif score >= 5:
            status_text = "⭐ **พ่อค้าเครดิตดี (Verified Merchant)**"
            badge_icon = "⭐"
            color = discord.Color.green()
        elif score < 0:
            status_text = "⚠️ **มีประวัติถูกร้องเรียน (Caution)**"
            badge_icon = "⚠️"
            color = discord.Color.red()
        else:
            status_text = "⚪ **ประวัติการซื้อขายทั่วไป**"
            badge_icon = "⚪"
            color = discord.Color.light_grey()

        review_lines = []
        if reviews:
            for r in reviews[-3:]:
                icon = "✅" if r.get("type") == "+1" else "❌"
                review_lines.append(f"{icon} **{r.get('from_name', 'ลูกค้า')}:** *\"{r.get('comment', '')}\"*")
        else:
            review_lines = ["*ยังไม่มีประวัติรีวิวจากลูกค้า*"]

        embed = discord.Embed(
            title=f"{badge_icon} ข้อมูลเครดิต • {seller.display_name}",
            description=(
                f"• 👤 **คนขาย:** {seller.mention} (`{seller.name}`)\n"
                f"• 🛡️ **สถานะ:** {status_text}\n"
                f"• ⭐ **เครดิตสะสม:** **`{score}` คะแนน**\n\n"
                "───────────────────────────\n\n"
                "💬 **รีวิวล่าสุด:**\n"
                + "\n".join(review_lines)
            ),
            color=color
        )
        embed.set_thumbnail(url=seller.display_avatar.url)
        embed.set_footer(text="Gamers' Café Reputation System")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MarketRepActionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="ให้เครดิตคนขาย",
        style=discord.ButtonStyle.success,
        custom_id="btn_market_give_rep_pos",
        emoji="⭐",
        row=0
    )
    async def btn_give_pos(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PositiveRepModal())

    @discord.ui.button(
        label="รายงานปัญหา",
        style=discord.ButtonStyle.danger,
        custom_id="btn_market_give_rep_neg",
        emoji="⚠️",
        row=0
    )
    async def btn_give_neg(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(NegativeRepModal())

    @discord.ui.button(
        label="เช็คเครดิตคนขาย",
        style=discord.ButtonStyle.primary,
        custom_id="btn_market_check_rep",
        emoji="🔍",
        row=0
    )
    async def btn_check_rep(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CheckRepModal())

    @discord.ui.button(
        label="อันดับพ่อค้า",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_market_top_rep",
        emoji="🏆",
        row=0
    )
    async def btn_top_rep(self, interaction: discord.Interaction, button: Button):
        scored_users = []
        for uid_str in user_reputation_db.keys():
            score, _ = calc_rep_counts(uid_str)
            if score > 0:
                scored_users.append((uid_str, score))

        scored_users.sort(key=lambda x: x[1], reverse=True)
        top10 = scored_users[:10]

        lines = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, (uid_str, score) in enumerate(top10):
            m = interaction.guild.get_member(int(uid_str))
            name = extract_base_name(m.display_name) if m else f"User {uid_str}"
            medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
            badge_tag = "👑 พ่อค้าดีเด่น" if score >= 15 else ("⭐ เครดิตดี" if score >= 5 else "🔰 ทั่วไป")
            lines.append(f"{medal} **{name}** — `{badge_tag}` ⭐ **`{score}` เครดิต**")

        if not lines:
            lines = ["*ยังไม่มีข้อมูลอันดับพ่อค้าในระบบ*"]

        embed = discord.Embed(
            title="🏆 อันดับพ่อค้าที่มีเครดิตสูงสุดในตลาด (Top Trusted Merchants)",
            description="\n\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Gamers' Café Marketplace Leaderboard")
        await interaction.response.send_message(embed=embed, ephemeral=True)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

class MasterCafeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(DMRegisterView())
        self.add_view(RolesOnlyView())
        self.add_view(ROJobSelectView(0))
        self.add_view(DailyClaimView())
        self.add_view(MarketRepActionView())
        self.add_view(PartyHubView())
        self.add_view(ItemBuyView("1", 500))
        self.add_view(ItemBuyView("2", 500))
        self.add_view(ItemBuyView("3", 500))
        self.add_view(ItemBuyView("4", 500))
        self.add_view(ItemBuyView("5", 500))
        self.add_view(ItemBuyView("6", 1500))
        self.add_view(ItemBuyView("7", 3000))

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            # --- ปุ่มสร้างกิจกรรม Hub ---
            if custom_id == "btn_hub_create_event":
                await interaction.response.send_modal(CreateEventModal())
                return
            elif custom_id == "btn_hub_view_active_events":
                active_evs = [ev for ev in events_db.get("events", {}).values() if ev.get("status") == "open"]
                if not active_evs:
                    await interaction.response.send_message("ℹ️ **ขณะนี้ยังไม่มีกิจกรรมที่เปิดรับสมัครอยู่ครับ**\n👉 กดปุ่ม **[📢 สร้างกิจกรรมนัดตี้ & ประกาศทุกคน]** เพื่อเปิดกิจกรรมได้เลย!", ephemeral=True)
                    return

                lines = []
                for ev in active_evs:
                    eid = ev.get("event_id")
                    title = ev.get("title")
                    time_str = ev.get("time_str")
                    joined = len(ev.get("participants", {}))
                    size = ev.get("party_size", 6)
                    lines.append(f"• ⚔️ **[กิจกรรม #{eid}] {title}** — ⏰ `{time_str} น.` (ลงชื่อแล้ว `{joined}` คน • ตี้ละ `{size}` คน)")

                embed = discord.Embed(
                    title="📋 รายการกิจกรรมที่เปิดรับสมัครอยู่",
                    description="\n\n".join(lines) + "\n\n💡 *ระบบจะปิดรับสมัครและสรุปตี้ให้ก่อนเวลาเริ่ม 8 นาทีครับ*",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # --- ปุ่มลงชื่อใน Event Card / DM ---
            elif custom_id.startswith("btn_ev_signup_"):
                ev_id_str = custom_id.replace("btn_ev_signup_", "")
                ev_data = events_db.get("events", {}).get(ev_id_str)
                
                uid = str(interaction.user.id)
                user_data = user_levels_db.get(uid, {})
                user_ro_job = user_data.get("ro_job")

                # ตรวจสอบว่าเป็นกิจกรรม Ragnarok ทุกรูปแบบหรือไม่
                if ev_data:
                    ev_title = ev_data.get("title", "")
                    game_title = ev_data.get("game", "")
                    is_ro_event = check_is_ragnarok_player(ev_title) or check_is_ragnarok_player(game_title)
                    
                    if is_ro_event and not user_ro_job:
                        # ส่งข้อความพร้อมปุ่มเลือกอาชีพไปที่แชทส่วนตัว (DM) ทันที
                        dm_embed = discord.Embed(
                            title="⚔️ กรุณาเลือกอาชีพ Ragnarok ก่อนลงชื่อกิจกรรม 🎮",
                            description=(
                                f"สวัสดีครับคุณ {interaction.user.mention}! 🏰\n\n"
                                f"กิจกรรม **[{ev_title}]** เป็นกิจกรรมเกม **Ragnarok**\n"
                                "ระบบต้องการทราบอาชีพของคุณเพื่อนำไปจัดสมดุลปาร์ตี้ (พระ / แทงค์ / ดาเมจ)\n\n"
                                "👇 **กรุณากดปุ่มเลือกอาชีพของคุณด้านล่างนี้ได้เลยครับ:**"
                            ),
                            color=discord.Color.gold()
                        )
                        dm_embed.set_thumbnail(url="https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=800&q=80")
                        
                        dm_sent = False
                        try:
                            await interaction.user.send(embed=dm_embed, view=RolesOnlyView())
                            dm_sent = True
                        except Exception:
                            pass
                        
                        dm_text = "\n📩 **บอทได้ส่งปุ่มเลือกอาชีพไปในแชทส่วนตัว (DM) ให้คุณแล้วครับ**" if dm_sent else "\n*(กรุณาเปิดรับ DM หรือพิมพ์ `!rojob` ในห้องคุยเล่น)*"
                        await interaction.response.send_message(
                            f"⚠️ **คุณยังไม่ได้เลือกอาชีพ Ragnarok ครับ!**\n"
                            f"กิจกรรม **[{ev_title}]** จำเป็นต้องระบุอาชีพเพื่อจัดสมดุลตี้{dm_text}\n\n"
                            f"💡 *เมื่อกดเลือกอาชีพใน DM เรียบร้อยแล้ว สามารถกดปุ่ม **[⚔️ ลงชื่อเข้าร่วมกิจกรรม]** อีกครั้งได้ทันทีครับ!*",
                            ephemeral=True
                        )
                        return

                # กำหนดค่าเริ่มต้นให้อัตโนมัติตามข้อมูลผู้ใช้
                default_role = "ดาเมจ"
                if user_ro_job:
                    if user_ro_job in ["priest"]:
                        default_role = "พระ"
                    elif user_ro_job in ["knight", "crusader"]:
                        default_role = "แทงค์"

                base_name = user_data.get("base_name", "")
                default_ign = ""
                if "•" in base_name:
                    default_ign = base_name.split("•")[1].strip()
                elif base_name:
                    default_ign = base_name

                await interaction.response.send_modal(EventSignUpModal(int(ev_id_str), default_role=default_role, default_ign=default_ign))
                return

            # --- ปุ่มจัดตี้ทันทีก่อนหมดเวลา (เฉพาะ Admin เท่านั้น) ---
            elif custom_id.startswith("btn_ev_instant_balance_"):
                guild = interaction.guild or bot.get_guild(TARGET_GUILD_ID)
                member = interaction.user
                if guild and not isinstance(member, discord.Member):
                    member = guild.get_member(interaction.user.id)

                is_admin = False
                if member:
                    if getattr(member, "guild_permissions", None) and (member.guild_permissions.administrator or member.guild_permissions.manage_guild):
                        is_admin = True
                    elif guild and member.id == guild.owner_id:
                        is_admin = True

                if not is_admin:
                    await interaction.response.send_message(
                        "⛔ **เฉพาะผู้ดูแลเซิร์ฟเวอร์ (Admin) เท่านั้นที่สามารถกดจัดตี้ทันทีได้ครับ!**",
                        ephemeral=True
                    )
                    return

                ev_id_str = custom_id.replace("btn_ev_instant_balance_", "")
                ev_data = events_db.get("events", {}).get(ev_id_str)
                if not ev_data:
                    await interaction.response.send_message("❌ ไม่พบข้อมูลกิจกรรมนี้ในระบบ", ephemeral=True)
                    return

                if ev_data.get("status") == "balanced":
                    await interaction.response.send_message("⚠️ กิจกรรมนี้จัดตี้และปิดรับสมัครเรียบร้อยแล้วครับ!", ephemeral=True)
                    return

                participants = ev_data.get("participants", {})
                if not participants:
                    await interaction.response.send_message("⚠️ ยังไม่มีผู้ลงชื่อในกิจกรรมนี้ จึงยังไม่สามารถจัดตี้ได้ครับ", ephemeral=True)
                    return

                await interaction.response.send_message(
                    f"⚡ **กำลังทำการจัดตี้กิจกรรม [{ev_data.get('title')}] และแจ้งเตือนทุกคนทันที...** 🚀",
                    ephemeral=True
                )
                await execute_smart_party_balance(interaction.guild, ev_data)
                await update_event_messages(interaction.guild, ev_data)
                print(f"[⚡ Instant Balance by Admin] {interaction.user.name} สั่งจัดตี้ทันทีกิจกรรม #{ev_id_str}")
                return

            elif custom_id.startswith("btn_ev_view_roster_"):
                ev_id_str = custom_id.replace("btn_ev_view_roster_", "")
                ev_data = events_db.get("events", {}).get(ev_id_str)
                if not ev_data:
                    await interaction.response.send_message("❌ ไม่พบข้อมูลกิจกรรม", ephemeral=True)
                    return

                participants = ev_data.get("participants", {})
                if not participants:
                    await interaction.response.send_message("ℹ️ ยังไม่มีผู้ลงชื่อในกิจกรรมนี้ครับ", ephemeral=True)
                    return

                healers = [p for p in participants.values() if p["role"] == "healer"]
                tanks = [p for p in participants.values() if p["role"] == "tank"]
                dps_list = [p for p in participants.values() if p["role"] == "dps"]

                h_lines = [f"• 💖 <@{p['user_id']}> (`{p.get('ign', p['name'])}`)" for p in healers] or ["*[ยังไม่มี]*"]
                t_lines = [f"• 🛡️ <@{p['user_id']}> (`{p.get('ign', p['name'])}`)" for p in tanks] or ["*[ยังไม่มี]*"]
                d_lines = [f"• 🗡️ <@{p['user_id']}> (`{p.get('ign', p['name'])}`)" for p in dps_list] or ["*[ยังไม่มี]*"]

                embed = discord.Embed(
                    title=f"📋 รายชื่อผู้ลงชื่อกิจกรรม: {ev_data.get('title')} ({len(participants)} คน)",
                    description=(
                        f"⏰ **เวลาเริ่ม:** `{ev_data.get('time_str')} น.` (สรุปตี้ก่อนเริ่ม 8 นาที)\n\n"
                        "💖 **พระ / ซัพพอร์ต (Healer):**\n" + "\n".join(h_lines) + "\n\n"
                        "🛡️ **ไนท์ / แทงค์ (Tank):**\n" + "\n".join(t_lines) + "\n\n"
                        "🗡️ **ดาเมจ (DPS):**\n" + "\n".join(d_lines)
                    ),
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # --- ปุ่มตลาดเครดิต ---
            elif custom_id == "btn_market_give_rep_pos":
                await interaction.response.send_modal(PositiveRepModal())
                return
            elif custom_id == "btn_market_give_rep_neg":
                await interaction.response.send_modal(NegativeRepModal())
                return
            elif custom_id == "btn_market_check_rep":
                await interaction.response.send_modal(CheckRepModal())
                return
            elif custom_id == "btn_market_top_rep":
                scored_users = []
                for uid_str in user_reputation_db.keys():
                    score, _ = calc_rep_counts(uid_str)
                    if score > 0:
                        scored_users.append((uid_str, score))

                scored_users.sort(key=lambda x: x[1], reverse=True)
                top10 = scored_users[:10]

                lines = []
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

                for idx, (uid_str, score) in enumerate(top10):
                    m = interaction.guild.get_member(int(uid_str))
                    name = extract_base_name(m.display_name) if m else f"User {uid_str}"
                    medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
                    badge_tag = "👑 พ่อค้าดีเด่น" if score >= 15 else ("⭐ เครดิตดี" if score >= 5 else "🔰 ทั่วไป")
                    lines.append(f"{medal} **{name}** — `{badge_tag}` ⭐ **`{score}` เครดิต**")

                if not lines:
                    lines = ["*ยังไม่มีข้อมูลอันดับพ่อค้าในระบบ*"]

                embed = discord.Embed(
                    title="🏆 อันดับพ่อค้าที่มีเครดิตสูงสุดในตลาด (Top Trusted Merchants)",
                    description="\n\n".join(lines),
                    color=discord.Color.gold()
                )
                embed.set_footer(text="Gamers' Café Marketplace Leaderboard")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # --- ปุ่มร้านค้า Forum & Daily ---
            elif custom_id.startswith("btn_forum_buy_"):
                item_id = custom_id.replace("btn_forum_buy_", "")
                item = SHOP_ITEMS.get(item_id)
                if not item:
                    await interaction.response.send_message("❌ ไม่พบสินค้า", ephemeral=True)
                    return

                uid = str(interaction.user.id)
                my_coins = get_user_coins(uid)
                price = item["price"]
                role_name = item["name"]

                if my_coins < price:
                    await interaction.response.send_message(
                        f"❌ **เหรียญไม่พอครับ!**\nคุณมี `{my_coins:,} Coins` (ต้องการ `{price:,} Coins` • ขาดอีก `{price - my_coins:,} Coins`)\n\n💡 *กดปุ่ม **[🎁 รับเหรียญรายวันฟรี]** เพื่อรับเหรียญเพิ่มได้เลยครับ*",
                        ephemeral=True
                    )
                    return

                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if not role:
                    await interaction.response.send_message(f"⚠️ ไม่พบยศ `{role_name}` ในเซิร์ฟเวอร์ กรุณาติดต่อแอดมิน", ephemeral=True)
                    return

                if role in interaction.user.roles:
                    await interaction.response.send_message(f"⚠️ คุณมียศ `{role_name}` อยู่ในครอบครองแล้วครับ!", ephemeral=True)
                    return

                user_economy_db[uid]["coins"] -= price
                save_economy(user_economy_db)

                try:
                    await interaction.user.add_roles(role)
                except Exception as e:
                    await interaction.response.send_message(f"❌ มอบยศไม่สำเร็จ: {e}", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="🎉 แลกของตกแต่งสำเร็จ!",
                    description=(
                        f"ยินดีด้วยครับคุณ {interaction.user.mention}! 🛍️✨\n\n"
                        f"🏷️ **ได้รับยศ:** {role.mention}\n"
                        f"💰 **ชำระ:** `-{price:,} ☕ Coins`\n"
                        f"🪙 **คงเหลือ:** `{user_economy_db[uid]['coins']:,} ☕ Coins`"
                    ),
                    color=discord.Color.brand_green()
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                print(f"[+] {interaction.user.name} แลกซื้อยศ {role_name} สำเร็จ")
                return

            elif custom_id == "btn_forum_check_wallet" or custom_id == "btn_direct_check_balance":
                uid = str(interaction.user.id)
                coins = get_user_coins(uid)
                await interaction.response.send_message(
                    f"👤 **กระเป๋าเหรียญของคุณ {interaction.user.display_name}:**\n🪙 คุณมีเหรียญสะสมทั้งหมด: **`{coins:,} ☕ Cafe Coins`**",
                    ephemeral=True
                )
                return

            elif custom_id == "btn_direct_claim_daily":
                uid = str(interaction.user.id)
                now = time.time()
                
                if uid not in user_economy_db:
                    user_economy_db[uid] = {"coins": 200, "last_daily": 0}
                
                last_daily = user_economy_db[uid].get("last_daily", 0)
                cooldown = 24 * 3600

                if now - last_daily < cooldown:
                    remaining = int(cooldown - (now - last_daily))
                    hours = remaining // 3600
                    mins = (remaining % 3600) // 60
                    await interaction.response.send_message(
                        f"⏰ **คุณกดรับเหรียญไปแล้วครับ!**\nกลับมารับได้อีกใน: **`{hours} ชม. {mins} นาที`**",
                        ephemeral=True
                    )
                    return

                reward = random.randint(100, 300)
                user_economy_db[uid]["coins"] = user_economy_db[uid].get("coins", 200) + reward
                user_economy_db[uid]["last_daily"] = now
                save_economy(user_economy_db)

                total_coins = user_economy_db[uid]["coins"]
                embed = discord.Embed(
                    title="🎁 เช็คอินรับเหรียญสำเร็จ!",
                    description=f"🎉 ได้รับ: **`+{reward:,} ☕ Coins`**\n💰 ยอดสะสม: **`{total_coins:,} ☕ Coins`**",
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

bot = MasterCafeBot()

async def setup_party_channel_hub(guild):
    party_ch = guild.get_channel(PARTY_CHANNEL_ID)
    if not party_ch:
        return

    # ลบป้ายศูนย์กลางขนาดใหญ่ออก เพื่อให้ห้องเป็นห้องประกาศตี้และสรุปผลตี้แบบคลีน 100%
    try:
        async for msg in party_ch.history(limit=50):
            if msg.author == bot.user and msg.embeds:
                emb = msg.embeds[0]
                if "ศูนย์จัดปาร์ตี้ & กิจกรรมนัดตี้" in (emb.title or "") or "ศูนย์จัดปาร์ตี้ & หาตี้ลงดัน" in (emb.title or ""):
                    await msg.delete()
                    await asyncio.sleep(0.3)
    except Exception:
        pass
    print("[+] ปรับห้อง #⚔️・จัดตี้เกม เป็นห้องประกาศตี้และสรุปผลตี้แบบคลีน 100% เรียบร้อย")

async def configure_channel_permissions(guild):
    """
    🔒 ล็อคและซ่อนทุกห้องจากยศ 'ยังไม่ได้ตั้งชื่อ' และ @everyone
    เห็นได้เฉพาะห้อง #ต้อนรับ และ #กฎ จนกว่าจะตั้งชื่อเสร็จและได้ยศ 'Cafe Member'
    """
    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME) or discord.utils.get(guild.roles, name="ยังไม่ได้ตั้งชื่อ")
    if not unverified_role:
        try:
            unverified_role = await guild.create_role(name=UNVERIFIED_ROLE_NAME, color=discord.Color.dark_grey(), reason="Auto-created unverified role")
        except Exception:
            pass

    member_role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME) or discord.utils.get(guild.roles, name="Cafe Member")
    if not member_role:
        try:
            member_role = await guild.create_role(name=MEMBER_ROLE_NAME, color=discord.Color.from_rgb(255, 107, 129), reason="Auto-created member role")
        except Exception:
            pass

    # สิทธิ์สำหรับห้องที่อนุญาตให้คนยังไม่ตั้งชื่อดูได้ (ต้อนรับ, กฎ)
    public_ch_ids = {WELCOME_CHANNEL_ID, RULES_CHANNEL_ID}

    hide_perms = discord.PermissionOverwrite(
        view_channel=False,
        connect=False,
        send_messages=False,
        read_messages=False
    )
    show_member_text_perms = discord.PermissionOverwrite(
        view_channel=True,
        read_messages=True,
        read_message_history=True,
        send_messages=True
    )
    show_member_voice_perms = discord.PermissionOverwrite(
        view_channel=True,
        connect=True,
        speak=True,
        stream=True
    )

    # 1. ตั้งค่า Text Channels & Voice Channels
    for ch in guild.channels:
        if ch.id in public_ch_ids:
            # ห้องสาธารณะ (ต้อนรับ, กฎ)
            try:
                public_perms = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False
                )
                if unverified_role:
                    await ch.set_permissions(unverified_role, overwrite=public_perms)
                await ch.set_permissions(guild.default_role, overwrite=public_perms)
            except Exception:
                pass
        else:
            # ห้องอื่นๆ ทั้งหมด (คุยเล่น, ข่าว, จัดตี้, รูปภาพ, ตลาด, ห้องเสียง) -> ซ่อนจากคนยังไม่ตั้งชื่อ 100%
            try:
                if unverified_role:
                    await ch.set_permissions(unverified_role, overwrite=hide_perms)
                await ch.set_permissions(guild.default_role, overwrite=hide_perms)

                if member_role:
                    if isinstance(ch, discord.VoiceChannel):
                        await ch.set_permissions(member_role, overwrite=show_member_voice_perms)
                    elif ch.id == PHOTO_CHANNEL_ID or ch.id == NEWS_CHANNEL_ID:
                        # ห้องรูปภาพ/ข่าว สมาชิกดูได้อย่างเดียว ห้ามพิมพ์
                        readonly_perms = discord.PermissionOverwrite(
                            view_channel=True,
                            read_messages=True,
                            read_message_history=True,
                            send_messages=False,
                            add_reactions=True
                        )
                        await ch.set_permissions(member_role, overwrite=readonly_perms)
                    else:
                        await ch.set_permissions(member_role, overwrite=show_member_text_perms)
            except Exception:
                pass

    # 2. ตั้งค่า Categories ทั้งหมด
    for cat in guild.categories:
        try:
            if unverified_role:
                await cat.set_permissions(unverified_role, overwrite=hide_perms)
            await cat.set_permissions(guild.default_role, overwrite=hide_perms)
            if member_role:
                await cat.set_permissions(member_role, overwrite=show_member_text_perms)
        except Exception:
            pass

    print("[🔒 Permissions] ตั้งค่าซ่อนทุกห้องจากยศ 'ยังไม่ได้ตั้งชื่อ' และเปิดให้เฉพาะ 'Cafe Member' สำเร็จ 100%!")

async def send_dm_verification(member):
    embed = discord.Embed(
        title="☕ ยินดีต้อนรับเข้าสู่ Gamers’ Café! 🎮",
        description=(
            f"สวัสดีครับคุณ **{member.name}**!\n"
            "ยินดีต้อนรับเข้าสู่คอมมูนิตี้คนรักการเล่นเกมของเรา ✨\n\n"
            "───────────────────────────────\n"
            "🔒 **เพื่อปลดล็อคห้องพูดคุยและห้องเสียงในเซิร์ฟเวอร์:**\n\n"
            "👉 **วิธีที่ 1 (พิมพ์ตอบกลับ):**\n"
            "พิมพ์ตอบกลับข้อความนี้ในรูปแบบ: `[ชื่อเล่น] [ชื่อในเกม] [เกมที่เล่น]`\n"
            "*(ตัวอย่าง: `โจ้ Yuna Ragnarok` หรือ `กานต์ KarnZaa Valorant`)*\n\n"
            "👉 **วิธีที่ 2 (กดปุ่มกรอกฟอร์ม):**\n"
            "คลิกปุ่มสีเขียวด้านล่างนี้ได้เลยครับ\n"
            "───────────────────────────────\n"
            "✨ เมื่อกรอกเรียบร้อย บอทจะเปลี่ยนชื่อเล่นพร้อมติดระดับเลเวล `[Lv.1]` และ **ปลดล็อคห้องทั้งหมดให้ทันทีครับ!**\n\u200b"
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Gamers' Café • Welcome System")
    try:
        m1 = await member.send(embed=embed)
        await asyncio.sleep(0.3)
        m2 = await member.send(
            content="👇 **คลิกที่ปุ่มด้านล่างนี้เพื่อเปิดฟอร์มกรอกชื่อ:**",
            view=DMRegisterView()
        )
        verification_dm_map[str(member.id)] = [m1.id, m2.id]
        print(f"[+] ส่งแชทส่วนตัว (DM) ไปหา {member.name} สำเร็จ! (บันทึก ID สำหรับลบอัตโนมัติ)")
    except discord.Forbidden:
        print(f"[!] ไม่สามารถส่ง DM หา {member.name} ได้ (ผู้ใช้ปิดรับข้อความส่วนตัว)")

async def setup_welcome_hub(guild):
    welcome_ch = guild.get_channel(WELCOME_CHANNEL_ID)
    if not welcome_ch:
        return

    try:
        async for msg in welcome_ch.history(limit=20):
            if msg.author == bot.user:
                await msg.delete()
                await asyncio.sleep(0.3)
    except Exception:
        pass

    embed = discord.Embed(
        title="☕ ยินดีต้อนรับสู่ Gamers’ Café! 🎮",
        description=(
            "ยินดีต้อนรับสมาชิกทุกคนเข้าสู่คอมมูนิตี้สำหรับคนรักการเล่นเกม!\n"
            "ไม่ว่าคุณจะเล่นเกมแนวไหน บนมือถือ PC หรือคอนโซล ที่นี่มีเพื่อนเล่นด้วยเสมอ ✨\n\n"
            "───────────────────────────────\n\n"
            "📩 **ระบบลงทะเบียนสมาชิกใหม่:**\n"
            "บอทได้ **ส่งข้อความแชทส่วนตัว (DM) ไปหาคุณเรียบร้อยแล้ว**\n"
            "กรุณาตรวจสอบแชทส่วนตัวเพื่อพิมพ์ชื่อเล่นและปลดล็อคห้องในเซิร์ฟเวอร์นะครับ!\n\n"
            "───────────────────────────────\n\n"
            "📌 **ทางลัดห้องสำคัญ:**\n\n"
            f"• 📜 **อ่านกฎระเบียบ:** <#{RULES_CHANNEL_ID}>\n\n"
            f"• 💬 **ห้องพูดคุยทั่วไป:** <#{CHAT_CHANNEL_ID}>\n\n"
            f"• ⚔️ **จัดปาร์ตี้ & กิจกรรม:** <#{PARTY_CHANNEL_ID}>\n\n"
            f"• 🎁 **แลกของตกแต่งโปรไฟล์:** <#1543523068767506445>\n\n"
            f"• 🔊 **สร้างห้องเสียงพูดคุย:** <#1543485923839447114>\n\n"
            f"• 📰 **ติดตามข่าวสารเกมใหม่:** <#{NEWS_CHANNEL_ID}>\n\n"
            f"• 🛒 **ตลาดซื้อขายไอเทม:** <#{MARKET_CHANNEL_ID}>\n\n"
            "───────────────────────────────\n\n"
            "ขอให้ทุกคนสนุกและมีความสุขกับการเล่นเกมไปด้วยกันนะครับ! 🎉"
        ),
        color=discord.Color.from_rgb(255, 107, 129)
    )
    if os.path.exists(BANNER_PATH):
        file = discord.File(BANNER_PATH, filename="cover.jpg")
        embed.set_image(url="attachment://cover.jpg")
        await welcome_ch.send(file=file, embed=embed)
    else:
        embed.set_image(url="https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1000&q=80")
        await welcome_ch.send(embed=embed)
    print("[+] โพสต์ป้ายต้อนรับแบบคลีน ไร้ปุ่มในเซิร์ฟเวอร์ 100% สำเร็จ!")

async def configure_afk_system(guild):
    afk_ch = guild.get_channel(AFK_CHANNEL_ID)
    if not afk_ch:
        afk_ch = discord.utils.get(guild.voice_channels, name="💤 พักสายตา")

    if afk_ch:
        try:
            await guild.edit(afk_channel=afk_ch, afk_timeout=300)
            print(f"[+] ผูกห้อง AFK ประจำเซิร์ฟเวอร์: {afk_ch.name}")
        except Exception:
            pass

        try:
            perms = discord.PermissionOverwrite(
                connect=True,
                speak=False,
                stream=False,
                use_voice_activation=False
            )
            await afk_ch.set_permissions(guild.default_role, overwrite=perms)
        except Exception:
            pass

# ----------------- ระบบตรวจเช็คและกวาดล้างห้องเสียงที่ว่างเปล่า -----------------
@tasks.loop(seconds=10)
async def cleanup_empty_voice_rooms():
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild:
        return

    for vc in list(guild.voice_channels):
        if "สร้างห้อง" in vc.name or "พักสายตา" in vc.name or "พูดคุย" in vc.name:
            continue
        
        is_party_room = "ตี้ของ" in vc.name or "ตี้" in vc.name or vc.id in temp_party_rooms
        if is_party_room and len(vc.members) == 0:
            try:
                if vc.id in temp_party_rooms:
                    temp_party_rooms.remove(vc.id)
                await vc.delete()
                print(f"[-] Auto-Cleanup: ลบห้องเสียงว่างสำเร็จ: {vc.name}")
            except Exception:
                pass

# ----------------- ระบบตรวจเช็คและอวยพรวันเกิดอัตโนมัติ -----------------
@tasks.loop(minutes=30)
async def birthday_check_loop():
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild:
        return

    now = datetime.datetime.now()
    today_day = now.day
    today_month = now.month
    today_str = now.strftime("%Y-%m-%d")

    chat_channel = guild.get_channel(CHAT_CHANNEL_ID)
    birthday_role = discord.utils.get(guild.roles, name=BIRTHDAY_ROLE_NAME)

    for uid_str, data in user_birthdays_db.items():
        member = guild.get_member(int(uid_str))
        if not member:
            continue

        b_day = data.get("day")
        b_month = data.get("month")
        last_celeb = data.get("last_celebrated")

        if b_day == today_day and b_month == today_month:
            if last_celeb != today_str:
                data["last_celebrated"] = today_str
                save_birthdays(user_birthdays_db)

                if birthday_role and birthday_role not in member.roles:
                    try:
                        await member.add_roles(birthday_role)
                    except Exception:
                        pass

                add_user_coins(uid_str, 500)

                if chat_channel:
                    month_name = THAI_MONTHS[b_month] if 1 <= b_month <= 12 else str(b_month)
                    embed = discord.Embed(
                        title="🎂 สุขสันต์วันเกิด! HAPPY BIRTHDAY 🎉",
                        description=(
                            f"🎉 **สุขสันต์วันเกิดคุณ {member.mention}!** 🥳🎈\n\n"
                            "ขอให้มีความสุขมากๆ สุขภาพร่างกายแข็งแรง\n"
                            "เล่นเกมชนะทุกตา และเปิดกาชาไม่เกลือตลอดปีครับ! ✨\n\n"
                            "───────────────────────────\n\n"
                            "🎁 **ของขวัญวันเกิดพิเศษจากร้าน:**\n"
                            f"• 👑 **ยศฉายา:** {birthday_role.mention if birthday_role else '`🎂 Birthday`'}\n"
                            "• 🪙 **เหรียญฟรี:** `+500 ☕ Cafe Coins`\n"
                        ),
                        color=discord.Color.from_rgb(255, 215, 0)
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_image(url="https://images.unsplash.com/photo-1513151233558-d860c5398176?auto=format&fit=crop&w=1000&q=80")
                    embed.set_footer(text=f"Gamers' Café • วันที่ {b_day} {month_name}")

                    await chat_channel.send(content=f"🎂 HBD {member.mention}! ขอให้มีความสุขมากๆ ครับ 🎉", embed=embed)
                    print(f"[🎂] อวยพรวันเกิดให้ {member.name} สำเร็จ!")
        else:
            if birthday_role and birthday_role in member.roles:
                try:
                    await member.remove_roles(birthday_role)
                    print(f"[-] ถอดยศวันเกิดของ {member.name} หลังหมดวันเกิด")
                except Exception:
                    pass

@tasks.loop(minutes=2)
async def voice_xp_loop():
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild:
        return

    for vc in guild.voice_channels:
        if vc.id == AFK_CHANNEL_ID or "พักสายตา" in vc.name:
            continue
        if len(vc.members) >= 1:
            for member in vc.members:
                if member.bot:
                    continue
                uid = str(member.id)
                base_name = user_levels_db.get(uid, {}).get("base_name", extract_base_name(member.display_name))
                is_lvl_up, new_lvl, new_xp, bname = add_user_xp(uid, base_name, 10)
                if is_lvl_up:
                    new_nick = format_nickname_with_level(bname, new_lvl)
                    try:
                        await member.edit(nick=new_nick)
                        print(f"[🆙] {member.name} เลเวลอัปจากห้องเสียงเป็น Lv.{new_lvl} (ชื่อใหม่: {new_nick})")
                    except Exception:
                        pass

@tasks.loop(minutes=30)
async def auto_news_loop():
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild:
        return
    news_channel = guild.get_channel(NEWS_CHANNEL_ID)
    if not news_channel:
        return

    sources = [
        "https://game-ded.com/feed",
        "https://www.gamingdose.com/feed/"
    ]

    for feed_url in sources:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                link = entry.link
                if link in posted_news_links:
                    continue

                title = entry.title
                summary_raw = getattr(entry, "description", getattr(entry, "summary", ""))
                soup = BeautifulSoup(summary_raw, "html.parser")
                clean_summary = soup.get_text().strip()
                if len(clean_summary) > 220:
                    clean_summary = clean_summary[:220].rsplit(' ', 1)[0] + "..."

                img_url = None
                if hasattr(entry, "media_content") and entry.media_content:
                    img_url = entry.media_content[0].get("url")
                elif soup.find("img"):
                    img_url = soup.find("img").get("src")

                embed = discord.Embed(
                    title=f"📰 {title}",
                    url=link,
                    description=(
                        f"**รายละเอียดโดยย่อ:**\n"
                        f"> {clean_summary}\n\n"
                        f"👉 **[คลิกที่นี่เพื่ออ่านข่าวฉบับเต็ม]({link})**"
                    ),
                    color=discord.Color.from_rgb(88, 101, 242)
                )
                embed.set_author(name="ข่าวสารเกม")
                if img_url and img_url.startswith("http"):
                    embed.set_image(url=img_url)
                embed.set_footer(text="Gamers' Café News")

                await news_channel.send(embed=embed)
                posted_news_links.add(link)
                await asyncio.sleep(1.0)
        except Exception:
            pass
    save_posted_news(posted_news_links)

@bot.event
async def on_scheduled_event_create(event: discord.ScheduledEvent):
    """
    🔗 เชื่อมต่อระบบกิจกรรมของ Discord Server เข้ากับระบบจัดตี้อัตโนมัติ 8 นาทีก่อนเริ่ม
    """
    guild = event.guild
    if guild.id != TARGET_GUILD_ID:
        return

    # คำนวณเวลาเริ่ม (Bangkok Time UTC+7)
    start_dt = event.start_time.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
    time_str = start_dt.strftime("%H:%M")
    start_ts = event.start_time.timestamp()
    balance_ts = start_ts - (8 * 60)

    # ตรวจสอบขนาดตี้จากรายละเอียดกิจกรรม (Description)
    desc = event.description or ""
    party_size = 6
    if "ขนาดตี้:" in desc or "party:" in desc.lower() or "ตี้ละ" in desc:
        match = re.search(r"(?:ขนาดตี้:|party:|ตี้ละ)\s*(\d+)", desc, re.IGNORECASE)
        if match:
            try:
                party_size = int(match.group(1))
            except Exception:
                party_size = 6

    # ตรวจสอบเกม
    game_title = "ROM / ROX"
    if "valorant" in (event.name + desc).lower():
        game_title = "Valorant"
    elif "rov" in (event.name + desc).lower():
        game_title = "RoV"
    elif "ragnarok" in (event.name + desc).lower() or "rom" in (event.name + desc).lower() or "rox" in (event.name + desc).lower():
        game_title = "ROM / ROX"

    ev_id = events_db.get("counter", 1)
    events_db["counter"] = ev_id + 1

    ev_data = {
        "event_id": ev_id,
        "discord_event_id": event.id,
        "title": event.name,
        "game": game_title,
        "time_str": time_str,
        "event_timestamp": start_ts,
        "balance_timestamp": balance_ts,
        "party_size": party_size,
        "creator_id": event.creator_id or guild.owner_id,
        "status": "open",
        "participants": {},
        "dm_msg_ids": {},
        "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    embed = render_event_announcement_embed(ev_data)

    # 1. ส่งประกาศลงห้อง #⚔️・จัดตี้เกม
    party_ch = guild.get_channel(PARTY_CHANNEL_ID)
    if party_ch:
        m1 = await party_ch.send(
            content=f"📢 **ตรวจพบการสร้างกิจกรรมใหม่ของเซิร์ฟเวอร์!** [🔗 ดูอีเวนต์]({event.url}) (เริ่ม `{time_str} น.`)",
            embed=embed,
            view=EventActionView(ev_id)
        )
        ev_data["party_msg_id"] = m1.id

    # 2. ส่งประกาศลงห้อง #คุยเล่น
    chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
    if chat_ch:
        m2 = await chat_ch.send(
            content=f"⚔️ **มีกิจกรรมใหม่ของเซิร์ฟเวอร์ [{event.name}] วันนี้เวลา `{time_str} น.`!** กดปุ่มลงชื่อด้านล่างได้เลยครับ @everyone",
            embed=embed,
            view=EventActionView(ev_id)
        )
        ev_data["chat_msg_id"] = m2.id

    # 3. ส่งข้อความ DM หาผู้ใช้ทุกคนในเซิร์ฟเวอร์ และบันทึก ID ไว้เพื่อลบเมื่อยกเลิก
    dm_map = {}
    for m in guild.members:
        if m.bot:
            continue
        dm_embed = discord.Embed(
            title=f"⚔️ [Gamers' Café] ชวนร่วมกิจกรรม: {event.name}",
            description=(
                f"สวัสดีครับคุณ **{m.display_name}**! 🎮✨\n\n"
                f"เซิร์ฟเวอร์ได้เปิดกิจกรรม **{event.name}** (`{game_title}`)\n"
                f"⏰ **เวลากิจกรรม:** **`{time_str} น.`**\n"
                f"👥 **ขนาดปาร์ตี้:** **`{party_size} คน/ตี้`** (จัดสมดุลพระ/แทงค์/ดาเมจ)\n\n"
                "───────────────────────────\n"
                "⏰ **ระบบจะสรุปตี้และแจ้งกลุ่มให้ทราบก่อนเริ่ม 8 นาที**\n"
                "👇 **คลิกปุ่มด้านล่างนี้เพื่อลงชื่อเข้าร่วมได้ทันที:**"
            ),
            color=discord.Color.brand_green()
        )
        dm_embed.set_footer(text=f"Gamers' Café Server Event #{ev_id}")
        try:
            dm_msg = await m.send(embed=dm_embed, view=EventActionView(ev_id))
            dm_map[str(m.id)] = dm_msg.id
            await asyncio.sleep(0.1)
        except Exception:
            pass

    ev_data["dm_msg_ids"] = dm_map
    events_db["events"][str(ev_id)] = ev_data
    save_events(events_db)

    print(f"[📢 Server Event Linked] บอทตรวจพบกิจกรรมของ Server: {event.name} ({time_str} น.) ซิงค์เข้าระบบจัดตี้อัตโนมัติสำเร็จ!")

async def purge_event_completely(guild: discord.Guild, target_ev_id: str, target_data: dict):
    """
    🗑️ ฟังก์ชันลบประกาศกิจกรรมทั้งหมด: ลบใน #จัดตี้เกม, #คุยเล่น และลบแชทส่วนตัว (DM) ของทุกคนแบบขนาน (Parallel) ทันที
    """
    if not target_data:
        return

    # 1. ลบข้อความในห้อง #⚔️・จัดตี้เกม
    if "party_msg_id" in target_data:
        party_ch = guild.get_channel(PARTY_CHANNEL_ID)
        if party_ch:
            try:
                p_msg = await party_ch.fetch_message(target_data["party_msg_id"])
                if p_msg:
                    await p_msg.delete()
                    print(f"[🗑️] ลบข้อความประกาศกิจกรรม #{target_ev_id} ในห้อง #จัดตี้เกม สำเร็จ")
            except Exception:
                pass

    # 2. ลบข้อความในห้อง #คุยเล่น
    if "chat_msg_id" in target_data:
        chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
        if chat_ch:
            try:
                c_msg = await chat_ch.fetch_message(target_data["chat_msg_id"])
                if c_msg:
                    await c_msg.delete()
                    print(f"[🗑️] ลบข้อความประกาศกิจกรรม #{target_ev_id} ในห้อง #คุยเล่น สำเร็จ")
            except Exception:
                pass

    # 3. ลบข้อความใน DM ของทุกคนแบบขนาน (Parallel)
    dm_map = target_data.get("dm_msg_ids", {})
    async def delete_single_dm(uid_str, msg_id):
        try:
            m_obj = guild.get_member(int(uid_str))
            if not m_obj:
                m_obj = await bot.fetch_user(int(uid_str))
            if m_obj:
                dm_ch = getattr(m_obj, "dm_channel", None) or await m_obj.create_dm()
                dm_msg = await dm_ch.fetch_message(msg_id)
                if dm_msg:
                    await dm_msg.delete()
        except Exception:
            pass

    if dm_map:
        await asyncio.gather(*[delete_single_dm(uid, mid) for uid, mid in dm_map.items()], return_exceptions=True)
        print(f"[🗑️] ลบข้อความ DM ชวนร่วมกิจกรรม #{target_ev_id} ทั้งหมด ({len(dm_map)} คน) สำเร็จ!")

    # 4. ลบออกจากฐานข้อมูล
    if target_ev_id in events_db.get("events", {}):
        del events_db["events"][target_ev_id]
        save_events(events_db)
    print(f"[🗑️ Purged Event] ยกเลิกและลบข้อความประกาศกิจกรรม #{target_ev_id} ทุกช่องทางเรียบร้อยแล้ว!")

@bot.event
async def on_scheduled_event_delete(event: discord.ScheduledEvent):
    """
    🗑️ เมื่อมีการลบ/ยกเลิกกิจกรรมใน Discord: ลบข้อความประกาศทั้งหมดในแชทและ DM ทันที!
    """
    guild = event.guild
    if guild.id != TARGET_GUILD_ID:
        return

    target_ev_id = None
    target_data = None
    for eid, ev in list(events_db.get("events", {}).items()):
        if ev.get("discord_event_id") == event.id:
            target_ev_id = eid
            target_data = ev
            break

    if target_data and target_ev_id:
        await purge_event_completely(guild, target_ev_id, target_data)

@bot.event
async def on_scheduled_event_update(before: discord.ScheduledEvent, after: discord.ScheduledEvent):
    """
    🔄 ดักจับเมื่อกิจกรรมถูกกดยกเลิก (Cancelled) หรือสิ้นสุด (Completed)
    """
    guild = after.guild
    if guild.id != TARGET_GUILD_ID:
        return

    # ถ้ายกเลิกกิจกรรม
    if after.status in [discord.EventStatus.cancelled, discord.EventStatus.completed, discord.EventStatus.ended]:
        target_ev_id = None
        target_data = None
        for eid, ev in list(events_db.get("events", {}).items()):
            if ev.get("discord_event_id") == after.id:
                target_ev_id = eid
                target_data = ev
                break

        if target_data and target_ev_id:
            await purge_event_completely(guild, target_ev_id, target_data)

async def cleanup_orphaned_event_messages(guild):
    """
    🧹 สแกนและลบข้อความประกาศของกิจกรรมที่ถูกยกเลิกไปแล้ว หรือกิจกรรมเก่าที่หมดเวลาไปแล้ว
    """
    party_ch = guild.get_channel(PARTY_CHANNEL_ID)
    chat_ch = guild.get_channel(CHAT_CHANNEL_ID)
    current_discord_event_ids = {e.id for e in guild.scheduled_events}
    now_ts = time.time()

    # ลบข้อความประกาศใน #จัดตี้เกม ที่ไม่อยู่ในรายการ scheduled_events ปัจจุบัน
    if party_ch:
        try:
            async for msg in party_ch.history(limit=50):
                if msg.author == bot.user and msg.embeds:
                    emb = msg.embeds[0]
                    title_text = emb.title or ""
                    # ถ้าเป็นการ์ดประกาศกิจกรรม (ไม่ใช่ป้ายศูนย์กลาง)
                    if "[กิจกรรมนัดตี้]" in title_text or "ยอดสมาชิกลงชื่อปัจจุบัน" in (emb.description or ""):
                        # ตรวจสอบว่ากิจกรรมนี้ยังมีอยู่ใน Discord หรือไม่
                        is_active = False
                        for ev_id, ev_data in events_db.get("events", {}).items():
                            if ev_data.get("party_msg_id") == msg.id and ev_data.get("discord_event_id") in current_discord_event_ids:
                                # ถ้ายังไม่หมดเวลา
                                if ev_data.get("event_timestamp", 0) > (now_ts - 3600):
                                    is_active = True
                                    break
                        if not is_active:
                            await msg.delete()
                            print(f"[🧹] ลบการ์ดกิจกรรมที่ยกเลิก/หมดเวลาแล้วใน #จัดตี้เกม: {msg.id}")
                            await asyncio.sleep(0.3)
        except Exception:
            pass

    # ลบข้อความประกาศใน #คุยเล่น
    if chat_ch:
        try:
            async for msg in chat_ch.history(limit=50):
                if msg.author == bot.user and msg.embeds:
                    emb = msg.embeds[0]
                    title_text = emb.title or ""
                    if "[กิจกรรมนัดตี้]" in title_text or "มีกิจกรรมใหม่ของเซิร์ฟเวอร์" in msg.content:
                        is_active = False
                        for ev_id, ev_data in events_db.get("events", {}).items():
                            if ev_data.get("chat_msg_id") == msg.id and ev_data.get("discord_event_id") in current_discord_event_ids:
                                if ev_data.get("event_timestamp", 0) > (now_ts - 3600):
                                    is_active = True
                                    break
                        if not is_active:
                            await msg.delete()
                            print(f"[🧹] ลบการ์ดกิจกรรมที่ยกเลิก/หมดเวลาแล้วใน #คุยเล่น: {msg.id}")
                            await asyncio.sleep(0.3)
        except Exception:
            pass

@bot.event
async def on_ready():
    print("=" * 60)
    print(f"[OK] Master Café Bot พร้อมระบบ Event Scheduling & Auto-Balancing 8 นาที ออนไลน์ 100%: {bot.user.name}")
    print("=" * 60)

    guild = bot.get_guild(TARGET_GUILD_ID)
    if guild:
        await setup_welcome_hub(guild)
        await setup_party_channel_hub(guild)
        await configure_afk_system(guild)
        await configure_channel_permissions(guild)
        await cleanup_orphaned_event_messages(guild)

        # 🔄 Auto-Sync: ซิงค์ยศสมาชิกที่เคยตั้งชื่อแล้วให้ได้รับยศ Cafe Member ทันที
        member_r = get_member_role(guild)
        unverified_r = get_unverified_role(guild)
        for m in guild.members:
            if m.bot:
                continue
            uid_str = str(m.id)
            if uid_str in user_levels_db and user_levels_db[uid_str].get("base_name"):
                if unverified_r and unverified_r in m.roles:
                    try:
                        await m.remove_roles(unverified_r)
                    except Exception:
                        pass
                if member_r and member_r not in m.roles:
                    try:
                        await m.add_roles(member_r)
                        print(f"[+] Auto-Sync: มอบยศ {member_r.name} ให้กับ {m.name} สำเร็จ")
                    except Exception:
                        pass

    if not auto_news_loop.is_running():
        auto_news_loop.start()
    if not voice_xp_loop.is_running():
        voice_xp_loop.start()
    if not cleanup_empty_voice_rooms.is_running():
        cleanup_empty_voice_rooms.start()
    if not birthday_check_loop.is_running():
        birthday_check_loop.start()
    if not event_scheduler_loop.is_running():
        event_scheduler_loop.start()

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_ch = guild.get_channel(WELCOME_CHANNEL_ID)

    member_role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME) or discord.utils.get(guild.roles, name="Cafe Member")
    if member_role and member_role in member.roles:
        try:
            await member.remove_roles(member_role)
        except Exception:
            pass

    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME) or discord.utils.get(guild.roles, name="ยังไม่ได้ตั้งชื่อ")
    if not unverified_role:
        try:
            unverified_role = await guild.create_role(name=UNVERIFIED_ROLE_NAME, color=discord.Color.dark_grey(), reason="Auto-created unverified role for new members")
        except Exception:
            pass

    if unverified_role:
        try:
            await member.add_roles(unverified_role)
            print(f"[+] มอบยศ {unverified_role.name} ให้กับสมาชิกใหม่: {member.name}")
        except Exception as e:
            print(f"[!] ไม่สามารถมอบยศ {UNVERIFIED_ROLE_NAME} ให้ {member.name}: {e}")

    await send_dm_verification(member)

    if welcome_ch:
        try:
            async for msg in welcome_ch.history(limit=100):
                if msg.author == bot.user and msg.embeds:
                    emb = msg.embeds[0]
                    footer_text = getattr(emb.footer, 'text', '') or ''
                    desc_text = emb.description or ''
                    
                    is_this_user = (
                        str(member.id) in footer_text or 
                        member.name in desc_text or 
                        member.display_name in desc_text or 
                        member.mention in desc_text
                    )
                    is_main_hub = "ยินดีต้อนรับสู่ Gamers’ Café!" in (emb.title or '')

                    if is_this_user and not is_main_hub:
                        await msg.delete()
                        await asyncio.sleep(0.3)
        except Exception:
            pass

        embed = discord.Embed(
            title="🎉 ยินดีต้อนรับสมาชิกเข้าสู่ Gamers’ Café! ☕",
            description=(
                f"ยินดีต้อนรับคุณ **{member.display_name}** (`{member.name}`) เข้าสู่คอมมูนิตี้คนเล่นเกมของเรา!\n\n"
                f"✨ **คุณเป็นสมาชิกลำดับที่:** `#{member.guild.member_count}`\n\n"
                f"📩 **บอทได้ส่งข้อความแชทส่วนตัว (DM) ไปหาคุณแล้ว** เพื่อให้ตอบชื่อเล่นและปลดล็อคห้องครับ!"
            ),
            color=discord.Color.brand_green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Gamers' Café • ID: {member.id}")
        
        await welcome_ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

@bot.event
async def on_member_remove(member):
    # 1. ลบข้อความที่ส่งไปใน DM ของผู้ใช้ที่ออกจากเซิร์ฟเวอร์
    await delete_user_verification_dms(member.id)

    # 2. ถอนรายชื่อออกจากกิจกรรมที่เปิดรับสมัครอยู่ทั้งหมดทันที
    uid_str = str(member.id)
    events_updated = False
    for ev_id, ev_data in list(events_db.get("events", {}).items()):
        if ev_data.get("status") == "open":
            participants = ev_data.get("participants", {})
            if uid_str in participants:
                del participants[uid_str]
                ev_data["participants"] = participants
                events_updated = True
                # อัปเดตยอดคนลงชื่อบนการ์ดในห้อง #จัดตี้เกม และ #คุยเล่น แบบเรียลไทม์
                await update_event_messages(member.guild, ev_data)
                print(f"[-] สมาชิก {member.name} ออกจากเซิร์ฟเวอร์ -> ลบรายชื่อออกจากกิจกรรม #{ev_id} สำเร็จ")

    if events_updated:
        save_events(events_db)

    welcome_ch = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not welcome_ch:
        return

    # 3. ลบข้อความต้อนรับเดิมของสมาชิกคนนี้ในห้อง #ต้อนรับ เพื่อความสะอาด
    try:
        async for msg in welcome_ch.history(limit=50):
            if msg.author == bot.user and msg.embeds:
                emb = msg.embeds[0]
                footer_text = getattr(emb.footer, 'text', '') or ''
                desc_text = emb.description or ''
                if str(member.id) in footer_text or member.name in desc_text:
                    await msg.delete()
                    await asyncio.sleep(0.3)
    except Exception:
        pass

    embed = discord.Embed(
        title="🚪 สมาชิกออกจากเซิร์ฟเวอร์",
        description=(
            f"คุณ **{member.display_name}** (`{member.name}`) ได้ออกจาก **{member.guild.name}** แล้ว\n\n"
            f"หวังว่าจะได้พบกันใหม่อีกครั้งนะครับ! 👋✨\n\n"
            f"👥 **สมาชิกที่เหลืออยู่ในเซิร์ฟเวอร์:** `{member.guild.member_count}` คน"
        ),
        color=discord.Color.from_rgb(149, 165, 166)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Gamers' Café • ID: {member.id}")
    
    await welcome_ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

@bot.event
async def on_voice_state_update(member, before, after):
    unverified_role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE_NAME)
    if after.channel and unverified_role and unverified_role in member.roles:
        try:
            await member.move_to(None)
        except Exception:
            pass
        return

    if after.channel and "สร้างห้อง" in after.channel.name:
        guild = after.channel.guild
        category = after.channel.category
        new_room_name = f"🔊 ตี้ของ {member.display_name}"
        try:
            new_room = await guild.create_voice_channel(
                name=new_room_name,
                category=category,
                user_limit=0
            )
            temp_party_rooms.add(new_room.id)
            print(f"[+] สร้างห้องตี้ใหม่: {new_room_name}")
            await member.move_to(new_room)
        except Exception as e:
            print(f"[!] เกิดข้อผิดพลาด: {e}")

    if after.channel and (after.channel.id == AFK_CHANNEL_ID or "พักสายตา" in after.channel.name):
        try:
            await member.edit(mute=True, deafen=True)
        except Exception:
            pass

    if before.channel and (before.channel.id == AFK_CHANNEL_ID or "พักสายตา" in before.channel.name):
        if after.channel and after.channel.id != AFK_CHANNEL_ID:
            try:
                await member.edit(mute=False, deafen=False)
            except Exception:
                pass

    if before.channel:
        is_temp = (
            before.channel.id in temp_party_rooms or 
            "ตี้ของ" in before.channel.name or 
            "ตี้" in before.channel.name
        )
        if is_temp and "สร้างห้อง" not in before.channel.name and "พักสายตา" not in before.channel.name:
            if len(before.channel.members) == 0:
                try:
                    if before.channel.id in temp_party_rooms:
                        temp_party_rooms.remove(before.channel.id)
                    await before.channel.delete()
                    print(f"[-] ลบห้องตี้ที่ไม่มีคนแล้วทันที: {before.channel.name}")
                except Exception:
                    pass

@bot.event
async def on_message_delete(message: discord.Message):
    if message.channel.id == CHAT_CHANNEL_ID:
        orig_id_str = str(message.id)
        if orig_id_str in photo_message_map:
            target_ids = photo_message_map[orig_id_str]
            photo_ch = message.guild.get_channel(PHOTO_CHANNEL_ID)
            if photo_ch:
                for tid in target_ids:
                    try:
                        target_msg = await photo_ch.fetch_message(tid)
                        if target_msg:
                            await target_msg.delete()
                            print(f"[🧹] ลบรูปภาพใน #รูปภาพ ตามข้อความต้นฉบับ ({orig_id_str} -> {tid})")
                    except Exception:
                        pass
            del photo_message_map[orig_id_str]
            save_photo_map(photo_message_map)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 🛡️ ระบบ Anti-Scam
    if message.guild and isinstance(message.author, discord.Member):
        is_admin = message.author.guild_permissions.administrator or message.author.id == message.guild.owner_id
        if not is_admin:
            is_scam, scam_reason = check_is_scam(message.content)
            if is_scam:
                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    await message.author.timeout(datetime.timedelta(hours=1), reason=f"Anti-Scam: {scam_reason}")
                except Exception:
                    pass

                warning_embed = discord.Embed(
                    title="🛡️ ระบบความปลอดภัยระงับข้อความอันตราย (Anti-Scam)",
                    description=(
                        f"⚠️ **ตรวจพบและลบข้อความสแกม/ฟิชชิ่งจากคุณ {message.author.mention} ทันที!**\n\n"
                        f"📌 **สาเหตุ:** {scam_reason}\n"
                        f"⏱️ **การดำเนินการ:** ระงับการส่งข้อความชั่วคราวเป็นเวลา 1 ชั่วโมงเพื่อความปลอดภัยของสมาชิกทุกคนครับ"
                    ),
                    color=discord.Color.red()
                )
                try:
                    w_msg = await message.channel.send(embed=warning_embed)
                    await asyncio.sleep(8)
                    await w_msg.delete()
                except Exception:
                    pass

                report_ch = message.guild.get_channel(REPORT_LOG_CHANNEL_ID)
                if report_ch:
                    log_embed = discord.Embed(
                        title="🚨 บันทึกความปลอดภัย Anti-Scam Alert",
                        description=(
                            f"• 👤 **ผู้ส่ง:** {message.author.mention} (`{message.author.name}` | ID: `{message.author.id}`)\n"
                            f"• 💬 **ห้องที่ส่ง:** {message.channel.mention}\n"
                            f"• ⚠️ **สาเหตุ:** {scam_reason}\n"
                            f"• 📝 **เนื้อหาข้อความ:**\n```\n{message.content[:500]}\n```\n"
                            f"• 🛡️ **การดำเนินการ:** ลบข้อความ + Timeout 1 ชั่วโมง เรียบร้อยแล้ว"
                        ),
                        color=discord.Color.dark_red()
                    )
                    log_embed.set_thumbnail(url=message.author.display_avatar.url)
                    log_embed.set_footer(text="Gamers' Café Security System")
                    await report_ch.send(embed=log_embed)

                print(f"[🛡️ Anti-Scam] สกัดกั้นสแกมสำเร็จจาก {message.author.name}: {scam_reason}")
                return

    # 1. จัดการข้อความที่ตอบกลับมาในแชทส่วนตัว (DM)
    if isinstance(message.channel, discord.DMChannel):
        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            return
        member = guild.get_member(message.author.id)
        if not member:
            await message.channel.send("⚠️ ไม่พบข้อมูลของคุณในเซิร์ฟเวอร์ Gamers’ Café")
            return

        raw_parts = message.content.strip().split()
        if len(raw_parts) >= 2:
            user_nick = raw_parts[0]
            user_ign = raw_parts[1]
            user_game = " ".join(raw_parts[2:]).lower() if len(raw_parts) > 2 else ""
            base_name = f"{user_nick} • {user_ign}"
        else:
            user_nick = raw_parts[0]
            user_game = ""
            base_name = user_nick

        uid = str(member.id)
        current_data = user_levels_db.get(uid, {"xp": 0, "level": 1})
        current_lvl = current_data.get("level", 1)
        current_data["base_name"] = base_name
        user_levels_db[uid] = current_data
        save_user_levels(user_levels_db)

        starting_coins = add_user_coins(uid, 100)
        final_name = format_nickname_with_level(base_name, current_lvl)

        try:
            await member.edit(nick=final_name)
        except Exception:
            pass

        # ปลดยศ 'ยังไม่ได้ตั้งชื่อ' ออกทั้งหมด
        unverified_role = get_unverified_role(guild)
        if unverified_role and unverified_role in member.roles:
            try:
                await member.remove_roles(unverified_role, reason="ลงทะเบียนผ่าน DM สำเร็จ")
                print(f"[+] ปลดยศ {unverified_role.name} จาก {member.name} สำเร็จ")
            except Exception as e:
                print(f"[!] ไม่สามารถปลดยศ unverified จาก {member.name}: {e}")

        # มอบยศ 'Cafe Member'
        member_role = get_member_role(guild)
        if not member_role:
            try:
                member_role = await guild.create_role(name=MEMBER_ROLE_NAME, color=discord.Color.from_rgb(255, 107, 129), reason="Auto-created member role")
            except Exception:
                pass

        if member_role and member_role not in member.roles:
            try:
                await member.add_roles(member_role, reason="ลงทะเบียนผ่าน DM สำเร็จ")
                print(f"[+] มอบยศ {member_role.name} ให้กับ {member.name} สำเร็จ!")
            except Exception as e:
                print(f"[!] ไม่สามารถมอบยศ {member_role.name} ให้ {member.name}: {e}")

        for kw, rname in GAME_ROLE_MAPPING.items():
            if kw in user_game:
                r = discord.utils.get(guild.roles, name=rname)
                if r:
                    try:
                        await member.add_roles(r)
                    except Exception:
                        pass

        success_embed = discord.Embed(
            title="✅ ยืนยันข้อมูลและปลดล็อคห้องสำเร็จ!",
            description=(
                f"ยินดีต้อนรับคุณ **{final_name}** เข้าสู่ **{guild.name}**!\n\n"
                f"⭐ **เลเวลเริ่มต้นของคุณ:** `Lv.{current_lvl}`\n"
                f"🪙 **เหรียญขวัญถุงต้อนรับ:** `+{starting_coins:,} ☕ Coins`\n"
                f"🔓 **บอทได้เปลี่ยนชื่อเล่นและปลดล็อคห้องสำคัญทั้งหมดในเซิร์ฟเวอร์ให้คุณแล้วครับ**\n"
                f"สามารถกลับไปพูดคุยและเล่นเกมกับเพื่อนๆ ในเซิร์ฟเวอร์ได้เลยครับ! ☕🎮"
            ),
            color=discord.Color.green()
        )
        await message.channel.send(embed=success_embed)
        await delete_user_verification_dms(member.id)
        print(f"[+] สมาชิก {member.name} ยืนยันผ่าน DM: '{final_name}' (ลบข้อความชวนกรอกเดิมเรียบร้อย)")

        # ถ้าผู้ใช้เล่น Ragnarok (ทุกเวอร์ชัน) ให้ส่งเมนูเลือกอาชีพทันที
        is_ro = check_is_ragnarok_player(user_game)
        if is_ro:
            ro_prompt_embed = discord.Embed(
                title="⚔️ คุณเล่น Ragnarok! กรุณาเลือกอาชีพของคุณ 🎮",
                description=(
                    "🏰 **เลือกอาชีพที่คุณเล่นจากเมนูดรอปดาวน์ด้านล่างนี้ได้เลยครับ:**\n\n"
                    "• 🏷️ **รับยศประจำอาชีพของคุณ**\n"
                    "• 👑 **ใส่อิโมจิประจำอาชีพไว้หน้าชื่อเล่นของคุณในเซิร์ฟเวอร์**\n"
                    "• ⚔️ **เพื่อนๆ ในตี้จะเห็นอาชีพของคุณทันทีตอนหาตี้ลงดัน!**"
                ),
                color=discord.Color.gold()
            )
            try:
                await message.author.send(embed=ro_prompt_embed, view=ROJobSelectView(member.id))
            except Exception:
                pass
        return

    # 2. จัดการเมื่อพิมพ์ในห้องเซิร์ฟเวอร์ (ถ้ายังไม่ยืนยันตัวตน)
    guild = message.guild
    member = message.author
    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    if unverified_role and unverified_role in member.roles:
        try:
            await message.delete()
        except Exception:
            pass

        alert_embed = discord.Embed(
            title="⚠️ กรุณาตอบแชทส่วนตัวของบอทเพื่อปลดล็อคห้องครับ",
            description=(
                f"สวัสดีครับคุณ {member.mention}!\n\n"
                f"📩 **บอทได้ส่งข้อความแชทส่วนตัว (DM) ไปหาคุณแล้ว**\n"
                f"กรุณาตรวจสอบแชทส่วนตัวเพื่อกรอกชื่อเล่นและปลดล็อคห้องในเซิร์ฟเวอร์ครับ! ☕🎮"
            ),
            color=discord.Color.orange()
        )
        alert_msg = await message.channel.send(
            content=f"👋 {member.mention}",
            embed=alert_embed,
            allowed_mentions=discord.AllowedMentions.none()
        )
        await asyncio.sleep(15)
        try:
            await alert_msg.delete()
        except Exception:
            pass
        return

    # 3. ระบบสะสม XP จากการพิมพ์คุยในแชท
    now = time.time()
    uid = str(member.id)
    last_xp_time = xp_cooldowns.get(uid, 0)
    
    if now - last_xp_time > 30 and not message.content.startswith("!"):
        xp_cooldowns[uid] = now
        xp_gain = random.randint(15, 25)
        
        base_name = user_levels_db.get(uid, {}).get("base_name")
        if not base_name:
            base_name = extract_base_name(member.display_name)

        is_lvl_up, new_lvl, total_xp, bname = add_user_xp(uid, base_name, xp_gain)

        if is_lvl_up:
            new_nick = format_nickname_with_level(bname, new_lvl)
            try:
                await member.edit(nick=new_nick)
            except Exception:
                pass

            lvl_embed = discord.Embed(
                title="🎉 LEVEL UP! เลเวลอัปแล้ว!",
                description=(
                    f"ยินดีด้วยครับคุณ {member.mention}! 🌟\n\n"
                    f"✨ เลเวลของคุณอัปเป็น **`Lv.{new_lvl}`** แล้ว!\n"
                    f"🏷️ ชื่อใหม่ในเซิร์ฟเวอร์: **`{new_nick}`**\n"
                    f"🔥 ค่าประสบการณ์สะสมทั้งหมด: `{total_xp:,} XP`"
                ),
                color=discord.Color.gold()
            )
            lvl_embed.set_thumbnail(url=member.display_avatar.url)
            lvl_msg = await message.channel.send(embed=lvl_embed)
            await asyncio.sleep(10)
            try:
                await lvl_msg.delete()
            except Exception:
                pass

    # 4. ระบบส่งต่อรูปภาพจาก #คุยเล่น ไป #รูปภาพ
    if message.channel.id == CHAT_CHANNEL_ID:
        photo_channel = message.guild.get_channel(PHOTO_CHANNEL_ID)
        image_attachments = [
            att for att in message.attachments 
            if att.content_type and any(att.content_type.startswith(t) for t in ['image/', 'video/'])
        ]

        if image_attachments and photo_channel:
            sent_target_ids = []
            for att in image_attachments:
                embed = discord.Embed(
                    title=f"📸 อัลบั้มรูปภาพ • {message.author.display_name}",
                    description=f"{message.content}\n\n[👉 ดูข้อความต้นฉบับในห้อง #คุยเล่น]({message.jump_url})",
                    color=discord.Color.pink()
                )
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                if att.content_type.startswith('image/'):
                    embed.set_image(url=att.url)
                embed.set_footer(text=f"ส่งเมื่อ • {message.created_at.strftime('%d/%m/%Y %H:%M')}")
                
                if att.content_type.startswith('video/'):
                    m1 = await photo_channel.send(embed=embed)
                    m2 = await photo_channel.send(att.url)
                    sent_target_ids.extend([m1.id, m2.id])
                else:
                    m1 = await photo_channel.send(embed=embed)
                    sent_target_ids.append(m1.id)

            if sent_target_ids:
                photo_message_map[str(message.id)] = sent_target_ids
                save_photo_map(photo_message_map)

            try:
                await message.add_reaction("📸")
            except Exception:
                pass

    await bot.process_commands(message)

# ==================== ⚔️ คำสั่งระบบอาชีพ Ragnarok ====================

@bot.command(name="rojob", aliases=["อาชีพ", "job", "เลือกอาชีพ", "ro"])
async def cmd_rojob(ctx):
    """
    ⚔️ เมนูเลือกอาชีพ Ragnarok และใส่อิโมจิอาชีพนำหน้าชื่ออัตโนมัติ
    """
    embed = discord.Embed(
        title="⚔️ เมนูเลือกอาชีพ Ragnarok Online 🎮",
        description=(
            f"สวัสดีครับคุณ {ctx.author.mention}! 🏰\n\n"
            "กรุณาเลือกอาชีพที่คุณเล่นจากเมนูดรอปดาวน์ด้านล่างนี้ได้เลยครับ:\n\n"
            "✨ **สิทธิประโยชน์ที่จะได้รับ:**\n"
            "• 🏷️ **รับยศประจำอาชีพของคุณ**\n"
            "• 👑 **ใส่อิโมจิประจำอาชีพไว้หน้าชื่อเล่นของคุณในเซิร์ฟเวอร์**\n"
            "• ⚔️ **เพื่อนๆ ในตี้จะเห็นอาชีพของคุณทันทีตอนหาตี้ลงดัน!**"
        ),
        color=discord.Color.from_rgb(255, 215, 0)
    )
    embed.set_thumbnail(url="https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=800&q=80")
    embed.set_footer(text="Gamers' Café • Ragnarok Job System")
    await ctx.send(embed=embed, view=ROJobSelectView(ctx.author.id))

# ==================== ⭐ คำสั่งระบบเครดิต ====================

@bot.command(name="rep", aliases=["เครดิต", "+rep", "-rep"])
async def cmd_rep(ctx, target_member: discord.Member = None, rep_val: str = None, *, review_comment: str = None):
    if target_member is None:
        target_member = ctx.author

    if rep_val is None:
        await show_reputation_card(ctx, target_member)
        return

    rep_val_clean = rep_val.strip()
    if rep_val_clean not in ["+1", "+", "-1", "-", "บวก", "ลบ"]:
        if review_comment:
            review_comment = f"{rep_val} {review_comment}"
        else:
            review_comment = rep_val
        rep_val_clean = "+1"

    is_pos = rep_val_clean in ["+1", "+", "บวก"]

    if target_member.id == ctx.author.id:
        await ctx.send("❌ **ไม่สามารถให้คะแนนเครดิตตัวเองได้ครับ!**")
        return

    if target_member.bot:
        await ctx.send("❌ ไม่สามารถให้คะแนนเครดิตบอทได้ครับ!")
        return

    target_uid = str(target_member.id)
    voter_uid = str(ctx.author.id)
    r_data = get_user_rep_data(target_uid)
    voters = r_data.get("voters", {})

    if voter_uid in voters and ctx.author.id != ctx.guild.owner_id:
        await ctx.send(f"⚠️ **คุณเคยให้คะแนนคุณ {target_member.mention} ไปแล้วครับ!** (จำกัด 1 คน ต่อ 1 ผู้ใช้)")
        return

    comment_text = review_comment.strip() if review_comment else ("ซื้อขายเรียบร้อย" if is_pos else "พบปัญหาในการซื้อขาย")

    voters[voter_uid] = {
        "from_id": ctx.author.id,
        "from_name": ctx.author.display_name,
        "type": "+1" if is_pos else "-1",
        "comment": comment_text,
        "time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    r_data["voters"] = voters
    save_reputation(user_reputation_db)

    score, _ = calc_rep_counts(target_uid)
    await update_seller_roles(ctx.guild, target_member, score)

    embed = discord.Embed(
        title="⭐ บันทึกเครดิตสำเร็จ!" if is_pos else "⚠️ บันทึกรายงานปัญหาสำเร็จ!",
        description=(
            f"👤 **ผู้ให้คะแนน:** {ctx.author.mention}\n"
            f"🛍️ **คนขาย:** {target_member.mention}\n\n"
            "───────────────────────────\n\n"
            f"💬 **ข้อความ:** *\"{comment_text}\"*\n\n"
            f"⭐ **เครดิตสะสมทั้งหมด:** **`{score}` คะแนน**"
        ),
        color=discord.Color.green() if is_pos else discord.Color.red()
    )
    embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.set_footer(text="Gamers' Café Community Reputation")
    await ctx.send(embed=embed)

async def show_reputation_card(ctx, target_member: discord.Member):
    target_uid = str(target_member.id)
    score, reviews = calc_rep_counts(target_uid)

    if score >= 15:
        status_text = "👑 **พ่อค้าดีเด่น (Top Trusted Merchant)**"
        badge_icon = "👑"
        color = discord.Color.gold()
    elif score >= 5:
        status_text = "⭐ **พ่อค้าเครดิตดี (Verified Merchant)**"
        badge_icon = "⭐"
        color = discord.Color.green()
    elif score < 0:
        status_text = "⚠️ **มีประวัติถูกร้องเรียน (Caution)**"
        badge_icon = "⚠️"
        color = discord.Color.red()
    else:
        status_text = "⚪ **ประวัติการซื้อขายทั่วไป**"
        badge_icon = "⚪"
        color = discord.Color.light_grey()

    review_lines = []
    if reviews:
        for r in reviews[-3:]:
            icon = "✅" if r.get("type") == "+1" else "❌"
            review_lines.append(f"{icon} **{r.get('from_name', 'ลูกค้า')}:** *\"{r.get('comment', '')}\"*")
    else:
        review_lines = ["*ยังไม่มีประวัติรีวิวจากลูกค้า*"]

    embed = discord.Embed(
        title=f"{badge_icon} ข้อมูลเครดิต • {target_member.display_name}",
        description=(
            f"• 👤 **คนขาย:** {target_member.mention} (`{target_member.name}`)\n"
            f"• 🛡️ **สถานะ:** {status_text}\n"
            f"• ⭐ **เครดิตสะสม:** **`{score}` คะแนน**\n\n"
            "───────────────────────────\n\n"
            "💬 **รีวิวล่าสุด:**\n"
            + "\n".join(review_lines)
        ),
        color=color
    )
    embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.set_footer(text="Gamers' Café Reputation System")
    await ctx.send(embed=embed)

@bot.command(name="checkrep", aliases=["ดูเครดิต", "เช็คเครดิต"])
async def cmd_checkrep(ctx, target_member: discord.Member = None):
    member = target_member or ctx.author
    await show_reputation_card(ctx, member)

@bot.command(name="toprep", aliases=["toptraders", "อันดับเครดิต"])
async def cmd_toprep(ctx):
    scored_users = []
    for uid_str in user_reputation_db.keys():
        score, _ = calc_rep_counts(uid_str)
        if score > 0:
            scored_users.append((uid_str, score))

    scored_users.sort(key=lambda x: x[1], reverse=True)
    top10 = scored_users[:10]

    lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, (uid_str, score) in enumerate(top10):
        m = ctx.guild.get_member(int(uid_str))
        name = extract_base_name(m.display_name) if m else f"User {uid_str}"
        medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
        badge_tag = "👑 พ่อค้าดีเด่น" if score >= 15 else ("⭐ เครดิตดี" if score >= 5 else "🔰 ทั่วไป")
        lines.append(f"{medal} **{name}** — `{badge_tag}` ⭐ **`{score}` เครดิต**")

    if not lines:
        lines = ["*ยังไม่มีข้อมูลอันดับพ่อค้าในระบบ*"]

    embed = discord.Embed(
        title="🏆 อันดับพ่อค้าที่มีเครดิตสูงสุดในตลาด (Top Trusted Merchants)",
        description="\n\n".join(lines),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Gamers' Café Marketplace Leaderboard")
    await ctx.send(embed=embed)

# ==================== คำสั่งระบบวันเกิด (Birthday System) ====================

@bot.command(name="setbirthday", aliases=["setbd", "ตั้งวันเกิด"])
async def cmd_setbirthday(ctx, *, date_str: str = None):
    if not date_str:
        await ctx.send("❓ **วิธีตั้งวันเกิด:** `!setbirthday [วัน] [เดือน]` (เช่น `!setbirthday 30 8` หรือ `!setbirthday 15/3`)")
        return

    clean_str = date_str.replace("/", " ").replace("-", " ").replace(",", " ")
    parts = clean_str.split()

    if len(parts) < 2:
        await ctx.send("❌ รูปแบบไม่ถูกต้อง! กรุณาพิมพ์: `!setbirthday [วัน] [เดือน]` เช่น `!setbirthday 30 8`")
        return

    try:
        day = int(parts[0])
        month = int(parts[1])
    except ValueError:
        await ctx.send("❌ วันและเดือนต้องเป็นตัวเลขครับ! เช่น `!setbirthday 30 8`")
        return

    if not (1 <= month <= 12 and 1 <= day <= 31):
        await ctx.send("❌ วันหรือเดือนไม่ถูกต้อง! (วัน: 1-31, เดือน: 1-12)")
        return

    uid = str(ctx.author.id)
    user_birthdays_db[uid] = {
        "day": day,
        "month": month,
        "last_celebrated": ""
    }
    save_birthdays(user_birthdays_db)

    month_name = THAI_MONTHS[month]
    embed = discord.Embed(
        title="🎂 บันทึกวันเกิดสำเร็จ! (Birthday Saved)",
        description=(
            f"บันทึกวันเกิดของคุณ {ctx.author.mention} เรียบร้อยแล้วครับ! 🎈\n\n"
            f"📅 **วันเกิดของคุณ:** วันที่ **`{day} {month_name}`**\n\n"
            f"✨ *เมื่อถึงวันเกิดของคุณ บอทจะมอบยศพิเศษ `🎂・Birthday` พร้อมของขวัญ `+500 ☕ Coins` ให้อัตโนมัติครับ!*"
        ),
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="Gamers' Café Birthday System")
    await ctx.send(embed=embed)

@bot.command(name="birthday", aliases=["mybirthday", "bd"])
async def cmd_birthday(ctx, target_member: discord.Member = None):
    member = target_member or ctx.author
    uid = str(member.id)
    b_data = user_birthdays_db.get(uid)

    if not b_data:
        if member.id == ctx.author.id:
            await ctx.send(f"⚠️ คุณยังไม่ได้ลงทะเบียนวันเกิด! พิมพ์ `!setbirthday [วัน] [เดือน]` เพื่อลงทะเบียนครับ")
        else:
            await ctx.send(f"⚠️ คุณ {member.display_name} ยังไม่ได้ลงทะเบียนวันเกิดในระบบครับ")
        return

    b_day = b_data.get("day")
    b_month = b_data.get("month")
    month_name = THAI_MONTHS[b_month]

    embed = discord.Embed(
        title=f"🎂 ข้อมูลวันเกิด • {member.display_name}",
        description=f"📅 วันเกิด: **`{b_day} {month_name}`** 🎉",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Gamers' Café Birthday System")
    await ctx.send(embed=embed)

@bot.command(name="birthdays", aliases=["upcomingbirthdays", "วันเกิด"])
async def cmd_birthdays(ctx):
    now = datetime.datetime.now()
    curr_month = now.month
    month_name = THAI_MONTHS[curr_month]

    this_month_bds = []
    for uid_str, data in user_birthdays_db.items():
        if data.get("month") == curr_month:
            m = ctx.guild.get_member(int(uid_str))
            name = extract_base_name(m.display_name) if m else f"User {uid_str}"
            this_month_bds.append((data.get("day", 1), name, uid_str))

    this_month_bds.sort(key=lambda x: x[0])

    lines = []
    for day, name, uid in this_month_bds:
        lines.append(f"• 🎈 **วันที่ {day} {month_name}:** <@{uid}> (`{name}`)")

    if not lines:
        lines = [f"*ยังไม่มีสมาชิกที่เกิดในเดือน {month_name} ลงทะเบียนไว้*"]

    embed = discord.Embed(
        title=f"🎂 รายชื่อคนเกิดในเดือนนี้ • {month_name}",
        description="\n\n".join(lines) + f"\n\n───────────────────────────────\n💡 *พิมพ์ `!setbirthday [วัน] [เดือน]` เพื่อลงทะเบียนวันเกิดของคุณ*",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Gamers' Café Birthday List")
    await ctx.send(embed=embed)

# ==================== คำสั่งระบบเศรษฐกิจ & ร้านค้า ====================

@bot.command(name="daily")
async def cmd_daily(ctx):
    uid = str(ctx.author.id)
    now = time.time()
    
    if uid not in user_economy_db:
        user_economy_db[uid] = {"coins": 200, "last_daily": 0}
    
    last_daily = user_economy_db[uid].get("last_daily", 0)
    cooldown = 24 * 3600

    if now - last_daily < cooldown:
        remaining = int(cooldown - (now - last_daily))
        hours = remaining // 3600
        mins = (remaining % 3600) // 60
        embed = discord.Embed(
            title="⏰ คุณกดรับเหรียญรายวันไปแล้ว!",
            description=f"คุณ {ctx.author.mention} สามารถกลับมากดรับได้ใหม่อีกครั้งใน:\n\n⏳ **`{hours} ชั่วโมง {mins} นาที`**",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        return

    reward = random.randint(100, 300)
    user_economy_db[uid]["coins"] = user_economy_db[uid].get("coins", 200) + reward
    user_economy_db[uid]["last_daily"] = now
    save_economy(user_economy_db)

    total_coins = user_economy_db[uid]["coins"]
    embed = discord.Embed(
        title="☕ เช็คอินรับเหรียญรายวันสำเร็จ! 🎁",
        description=(
            f"ยินดีด้วยครับคุณ {ctx.author.mention}! 🌟\n\n"
            f"🎉 ได้รับเหรียญฟรี: **`+{reward:,} ☕ Cafe Coins`**\n"
            f"💰 ยอดเหรียญสะสมปัจจุบัน: **`{total_coins:,} ☕ Coins`**\n\n"
            f"💡 *ไปที่ห้อง <#1543523068767506445> เพื่อเลือกแลกของตกแต่งโปรไฟล์ได้เลยครับ!*"
        ),
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="Gamers' Café Daily Rewards")
    await ctx.send(embed=embed)

@bot.command(name="balance", aliases=["bal", "wallet", "coins", "money"])
async def cmd_balance(ctx, target_member: discord.Member = None):
    member = target_member or ctx.author
    uid = str(member.id)
    coins = get_user_coins(uid)

    embed = discord.Embed(
        title=f"💰 กระเป๋าเหรียญ • {member.display_name}",
        description=f"คุณมีเหรียญสะสมทั้งหมด:\n\n🪙 **`{coins:,} ☕ Cafe Coins`**",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Gamers' Café Economy")
    await ctx.send(embed=embed)

@bot.command(name="shop", aliases=["store", "ร้านค้า"])
async def cmd_shop(ctx):
    uid = str(ctx.author.id)
    my_coins = get_user_coins(uid)

    lines = []
    for item_id, item in SHOP_ITEMS.items():
        lines.append(f"**[{item_id}] `{item['name']}`** — 💰 **`{item['price']:,} ☕ Coins`**\n> 📝 *{item['desc']}*")

    embed = discord.Embed(
        title="🛒 ร้านค้ายศ & ฉายาพิเศษ • Gamers’ Café Shop",
        description=(
            f"👤 **เหรียญของคุณ:** `{my_coins:,} ☕ Coins`\n\n"
            "───────────────────────────────\n\n"
            + "\n\n".join(lines) +
            "\n\n───────────────────────────────\n\n"
            "👉 **สั่งซื้อสะดวกกว่า:** ไปที่ห้อง <#1543523068767506445> แล้วกดปุ่มซื้อได้ทันทีใน 1 คลิก!"
        ),
        color=discord.Color.purple()
    )
    if os.path.exists(BANNER_PATH):
        file = discord.File(BANNER_PATH, filename="shop_cover.jpg")
        embed.set_image(url="attachment://shop_cover.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

@bot.command(name="buy", aliases=["ซื้อ"])
async def cmd_buy(ctx, *, item_query: str = None):
    if not item_query:
        await ctx.send("❓ **วิธีสั่งซื้อ:** `!buy [หมายเลขไอเทม]` (เช่น `!buy 1` หรือ `!buy 6`)\n*หรือไปที่ห้อง <#1543523068767506445> เพื่อกดปุ่มซื้อได้เลยครับ*")
        return

    item_query = item_query.strip()
    target_item = None

    if item_query in SHOP_ITEMS:
        target_item = SHOP_ITEMS[item_query]
    else:
        for it in SHOP_ITEMS.values():
            if item_query.lower() in it["name"].lower():
                target_item = it
                break

    if not target_item:
        await ctx.send("❌ **ไม่พบสินค้าชิ้นนี้ในร้านค้า!** กรุณาพิมพ์ `!shop` เพื่อดูหมายเลขสินค้าที่ถูกต้อง")
        return

    uid = str(ctx.author.id)
    my_coins = get_user_coins(uid)
    price = target_item["price"]
    role_name = target_item["name"]

    if my_coins < price:
        await ctx.send(f"❌ **เหรียญไม่พอครับ!** คุณมี `{my_coins:,} Coins` แต่สินค้านี้ราคา `{price:,} Coins` *(ขาดอีก {price - my_coins:,} Coins)*")
        return

    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"⚠️ ไม่พบยศ `{role_name}` ในเซิร์ฟเวอร์ กรุณาติดต่อแอดมิน")
        return

    if role in ctx.author.roles:
        await ctx.send(f"⚠️ คุณมียศ `{role_name}` อยู่ในครอบครองแล้วครับ!")
        return

    user_economy_db[uid]["coins"] -= price
    save_economy(user_economy_db)

    try:
        await ctx.author.add_roles(role)
    except Exception as e:
        await ctx.send(f"❌ มอบยศไม่สำเร็จ: {e}")
        return

    embed = discord.Embed(
        title="🎉 สั่งซื้อสินค้าสำเร็จ! (Purchase Completed)",
        description=(
            f"ยินดีด้วยครับคุณ {ctx.author.mention}! 🛍️\n\n"
            f"🏷️ **ได้รับยศ:** {role.mention}\n"
            f"💰 **ชำระเงิน:** `-{price:,} ☕ Coins`\n"
            f"🪙 **เหรียญคงเหลือ:** `{user_economy_db[uid]['coins']:,} ☕ Coins`"
        ),
        color=discord.Color.brand_green()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="Gamers' Café Shop")
    await ctx.send(embed=embed)

@bot.command(name="slot", aliases=["gamble", "spin"])
async def cmd_slot(ctx, bet: int = 50):
    if bet < 10:
        await ctx.send("❌ เดิมพันขั้นต่ำ 10 ☕ Coins ครับ!")
        return

    uid = str(ctx.author.id)
    my_coins = get_user_coins(uid)

    if my_coins < bet:
        await ctx.send(f"❌ เหรียญไม่พอครับ! คุณมี `{my_coins:,} Coins` แต่ต้องการหมุน `{bet:,} Coins`")
        return

    symbols = ["🍒", "🍋", "🍇", "💎", "👑", "7️⃣"]
    s1 = random.choice(symbols)
    s2 = random.choice(symbols)
    s3 = random.choice(symbols)

    multiplier = 0
    if s1 == s2 == s3:
        if s1 == "7️⃣":
            multiplier = 10
        elif s1 == "👑":
            multiplier = 5
        elif s1 == "💎":
            multiplier = 4
        else:
            multiplier = 3
    elif s1 == s2 or s2 == s3 or s1 == s3:
        multiplier = 1.5

    win_amount = int(bet * multiplier)
    net_change = win_amount - bet

    user_economy_db[uid]["coins"] += net_change
    save_economy(user_economy_db)
    new_coins = user_economy_db[uid]["coins"]

    if net_change > 0:
        res_title = "🎰 JACKPOT! คุณชนะการเดิมพัน! 🎉"
        res_color = discord.Color.gold()
        res_desc = f"🎉 **ยินดีด้วยครับ! คุณได้รับเงินรางวัล:** `+{win_amount:,} ☕ Coins` (กำไร `+{net_change:,}`)"
    else:
        res_title = "🎰 เสียใจด้วยครับ รอบนี้คุณไม่ถูกรางวัล"
        res_color = discord.Color.dark_grey()
        res_desc = f"💸 **เสียเงินเดิมพัน:** `-{bet:,} ☕ Coins`\n*ลองใหม่อีกครั้งนะครับ!*"

    embed = discord.Embed(
        title=res_title,
        description=(
            f"━━━━━━━━━━━━━━━━━━\n"
            f"   🎰  [ **{s1}** | **{s2}** | **{s3}** ]  🎰\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{res_desc}\n\n"
            f"🪙 **เหรียญคงเหลือ:** `{new_coins:,} ☕ Coins`"
        ),
        color=res_color
    )
    embed.set_footer(text="Gamers' Café Casino")
    await ctx.send(embed=embed)

@bot.command(name="give", aliases=["pay", "โอน"])
async def cmd_give(ctx, target_member: discord.Member = None, amount: int = None):
    if not target_member or not amount or amount <= 0:
        await ctx.send("❓ **วิธีโอนเหรียญ:** `!give @ชื่อเพื่อน [จำนวนเหรียญ]` (เช่น `!give @โจ้ 100`)")
        return

    if target_member.id == ctx.author.id:
        await ctx.send("❌ ไม่สามารถโอนเหรียญให้ตัวเองได้ครับ!")
        return

    sender_uid = str(ctx.author.id)
    receiver_uid = str(target_member.id)

    sender_coins = get_user_coins(sender_uid)
    if sender_coins < amount:
        await ctx.send(f"❌ เหรียญไม่พอครับ! คุณมี `{sender_coins:,} Coins` ไม่สามารถโอน `{amount:,} Coins` ได้")
        return

    user_economy_db[sender_uid]["coins"] -= amount
    add_user_coins(receiver_uid, amount)
    save_economy(user_economy_db)

    embed = discord.Embed(
        title="💸 โอนเหรียญสำเร็จ! (Transfer Successful)",
        description=(
            f"คุณ {ctx.author.mention} ได้โอนเหรียญให้คุณ {target_member.mention} เรียบร้อยแล้ว!\n\n"
            f"💰 **จำนวนที่โอน:** `+{amount:,} ☕ Cafe Coins`\n"
            f"🪙 **เหรียญคงเหลือของคุณ:** `{user_economy_db[sender_uid]['coins']:,} ☕ Coins`"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ==================== คำสั่งทั่วไปสำหรับสมาชิก ====================

@bot.command(name="rank", aliases=["level", "lvl"])
async def cmd_rank(ctx, target_member: discord.Member = None):
    member = target_member or ctx.author
    uid = str(member.id)
    base_name = user_levels_db.get(uid, {}).get("base_name", extract_base_name(member.display_name))
    data = user_levels_db.get(uid, {"xp": 0, "level": 1, "base_name": base_name})
    
    current_xp = data.get("xp", 0)
    current_lvl = data.get("level", 1)
    
    curr_lvl_base_xp = xp_for_level(current_lvl)
    next_lvl_xp = xp_for_level(current_lvl + 1)
    
    xp_in_level = current_xp - curr_lvl_base_xp
    xp_needed_level = next_lvl_xp - curr_lvl_base_xp
    
    pct = min(100, max(0, int((xp_in_level / max(1, xp_needed_level)) * 100)))
    
    filled = int(pct / 10)
    empty = 10 - filled
    bar = "🟩" * filled + "⬜" * empty

    embed = discord.Embed(
        title=f"📊 โปรไฟล์เลเวล • {member.display_name}",
        description=(
            f"👤 **ชื่อในเซิร์ฟเวอร์:** `{base_name}`\n"
            f"⭐ **ระดับเลเวล:** `Lv.{current_lvl}`\n"
            f"🔥 **ค่าประสบการณ์ (XP):** `{current_xp:,}` / `{next_lvl_xp:,} XP`\n\n"
            f"**ความคืบหน้าสู่ Lv.{current_lvl + 1}:**\n"
            f"`{bar}` **{pct}%**\n\n"
            f"💡 *คุยเล่นในแชทหรือเข้าห้องเสียงเพื่อสะสม XP เพิ่มเลเวลได้ตลอด 24 ชม.*"
        ),
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Gamers' Café Level System")
    await ctx.send(embed=embed)

@bot.command(name="top", aliases=["leaderboard", "lb"])
async def cmd_leaderboard(ctx):
    guild = ctx.guild
    sorted_users = sorted(user_levels_db.items(), key=lambda item: item[1].get("xp", 0), reverse=True)[:10]

    lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, (uid_str, data) in enumerate(sorted_users):
        m = guild.get_member(int(uid_str))
        name = data.get("base_name", extract_base_name(m.display_name) if m else f"User {uid_str}")
        lvl = data.get("level", 1)
        xp = data.get("xp", 0)
        medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
        lines.append(f"{medal} **{name} [Lv.{lvl}]** — (`{xp:,} XP`)")

    if not lines:
        lines = ["*ยังไม่มีข้อมูลอันดับในระบบ*"]

    embed = discord.Embed(
        title="🏆 อันดับผู้เล่นที่มีเลเวลสูงสุด (Leaderboard)",
        description="\n\n".join(lines),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Gamers' Café • Rank Leaderboard")
    await ctx.send(embed=embed)

@bot.command(name="roll")
async def cmd_roll(ctx, max_val: int = 100):
    if max_val < 1:
        max_val = 100
    res = random.randint(1, max_val)
    embed = discord.Embed(
        title="🎲 ผลการทอยเต๋า / สุ่มตัวเลข",
        description=f"คุณ {ctx.author.mention} ทอยสุ่มตัวเลข (1 - {max_val}):\n\n🎯 ได้แต้ม: **`{res}`**",
        color=discord.Color.teal()
    )
    await ctx.send(embed=embed)

@bot.command(name="flip", aliases=["coinflip", "toss"])
async def cmd_flip(ctx):
    res = random.choice(["👑 หัว (Heads)", "🪙 ก้อย (Tails)"])
    embed = discord.Embed(
        title="🪙 ผลการโยนเหรียญ",
        description=f"คุณ {ctx.author.mention} โยนเหรียญเสี่ยงทาย:\n\n✨ ผลที่ออกคือ: **`{res}`**",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name="choose", aliases=["pick"])
async def cmd_choose(ctx, *choices):
    if not choices:
        await ctx.send("❓ **วิธีใช้คำสั่ง:** `!choose [ตัวเลือก1] [ตัวเลือก2] [ตัวเลือก3]...` (เช่น `!choose Valorant RoV Ragnarok`)")
        return
    chosen = random.choice(choices)
    embed = discord.Embed(
        title="🤖 บอทตัดสินใจเลือกให้แล้ว!",
        description=f"จากตัวเลือกทั้งหมด: {', '.join([f'`{c}`' for c in choices])}\n\n👉 บอทเลือก: **`{chosen}`** 🎉",
        color=discord.Color.brand_green()
    )
    await ctx.send(embed=embed)

@bot.command(name="profile", aliases=["userinfo", "whois"])
async def cmd_profile(ctx, target_member: discord.Member = None):
    member = target_member or ctx.author
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    roles_str = ", ".join([f"`{r}`" for r in roles]) if roles else "`ไม่มีบทบาท`"
    
    uid = str(member.id)
    lvl = user_levels_db.get(uid, {}).get("level", 1)
    xp = user_levels_db.get(uid, {}).get("xp", 0)
    coins = get_user_coins(uid)

    joined_at = member.joined_at.strftime("%d/%m/%Y %H:%M") if member.joined_at else "ไม่ทราบ"
    created_at = member.created_at.strftime("%d/%m/%Y %H:%M")

    b_data = user_birthdays_db.get(uid)
    b_text = f"{b_data['day']} {THAI_MONTHS[b_data['month']]}" if b_data else "ยังไม่ได้ระบุ"

    score, _ = calc_rep_counts(uid)
    rep_badge = "👑 พ่อค้าดีเด่น" if score >= 15 else ("⭐ เครดิตดี" if score >= 5 else "🔰 ทั่วไป")

    embed = discord.Embed(
        title=f"👤 ข้อมูลโปรไฟล์ • {member.display_name}",
        description=(
            f"• 🆔 **User ID:** `{member.id}`\n"
            f"• ⭐ **ระดับเลเวล:** `Lv.{lvl}` (`{xp:,} XP`)\n"
            f"• 🪙 **เหรียญสะสม:** `{coins:,} ☕ Cafe Coins`\n"
            f"• 🛡️ **เครดิตตลาด:** {rep_badge} (`{score}` คะแนน)\n"
            f"• 🎂 **วันเกิด:** `{b_text}`\n"
            f"• 📅 **สร้างบัญชีเมื่อ:** `{created_at}`\n"
            f"• 🚪 **เข้าร่วมเซิร์ฟเวอร์:** `{joined_at}`\n\n"
            f"🏷️ **ยศ/บทบาททั้งหมด:**\n{roles_str}"
        ),
        color=discord.Color.dark_purple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Gamers' Café User Profile")
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", aliases=["server"])
async def cmd_serverinfo(ctx):
    guild = ctx.guild
    text_ch_count = len(guild.text_channels)
    voice_ch_count = len(guild.voice_channels)
    roles_count = len(guild.roles)

    embed = discord.Embed(
        title=f"🏰 ข้อมูลเซิร์ฟเวอร์ • {guild.name}",
        description=(
            f"• 👑 **เจ้าของเซิร์ฟเวอร์:** <@{guild.owner_id}>\n"
            f"• 👥 **จำนวนสมาชิกทั้งหมด:** `{guild.member_count}` คน\n"
            f"• 💬 **ห้องข้อความ:** `{text_ch_count}` ห้อง\n"
            f"• 🔊 **ห้องเสียง:** `{voice_ch_count}` ห้อง\n"
            f"• 🏷️ **จำนวนยศทั้งหมด:** `{roles_count}` ยศ\n"
            f"• 📅 **สร้างเซิร์ฟเวอร์เมื่อ:** `{guild.created_at.strftime('%d/%m/%Y')}`"
        ),
        color=discord.Color.gold()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Gamers' Café Server Info")
    await ctx.send(embed=embed)

async def handle_ping(request):
    return web.Response(text="Gamers' Cafe Bot is Running Online!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/healthz", handle_ping)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[🌐 Web Server] Health-check web server running on port {port}")

async def main():
    await start_web_server()
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("[Boot] กำลังเริ่มการทำงานบอท Gamers' Café...")
        print("=" * 60)
        asyncio.run(main())
    except Exception as e:
        import traceback
        print(f"[FATAL ERROR IN BOT]: {e}")
        traceback.print_exc()
        time.sleep(60)
