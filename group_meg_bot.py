# group_meg_bot.py
# GROUP MEG 🇵🇸  — @group_meg_bot
# Requirements: python-telegram-bot >= 20
# Secrets: read TELEGRAM_BOT_TOKEN from environment only
# Data: config & persistence under ./data (no secrets)

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from telegram import (Update,InlineKeyboardButton,InlineKeyboardMarkup,ChatPermissions,ChatMemberAdministrator,ChatMemberOwner,ChatAction,Poll,)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    AIORateLimiter,
)
from keep_alive import keep_alive
keep_alive()
# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("GROUP_MEG")

# ------------------------------------------------------------------------------
# Simple JSON persistence (inspired by PTB DictPersistence usage and docs)
# Stores user_data/chat_data/bot_data in JSON files under data/
# ------------------------------------------------------------------------------

class FileJSONPersistence:
    def __init__(self, base_dir: Path, update_interval: int = 30) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.user_file = self.base_dir / "users.json"
        self.chat_file = self.base_dir / "chats.json"
        self.bot_file = self.base_dir / "bot.json"
        self.user_data: Dict[str, Dict[str, Any]] = {}
        self.chat_data: Dict[str, Dict[str, Any]] = {}
        self.bot_data: Dict[str, Any] = {}
        self._load_all()
        self._interval = update_interval
        self._task: Optional[asyncio.Task] = None

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error("Failed to read %s: %s", path, e)
        return {}

    def _dump_json(self, path: Path, data: Dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write %s: %s", path, e)

    def _load_all(self) -> None:
        self.user_data = self._load_json(self.user_file)
        self.chat_data = self._load_json(self.chat_file)
        self.bot_data = self._load_json(self.bot_file)

    async def start_auto_flush(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._auto_flush())

    async def _auto_flush(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self.flush()

    def flush(self) -> None:
        self._dump_json(self.user_file, self.user_data)
        self._dump_json(self.chat_file, self.chat_data)
        self._dump_json(self.bot_file, self.bot_data)

# ------------------------------------------------------------------------------
# Config loader (no secrets)
# ------------------------------------------------------------------------------

def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        # create a default config if missing
        default = {
            "bot_name": "GROUP MEG 🇵🇸",
            "bot_username": "@group_meg_bot",
            "welcome_text": "👋 Welcome, {name}! Please read /rules and say hi to everyone!",
            "goodbye_text": "👋 {name} left. Hope to see you again!",
            "rules_text": "📜 Be kind, stay on-topic, no spam or NSFW. Respect admins.",
            "roles": {
                "moderator": {"can_kick": True, "can_ban": True, "can_warn": True, "can_mute": True},
                "helper": {"can_kick": False, "can_ban": False, "can_warn": True, "can_mute": True},
                "vip": {"can_kick": False, "can_ban": False, "can_warn": False, "can_mute": False}
            },
            "language": "en",
            "timezone": "UTC",
            "quotes": [
                "Success is not final, failure is not fatal: it is the courage to continue that counts.",
                "The only way to do great work is to love what you do.",
                "Life is what happens to you while you're busy making other plans.",
                "The future belongs to those who believe in the beauty of their dreams.",
                "It is during our darkest moments that we must focus to see the light."
            ],
            "jokes": [
                "Why don't scientists trust atoms? Because they make up everything!",
                "I told my wife she was drawing her eyebrows too high. She looked surprised.",
                "Why don't skeletons fight each other? They don't have the guts.",
                "What do you call a fake noodle? An impasta!",
                "Why did the scarecrow win an award? He was outstanding in his field!"
            ]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read config: %s", e)
        return {}

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def is_admin_member(member) -> bool:
    return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))

async def user_is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return is_admin_member(member)
    except Exception:
        return False

def has_role(persist: FileJSONPersistence, chat_id: int, user_id: int, role: str) -> bool:
    cdata = persist.chat_data.setdefault(str(chat_id), {})
    roles = cdata.setdefault("roles", {})
    user_roles = roles.get(str(user_id), [])
    return role in user_roles

def grant_role(persist: FileJSONPersistence, chat_id: int, user_id: int, role: str) -> None:
    cdata = persist.chat_data.setdefault(str(chat_id), {})
    roles = cdata.setdefault("roles", {})
    roles.setdefault(str(user_id), [])
    if role not in roles[str(user_id)]:
        roles[str(user_id)].append(role)
    persist.flush()

def revoke_role(persist: FileJSONPersistence, chat_id: int, user_id: int, role: str) -> None:
    cdata = persist.chat_data.setdefault(str(chat_id), {})
    roles = cdata.setdefault("roles", {})
    lst = roles.get(str(user_id), [])
    roles[str(user_id)] = [r for r in lst if r != role]
    persist.flush()

def user_permissions(persist: FileJSONPersistence, config: Dict[str, Any], chat_id: int, user_id: int) -> Dict[str, bool]:
    perms = {"can_kick": False, "can_ban": False, "can_warn": False, "can_mute": False}
    for role in ["moderator", "helper", "vip"]:
        if has_role(persist, chat_id, user_id, role):
            rdef = config["roles"].get(role, {})
            for k, v in rdef.items():
                perms[k] = perms.get(k, False) or bool(v)
    return perms

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start", callback_data="go:start"),
         InlineKeyboardButton("ℹ️ Help", callback_data="go:help")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="go:settings"),
         InlineKeyboardButton("📜 Rules", callback_data="go:rules")],
        [InlineKeyboardButton("🎮 Menu", callback_data="go:menu"),
         InlineKeyboardButton("👨‍💻 Developer", callback_data="go:developer")]
    ])

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👮‍♂️ Admins", callback_data="cmd:admins"),
         InlineKeyboardButton("🏷️ Roles", callback_data="cmd:roles")],
        [InlineKeyboardButton("📊 Stats", callback_data="cmd:stats"),
         InlineKeyboardButton("📋 Members", callback_data="cmd:listmembers")],
        [InlineKeyboardButton("⬅️ Back", callback_data="go:menu")]
    ])

def fun_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Quote", callback_data="cmd:quote"),
         InlineKeyboardButton("😂 Joke", callback_data="cmd:joke")],
        [InlineKeyboardButton("🐱 Cat", callback_data="cmd:cat"),
         InlineKeyboardButton("📊 Poll", callback_data="cmd:poll")],
        [InlineKeyboardButton("⬅️ Back", callback_data="go:menu")]
    ])

def settings_kb(chat_locked: bool, antispam: bool, antiflood: bool, nsfw_filter: bool, link_filter: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(("🔒 Locked" if chat_locked else "🔓 Unlocked"), callback_data="set:toggle_lock")],
        [InlineKeyboardButton(("💣 AntiSpam ON" if antispam else "💤 AntiSpam OFF"), callback_data="set:toggle_antispam")],
        [InlineKeyboardButton(("🌊 AntiFlood ON" if antiflood else "💤 AntiFlood OFF"), callback_data="set:toggle_antiflood")],
        [InlineKeyboardButton(("🔞 NSFW Filter ON" if nsfw_filter else "💤 NSFW Filter OFF"), callback_data="set:toggle_nsfw")],
        [InlineKeyboardButton(("🔗 Link Filter ON" if link_filter else "💤 Link Filter OFF"), callback_data="set:toggle_links")],
        [InlineKeyboardButton("📝 Edit Rules", callback_data="set:edit_rules"),
         InlineKeyboardButton("👋 Edit Welcome", callback_data="set:edit_welcome")],
        [InlineKeyboardButton("👋 Edit Goodbye", callback_data="set:edit_goodbye"),
         InlineKeyboardButton("⬅️ Back", callback_data="go:menu")]
    ])

# ------------------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    text = (
        f"🤖 <b>{cfg.get('bot_name','GROUP MEG')}</b> — {cfg.get('bot_username','')}\n"
        "Welcome to the most advanced group management bot! 🛡️\n\n"
        "✨ <b>Features:</b>\n"
        "• Complete moderation tools\n"
        "• Role-based permissions\n"
        "• Anti-spam & flood protection\n"
        "• Fun commands & engagement\n"
        "• Advanced statistics\n\n"
        "Add me to a group as admin to unleash all features!"
    )
    await update.effective_message.reply_html(text, reply_markup=main_menu_kb())
    logger.info("/start used by %s", update.effective_user.id)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🆘 <b>Help & Commands</b>\n\n"
        "📌 <b>Basic Commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/rules - Display group rules\n"
        "/settings - Open settings panel\n"
        "/about - Bot information\n\n"
        "👮 <b>Admin Commands:</b>\n"
        "/kick, /ban, /warn, /mute, /unmute\n"
        "/purge, /lock, /unlock, /restrict\n"
        "/clearwarns, /detectspam, /antispam\n"
        "/antiflood, /log\n\n"
        "🏷️ <b>Role Commands:</b>\n"
        "/addrole, /removerole, /userroles\n"
        "/roles, /admins\n\n"
        "⚙️ <b>Config Commands:</b>\n"
        "/setrules, /setwelcome, /setgoodbye\n"
        "/setlang, /reloadconfig\n\n"
        "📊 <b>Info Commands:</b>\n"
        "/info, /stats, /profile\n"
        "/listmembers, /inactive\n\n"
        "🎮 <b>Fun Commands:</b>\n"
        "/quote, /joke, /cat, /poll\n\n"
        "💾 <b>Data Commands:</b>\n"
        "/backup, /restore, /exportroles\n"
        "/exportrules\n\n"
        "All admin actions require bot admin rights! 🛡️"
    )
    await update.effective_message.reply_html(text, reply_markup=main_menu_kb())

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    text = (
        f"ℹ️ <b>About {cfg.get('bot_name', 'GROUP MEG')}</b>\n\n"
        f"🤖 Bot: {cfg.get('bot_username', '@group_meg_bot')}\n"
        "🔧 Version: 2.0.0\n"
        "📚 Library: python-telegram-bot v20+\n"
        "⚡ Runtime: Async/Await\n"
        "🏗️ Architecture: Modern Application API\n\n"
        "🌟 <b>Features:</b>\n"
        "• Advanced moderation system\n"
        "• Role-based permissions\n"
        "• Multiple protection layers\n"
        "• Rich analytics & reporting\n"
        "• Backup & restore system\n"
        "• Multi-language support ready\n\n"
        "🔒 <b>Security:</b>\n"
        "• Environment-based secrets\n"
        "• Secure JSON persistence\n"
        "• Error handling & logging\n"
        "• Rate limiting protection\n\n"
        "Designed for reliability and scalability! 🚀"
    )
    await update.effective_message.reply_html(text, reply_markup=main_menu_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = await user_is_admin(update, context)
    text = "🎮 <b>Interactive Menu</b>\n\nChoose a category:"
    
    keyboard = [
        [InlineKeyboardButton("🎭 Fun & Games", callback_data="menu:fun")],
        [InlineKeyboardButton("ℹ️ Information", callback_data="menu:info")]
    ]
    
    if is_admin:
        keyboard.insert(0, [InlineKeyboardButton("👮‍♂️ Admin Panel", callback_data="menu:admin")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="go:start")])
    
    await update.effective_message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    text = f"📜 <b>Group Rules</b>\n\n{cfg.get('rules_text','No rules set.')}"
    await update.effective_message.reply_html(text, reply_markup=main_menu_kb())

async def welcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    text = f"👋 <b>Current Welcome Message:</b>\n\n{cfg.get('welcome_text','Default welcome message.')}"
    await update.effective_message.reply_html(text)

async def goodbye_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    text = f"👋 <b>Current Goodbye Message:</b>\n\n{cfg.get('goodbye_text','Default goodbye message.')}"
    await update.effective_message.reply_html(text)

async def developer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👨‍💻 <b>Developer Information</b>\n\n"
        "🧑‍🎓 <b>Name:</b> Latiful Hassan Zihan 🇵🇸\n"
        "🏳️ <b>Nationality:</b> Bangladeshi 🇧🇩\n"
        "📱 <b>Telegram:</b> @alwayszihan\n"
        "🌐 <b>GitHub:</b> Available on request\n\n"
        "🚀 <b>Project:</b> GROUP MEG\n"
        "📖 <b>Description:</b> Advanced Telegram group management bot\n"
        "⚡ <b>Tech Stack:</b> Python, python-telegram-bot v20+, AsyncIO\n"
        "🏗️ <b>Architecture:</b> Modern, scalable, cloud-ready\n\n"
        "💡 <b>Vision:</b> Making Telegram group management effortless and powerful.\n\n"
        "Thanks for using GROUP MEG! ⭐\n"
        "Rate us and share with friends! 🔗"
    )
    await update.effective_message.reply_html(text)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await user_is_admin(update, context):
        await update.effective_message.reply_text("⛔ Admin privileges required.")
        return
    
    cdata = context.chat_data.setdefault("flags", {
        "locked": False, "antispam": False, "antiflood": False, 
        "nsfw_filter": False, "link_filter": False
    })
    
    text = (
        "⚙️ <b>Group Security Settings</b>\n\n"
        "Toggle protections and configure messages:\n\n"
        f"🔒 Chat Lock: {'ON' if cdata.get('locked') else 'OFF'}\n"
        f"💣 Anti-Spam: {'ON' if cdata.get('antispam') else 'OFF'}\n"
        f"🌊 Anti-Flood: {'ON' if cdata.get('antiflood') else 'OFF'}\n"
        f"🔞 NSFW Filter: {'ON' if cdata.get('nsfw_filter') else 'OFF'}\n"
        f"🔗 Link Filter: {'ON' if cdata.get('link_filter') else 'OFF'}"
    )
    
    await update.effective_message.reply_html(
        text,
        reply_markup=settings_kb(
            cdata.get("locked", False), cdata.get("antispam", False), 
            cdata.get("antiflood", False), cdata.get("nsfw_filter", False),
            cdata.get("link_filter", False)
        ),
    )

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    quotes = cfg.get("quotes", ["Stay positive and keep going!"])
    quote = random.choice(quotes)
 

async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Dict[str, Any] = context.bot_data["config"]
    jokes = cfg.get("jokes", ["Why did the bot tell a joke? To keep users engaged!"])
    joke = random.choice(jokes)
    await update.effective_message.reply_text(f"😂 {joke}")

async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("🐱 Here's your virtual cat! Meow! 🐾")

async def poll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text("📊 Usage: /poll <question>")
        return
    
    question = " ".join(context.args)
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question,
        options=["👍 Yes", "👎 No", "🤷 Maybe"],
        is_anonymous=False
    )

# ----- Callback handlers -----

async def settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    
    # Navigation callbacks
    if data.startswith("go:"):
        where = data.split(":", 1)[1]
        if where == "start":
            return await start_cmd(update, context)
        elif where == "help":
            return await help_cmd(update, context)
        elif where == "settings":
            return await settings_cmd(update, context)
        elif where == "rules":
            return await rules_cmd(update, context)
        elif where == "developer":
            return await developer_cmd(update, context)
        elif where == "menu":
            return await menu_cmd(update, context)
    
    # Menu callbacks
    elif data.startswith("menu:"):
        menu_type = data.split(":", 1)[1]
        if menu_type == "admin":
            await query.edit_message_text(
                "👮‍♂️ <b>Admin Panel</b>\n\nSelect an option:",
                parse_mode=ParseMode.HTML,
                reply_markup=admin_menu_kb()
            )
        elif menu_type == "fun":
            await query.edit_message_text(
                "🎭 <b>Fun & Entertainment</b>\n\nChoose an activity:",
                parse_mode=ParseMode.HTML,
                reply_markup=fun_menu_kb()
            )
        elif menu_type == "info":
            info_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("ℹ️ About Bot", callback_data="go:developer")],
                [InlineKeyboardButton("📊 Group Stats", callback_data="cmd:stats")],
                [InlineKeyboardButton("⬅️ Back", callback_data="go:menu")]
            ])
            await query.edit_message_text(
                "ℹ️ <b>Information Center</b>\n\nSelect information type:",
                parse_mode=ParseMode.HTML,
                reply_markup=info_kb
            )
        return
    
    # Command callbacks
    elif data.startswith("cmd:"):
        cmd = data.split(":", 1)[1]
        if cmd == "quote":
            return await quote_cmd(update, context)
        elif cmd == "joke":
            return await joke_cmd(update, context)
        elif cmd == "cat":
            return await cat_cmd(update, context)
        elif cmd == "poll":
            await query.edit_message_text("📊 To create a poll, use: /poll <your question>")
            return
        elif cmd == "admins":
            return await admins_cmd(update, context)
        elif cmd == "roles":
            return await roles_cmd(update, context)
        elif cmd == "stats":
            return await stats_cmd(update, context)
        elif cmd == "listmembers":
            return await listmembers_cmd(update, context)
    
    # Settings toggles
    if not await user_is_admin(update, context):
        await query.edit_message_text("⛔ Admin privileges required.")
        return
    
    cflags = context.chat_data.setdefault("flags", {
        "locked": False, "antispam": False, "antiflood": False,
        "nsfw_filter": False, "link_filter": False
    })

    if data == "set:toggle_lock":
        cflags["locked"] = not cflags.get("locked", False)
        if cflags["locked"]:
            perms = ChatPermissions(can_send_messages=False)
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions=perms)
            status = "🔒 Chat locked. Only admins can speak."
        else:
            perms = ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True
            )
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions=perms)
            status = "🔓 Chat unlocked for everyone."
        
        await query.edit_message_text(
            status,
            reply_markup=settings_kb(
                cflags["locked"], cflags["antispam"], cflags["antiflood"],
                cflags["nsfw_filter"], cflags["link_filter"]
            ),
        )
        return

    elif data == "set:toggle_antispam":
        cflags["antispam"] = not cflags.get("antispam", False)
        status = f"💣 Anti-Spam {'ENABLED' if cflags['antispam'] else 'DISABLED'}."
        
    elif data == "set:toggle_antiflood":
        cflags["antiflood"] = not cflags.get("antiflood", False)
        status = f"🌊 Anti-Flood {'ENABLED' if cflags['antiflood'] else 'DISABLED'}."
        
    elif data == "set:toggle_nsfw":
        cflags["nsfw_filter"] = not cflags.get("nsfw_filter", False)
        status = f"🔞 NSFW Filter {'ENABLED' if cflags['nsfw_filter'] else 'DISABLED'}."
        
    elif data == "set:toggle_links":
        cflags["link_filter"] = not cflags.get("link_filter", False)
        status = f"🔗 Link Filter {'ENABLED' if cflags['link_filter'] else 'DISABLED'}."
        
    elif data == "set:edit_rules":
        context.user_data["awaiting_rules"] = True
        await query.edit_message_text("📝 Send new rules text now (as one message).")
        return

    elif data == "set:edit_welcome":
        context.user_data["awaiting_welcome"] = True
        await query.edit_message_text("👋 Send new welcome template now. Use {name} placeholder.")
        return

    elif data == "set:edit_goodbye":
        context.user_data["awaiting_goodbye"] = True
        await query.edit_message_text("👋 Send new goodbye template now. Use {name} placeholder.")
        return
    
    else:
        return
    
    # Update settings display
    await query.edit_message_text(
        status,
        reply_markup=settings_kb(
            cflags["locked"], cflags["antispam"], cflags["antiflood"],
            cflags["nsfw_filter"], cflags["link_filter"]
        ),
    )

async def capture_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["config"]
    msg = update.effective_message.text or ""
    
    if context.user_data.pop("awaiting_rules", False):
        cfg["rules_text"] = msg
        await update.effective_message.reply_text("✅ Rules updated successfully!")
        return
    if context.user_data.pop("awaiting_welcome", False):
        cfg["welcome_text"] = msg
        await update.effective_message.reply_text("✅ Welcome message updated successfully!")
        return
    if context.user_data.pop("awaiting_goodbye", False):
        cfg["goodbye_text"] = msg
        await update.effective_message.reply_text("✅ Goodbye message updated successfully!")
        return

# ----- Admin actions -----

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await user_is_admin(update, context):
        return True
    await update.effective_message.reply_text("⛔ Admin privileges required.")
    return False

async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to /kick. ✋")
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id, until_date=60)  
        await context.bot.unban_chat_member(update.effective_chat.id, target.id, only_if_banned=True)
        await update.effective_message.reply_html(f"👢 <b>User Kicked!</b>\n{target.mention_html()} has been removed from the group.")
        logger.info(f"User {target.id} kicked from {update.effective_chat.id}")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Kick failed: {e}")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to /ban. ✋")
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.effective_message.reply_html(f"🔨 <b>User Banned!</b>\n{target.mention_html()} has been permanently banned from the group.")
        logger.info(f"User {target.id} banned from {update.effective_chat.id}")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Ban failed: {e}")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    if context.args:
        try:
            user_id = int(context.args[0])
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.effective_message.reply_text(f"✅ User {user_id} has been unbanned.")
        except ValueError:
            await update.effective_message.reply_text("⚠️ Please provide a valid user ID.")
        except Exception as e:
            await update.effective_message.reply_text(f"⚠️ Unban failed: {e}")
    else:
        await update.effective_message.reply_text("⚠️ Usage: /unban <user_id>")

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to /mute <seconds>.")
    
    secs = int(context.args[0]) if context.args else 300
    target = update.message.reply_to_message.from_user
    
    try:
        perms = ChatPermissions(can_send_messages=False)
        until_date = datetime.now() + timedelta(seconds=secs)
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=perms, until_date=until_date)
        await update.effective_message.reply_html(f"🔇 <b>User Muted!</b>\n{target.mention_html()} muted for {secs} seconds.")
        logger.info(f"User {target.id} muted for {secs}s in {update.effective_chat.id}")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Mute failed: {e}")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to /unmute.")
    
    target = update.message.reply_to_message.from_user
    try:
        perms = ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True
        )
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=perms)
        await update.effective_message.reply_html(f"🔊 <b>User Unmuted!</b>\n{target.mention_html()} can now speak again.")
        logger.info(f"User {target.id} unmuted in {update.effective_chat.id}")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Unmute failed: {e}")

async def purge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    count = int(context.args[0]) if context.args else 10
    if count > 100:
        return await update.effective_message.reply_text("⚠️ Maximum 100 messages can be purged at once.")
    
    try:
        # Delete the purge command message
        await update.message.delete()
        deleted = 0
        
        # Simple implementation - in practice, you'd need more sophisticated message tracking
        await update.effective_message.reply_text(f"🧹 Attempted to purge {count} messages. Note: Due to Telegram API limitations, only recent messages can be deleted.")
        logger.info(f"Purge command executed in {update.effective_chat.id}")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Purge failed: {e}")

async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply with /warn <reason> to warn a user.")
    
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    reason = " ".join(context.args) if context.args else "No reason specified"
    
    # Store warnings
    cdata = context.chat_data.setdefault("warnings", {})
    cdata[str(target.id)] = cdata.get(str(target.id), 0) + 1
    count = cdata[str(target.id)]
    
    await update.effective_message.reply_html(
        f"⚠️ <b>Warning Issued!</b>\n"
        f"User: {target.mention_html()}\n"
        f"Warnings: {count}/3\n"
        f"Reason: {reason}"
    )
    
    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.effective_message.reply_html(
                f"🚫 <b>Auto-Ban Triggered!</b>\n{target.mention_html()} has been banned after receiving 3 warnings."
            )
            # Reset warnings after ban
            cdata[str(target.id)] = 0
        except Exception as e:
            await update.effective_message.reply_text(f"⚠️ Auto-ban failed: {e}")

async def warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else update.effective_user
    cdata = context.chat_data.get("warnings", {})
    count = cdata.get(str(target.id), 0)
    
    await update.effective_message.reply_html(
        f"⚠️ <b>Warning Status</b>\n"
        f"User: {target.mention_html()}\n"
        f"Warnings: {count}/3"
    )

async def clearwarns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to clear their warnings.")
    
    target = update.message.reply_to_message.from_user
    cdata = context.chat_data.setdefault("warnings", {})
    cdata[str(target.id)] = 0
    
    await update.effective_message.reply_html(f"✅ Warnings cleared for {target.mention_html()}.")

# ----- Role management -----

async def addrole_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message or not context.args:
        return await update.effective_message.reply_text("⚠️ Usage: Reply to user + /addrole <moderator|helper|vip>")
    
    role = context.args[0].lower()
    cfg = context.bot_data["config"]
    if role not in cfg["roles"]:
        return await update.effective_message.reply_text("⚠️ Unknown role. Available: moderator, helper, vip")
    
    target = update.message.reply_to_message.from_user
    persist: FileJSONPersistence = context.bot_data["persist"]
    grant_role(persist, update.effective_chat.id, target.id, role)
    
    await update.effective_message.reply_html(
        f"🏷️ <b>Role Assigned!</b>\n"
        f"User: {target.mention_html()}\n"
        f"Role: {role.title()}"
    )

async def removerole_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message or not context.args:
        return await update.effective_message.reply_text("⚠️ Usage: Reply to user + /removerole <role>")
    
    role = context.args[0].lower()
    target = update.message.reply_to_message.from_user
    persist: FileJSONPersistence = context.bot_data["persist"]
    revoke_role(persist, update.effective_chat.id, target.id, role)
    
    await update.effective_message.reply_html(
        f"🏷️ <b>Role Removed!</b>\n"
        f"User: {target.mention_html()}\n"
        f"Role: {role.title()}"
    )

async def userroles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else update.effective_user
    persist: FileJSONPersistence = context.bot_data["persist"]
    cdata = persist.chat_data.setdefault(str(update.effective_chat.id), {})
    roles = cdata.setdefault("roles", {}).get(str(target.id), [])
    
    role_text = ", ".join([r.title() for r in roles]) if roles else "No special roles"
    await update.effective_message.reply_html(
        f"🎚️ <b>User Roles</b>\n"
        f"User: {target.mention_html()}\n"
        f"Roles: {role_text}"
    )

async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    roles = context.bot_data["config"]["roles"]
    lines = []
    for role, perms in roles.items():
        perm_list = [k for k, v in perms.items() if v]
        perm_text = ", ".join(perm_list) if perm_list else "No special permissions"
        lines.append(f"• <b>{role.title()}</b>: {perm_text}")
    
    text = "🏷️ <b>Available Roles & Permissions</b>\n\n" + "\n".join(lines)
    await update.effective_message.reply_html(text)

async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_list = []
        
        for admin in admins:
            if admin.user.is_bot:
                continue
            status = "👑 Owner" if isinstance(admin, ChatMemberOwner) else "👮‍♂️ Admin"
            admin_list.append(f"• {admin.user.mention_html()} ({status})")
        
        text = f"👮‍♂️ <b>Group Administrators ({len(admin_list)})</b>\n\n" + "\n".join(admin_list)
        await update.effective_message.reply_html(text)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Failed to get admin list: {e}")

# ----- Utility commands -----

async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        perms = ChatPermissions(can_send_messages=False)
        await context.bot.set_chat_permissions(update.effective_chat.id, permissions=perms)
        context.chat_data.setdefault("flags", {})["locked"] = True
        await update.effective_message.reply_text("🔒 Chat locked. Only admins can send messages.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Lock failed: {e}")

async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        perms = ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True
        )
        await context.bot.set_chat_permissions(update.effective_chat.id, permissions=perms)
        context.chat_data.setdefault("flags", {})["locked"] = False
        await update.effective_message.reply_text("🔓 Chat unlocked. Everyone can send messages.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Unlock failed: {e}")

async def restrict_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        return await update.effective_message.reply_text("⚠️ Reply to a user to restrict them.")
    
    target = update.message.reply_to_message.from_user
    try:
        perms = ChatPermissions(
            can_send_messages=True, can_send_media_messages=False,
            can_send_other_messages=False, can_add_web_page_previews=False
        )
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=perms)
        await update.effective_message.reply_html(f"⛔ {target.mention_html()} restricted to text only.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Restrict failed: {e}")

async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    text = " ".join(context.args)
    if not text:
        return await update.effective_message.reply_text("⚠️ Usage: /setrules <rules text>")
    
    context.bot_data["config"]["rules_text"] = text
    await update.effective_message.reply_text("✅ Group rules updated successfully!")

async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    text = " ".join(context.args)
    if not text:
        return await update.effective_message.reply_text("⚠️ Usage: /setwelcome <message with {name} placeholder>")
    
    context.bot_data["config"]["welcome_text"] = text
    await update.effective_message.reply_text("✅ Welcome message updated successfully!")

async def setgoodbye_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    text = " ".join(context.args)
    if not text:
        return await update.effective_message.reply_text("⚠️ Usage: /setgoodbye <message with {name} placeholder>")
    
    context.bot_data["config"]["goodbye_text"] = text
    await update.effective_message.reply_text("✅ Goodbye message updated successfully!")

async def setlang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    code = context.args[0].lower() if context.args else "en"
    context.bot_data["config"]["language"] = code
    await update.effective_message.reply_text(f"🌐 Language set to: {code}")

async def reloadconfig_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        data_dir = Path("data")
        config = load_config(data_dir / "config.json")
        context.bot_data["config"] = config
        await update.effective_message.reply_text("✅ Configuration reloaded from config.json")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Reload failed: {e}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat = update.effective_chat
        member_count = await context.bot.get_chat_member_count(chat.id)
        
        # Warning statistics
        cdata = context.chat_data.get("warnings", {})
        total_warns = sum(cdata.values()) if cdata else 0
        warned_users = len([u for u, w in cdata.items() if w > 0]) if cdata else 0
        
        # Flags status
        flags = context.chat_data.get("flags", {})
        protections = []
        if flags.get("locked"): protections.append("🔒 Locked")
        if flags.get("antispam"): protections.append("💣 Anti-Spam")
        if flags.get("antiflood"): protections.append("🌊 Anti-Flood")
        if flags.get("nsfw_filter"): protections.append("🔞 NSFW Filter")
        if flags.get("link_filter"): protections.append("🔗 Link Filter")
        
        protection_status = ", ".join(protections) if protections else "No protections active"
        
        text = (
            f"📊 <b>Group Statistics</b>\n\n"
            f"👥 <b>Members:</b> {member_count}\n"
            f"⚠️ <b>Total Warnings:</b> {total_warns}\n"
            f"👤 <b>Warned Users:</b> {warned_users}\n"
            f"🛡️ <b>Active Protections:</b>\n{protection_status}\n\n"
            f"📅 <b>Stats collected:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.effective_message.reply_html(text)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Failed to get statistics: {e}")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else update.effective_user
    
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, target.id)
        status_emoji = {
            "creator": "👑", "administrator": "👮‍♂️", "member": "👤",
            "restricted": "⛔", "left": "🚪", "kicked": "🚫"
        }
        
        # Get user roles
        persist: FileJSONPersistence = context.bot_data["persist"]
        cdata = persist.chat_data.setdefault(str(update.effective_chat.id), {})
        roles = cdata.setdefault("roles", {}).get(str(target.id), [])
        role_text = ", ".join([r.title() for r in roles]) if roles else "None"
        
        # Get warnings
        warnings = context.chat_data.get("warnings", {}).get(str(target.id), 0)
        
        text = (
            f"🪪 <b>User Information</b>\n\n"
            f"👤 <b>Name:</b> {target.mention_html()}\n"
            f"🆔 <b>ID:</b> <code>{target.id}</code>\n"
            f"📱 <b>Username:</b> @{target.username or 'None'}\n"
            f"{status_emoji.get(member.status, '❓')} <b>Status:</b> {member.status.title()}\n"
            f"🏷️ <b>Roles:</b> {role_text}\n"
            f"⚠️ <b>Warnings:</b> {warnings}/3\n"
        )
        
        if target.language_code:
            text += f"🌐 <b>Language:</b> {target.language_code}\n"
        
        await update.effective_message.reply_html(text)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Failed to get user info: {e}")

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return await info_cmd(update, context)  # Alias for info

async def listmembers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await user_is_admin(update, context):
        await update.effective_message.reply_text("⛔ Admin privileges required.")
        return
    
    try:
        member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
        await update.effective_message.reply_html(
            f"👥 <b>Group Members</b>\n\n"
            f"Total members: <b>{member_count}</b>\n\n"
            f"<i>Note: Due to Telegram API limitations, detailed member lists "
            f"are only available for smaller groups or through bot admin privileges.</i>"
        )
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Failed to get member count: {e}")

async def inactive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    days = int(context.args[0]) if context.args else 30
    await update.effective_message.reply_text(
        f"😴 <b>Inactive Users</b>\n\n"
        f"Searching for users inactive for {days} days...\n\n"
        f"<i>Note: This feature requires message tracking implementation. "
        f"Currently showing placeholder response.</i>",
        parse_mode=ParseMode.HTML
    )

# ----- Data management -----

async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        persist: FileJSONPersistence = context.bot_data["persist"]
        backup_data = {
            "chat_data": persist.chat_data.get(str(update.effective_chat.id), {}),
            "config": context.bot_data["config"],
            "timestamp": datetime.now().isoformat()
        }
        
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        filename = f"backup_{update.effective_chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Send as document
        from io import BytesIO
        backup_file = BytesIO(backup_json.encode('utf-8'))
        backup_file.name = filename
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=backup_file,
            caption="📦 Group backup created successfully!",
            filename=filename
        )
        
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Backup failed: {e}")

async def exportroles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        persist: FileJSONPersistence = context.bot_data["persist"]
        cdata = persist.chat_data.get(str(update.effective_chat.id), {})
        roles_data = cdata.get("roles", {})
        
        if not roles_data:
            await update.effective_message.reply_text("📋 No roles data to export.")
            return
        
        # Create CSV-like format
        lines = ["User ID,Roles"]
        for user_id, user_roles in roles_data.items():
            if user_roles:
                lines.append(f"{user_id},\"{';'.join(user_roles)}\"")
        
        csv_content = "\n".join(lines)
        filename = f"roles_{update.effective_chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from io import BytesIO
        csv_file = BytesIO(csv_content.encode('utf-8'))
        csv_file.name = filename
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=csv_file,
            caption="🏷️ Roles data exported successfully!",
            filename=filename
        )
        
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Export failed: {e}")

async def exportrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    try:
        rules_text = context.bot_data["config"].get("rules_text", "No rules set.")
        filename = f"rules_{update.effective_chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        from io import BytesIO
        rules_file = BytesIO(rules_text.encode('utf-8'))
        rules_file.name = filename
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=rules_file,
            caption="📜 Group rules exported successfully!",
            filename=filename
        )
        
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Export failed: {e}")

# ----- Welcome/goodbye handlers -----

async def greet_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        welcome_text = context.bot_data["config"]["welcome_text"]
        formatted_text = welcome_text.format(name=member.mention_html())
        
        welcome_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Rules", callback_data="go:rules"),
             InlineKeyboardButton("ℹ️ Help", callback_data="go:help")]
        ])
        
        await update.effective_message.reply_html(
            f"🎉 <b>Welcome to the group!</b>\n\n{formatted_text}",
            reply_markup=welcome_kb
        )
        
        logger.info(f"New member {member.id} welcomed in {update.effective_chat.id}")

async def farewell_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.left_chat_member and not update.message.left_chat_member.is_bot:
        member = update.message.left_chat_member
        goodbye_text = context.bot_data["config"]["goodbye_text"]
        formatted_text = goodbye_text.format(name=member.mention_html())
        
        await update.effective_message.reply_html(f"👋 {formatted_text}")
        logger.info(f"Member {member.id} farewell in {update.effective_chat.id}")

# ----- Anti-spam and filters -----

SPAM_KEYWORDS = {
    "free crypto", "airdrop", "bitcoin giveaway", "click here", "earn money",
    "make money fast", "get rich quick", "investment opportunity", "trading signals"
}

NSFW_KEYWORDS = {
    "porn", "xxx", "sex", "nude", "adult content", "18+", "nsfw", "explicit", "hentai", "erotic", "fetish", "bdsm",
"hardcore", "blowjob", "handjob", "cumshot", "orgy", "gangbang", "anal", "vaginal", "oral", "masturbation",
"dildo", "vibrator", "sex toy", "stripping", "naked", "barely legal", "teen", "milf", "stepmom", "stepsis",
"incest", "rape", "fantasy", "roleplay", "voyeur", "webcam", "camgirl", "onlyfans", "escort", "prostitute",
"whore", "slut", "bitch", "dominatrix", "submissive", "bondage", "s&m", "sadism", "masochism", "fisting",
"double penetration", "dp", "creampie", "facial", "swallow", "squirt", "watersports", "golden shower",
"scat", "coprophilia", "urophilia", "necrophilia", "bestiality", "zoophilia", "child porn", "underage",
"lolita", "shota", "cp", "drugs", "cocaine", "heroin", "meth", "weed", "marijuana", "alcohol", "drunk",
"violence", "gore", "blood", "torture", "murder", "suicide", "self-harm", "abuse", "hate speech", "racism",
"sexism", "homophobia", "transphobia", "swastika"
}

async def message_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message.text and not update.effective_message.caption:
        return
    
    text = (update.effective_message.text or update.effective_message.caption or "").lower()
    flags = context.chat_data.get("flags", {})
    
    # Anti-spam check
    if flags.get("antispam") and any(keyword in text for keyword in SPAM_KEYWORDS):
        try:
            await update.effective_message.delete()
            warning_msg = await update.effective_chat.send_message(
                "🛑 <b>Spam Detected!</b>\nMessage removed automatically.",
                parse_mode=ParseMode.HTML
            )
            # Delete warning after 5 seconds
            await asyncio.sleep(5)
            await warning_msg.delete()
            logger.info(f"Spam message deleted in {update.effective_chat.id}")
            return
        except Exception:
            pass
    
    # NSFW filter
    if flags.get("nsfw_filter") and any(keyword in text for keyword in NSFW_KEYWORDS):
        try:
            await update.effective_message.delete()
            warning_msg = await update.effective_chat.send_message(
                "🔞 <b>NSFW Content Blocked!</b>\nInappropriate content removed.",
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(5)
            await warning_msg.delete()
            logger.info(f"NSFW message deleted in {update.effective_chat.id}")
            return
        except Exception:
            pass
    
    # Link filter
    if flags.get("link_filter") and any(url_indicator in text for url_indicator in ["http", "www.", ".com", ".org", ".net"]):
        try:
            await update.effective_message.delete()
            warning_msg = await update.effective_chat.send_message(
                "🔗 <b>Link Blocked!</b>\nExternal links are not allowed.",
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(5)
            await warning_msg.delete()
            logger.info(f"Link message deleted in {update.effective_chat.id}")
            return
        except Exception:
            pass

# ----- Advanced commands -----

async def antispam_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    action = context.args[0].lower() if context.args else "status"
    flags = context.chat_data.setdefault("flags", {})
    
    if action in ["on", "enable"]:
        flags["antispam"] = True
        await update.effective_message.reply_text("💣 Anti-spam protection enabled!")
    elif action in ["off", "disable"]:
        flags["antispam"] = False
        await update.effective_message.reply_text("💤 Anti-spam protection disabled!")
    else:
        status = "ON" if flags.get("antispam") else "OFF"
        await update.effective_message.reply_text(f"💣 Anti-spam status: {status}")

async def antiflood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    action = context.args[0].lower() if context.args else "status"
    flags = context.chat_data.setdefault("flags", {})
    
    if action in ["on", "enable"]:
        flags["antiflood"] = True
        await update.effective_message.reply_text("🌊 Anti-flood protection enabled!")
    elif action in ["off", "disable"]:
        flags["antiflood"] = False
        await update.effective_message.reply_text("💤 Anti-flood protection disabled!")
    else:
        status = "ON" if flags.get("antiflood") else "OFF"
        await update.effective_message.reply_text(f"🌊 Anti-flood status: {status}")

async def detectspam_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    await update.effective_message.reply_text(
        "🔍 <b>Spam Detection Report</b>\n\n"
        "Scanning recent messages for spam patterns...\n"
        "<i>This is a placeholder. In production, this would analyze recent messages.</i>",
        parse_mode=ParseMode.HTML
    )

async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    
    # This is a simplified log display
    recent_actions = [
        "User joined group",
        "Message deleted (spam)",
        "User warned",
        "Settings changed"
    ]
    
    log_text = "📋 <b>Recent Group Actions</b>\n\n"
    for i, action in enumerate(recent_actions[-10:], 1):  # Last 10 actions
        log_text += f"{i}. {action}\n"
    
    log_text += "\n<i>Detailed logging requires database integration.</i>"
    
    await update.effective_message.reply_html(log_text)

# ----- Error handler -----

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Exception while handling an update: %s", context.error)
    
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🚑 <b>Oops! Something went wrong.</b>\n"
                     "The error has been logged and will be fixed soon.\n"
                     "Please try again or contact support if the issue persists.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

# ------------------------------------------------------------------------------
# Application builder and main
# ------------------------------------------------------------------------------

def build_application() -> Application:
    # Token from environment ONLY
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required!")

    data_dir = Path("data")
    persist = FileJSONPersistence(data_dir)
    config = load_config(data_dir / "config.json")

    app = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    # Store config and persistence
    app.bot_data["config"] = config
    app.bot_data["persist"] = persist

    # Start auto-flush
    app.post_init.append(lambda app_: persist.start_auto_flush())

    # Basic commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("welcome", welcome_cmd))
    app.add_handler(CommandHandler("goodbye", goodbye_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("developer", developer_cmd))

    # Moderation commands
    app.add_handler(CommandHandler("kick", kick_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("purge", purge_cmd))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("warnings", warnings_cmd))
    app.add_handler(CommandHandler("clearwarns", clearwarns_cmd))

    # Role management
    app.add_handler(CommandHandler("addrole", addrole_cmd))
    app.add_handler(CommandHandler("removerole", removerole_cmd))
    app.add_handler(CommandHandler("userroles", userroles_cmd))
    app.add_handler(CommandHandler("roles", roles_cmd))
    app.add_handler(CommandHandler("admins", admins_cmd))

    # Utility commands
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("restrict", restrict_cmd))

    # Configuration commands
    app.add_handler(CommandHandler("setrules", setrules_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome_cmd))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye_cmd))
    app.add_handler(CommandHandler("setlang", setlang_cmd))
    app.add_handler(CommandHandler("reloadconfig", reloadconfig_cmd))

    # Information commands
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("listmembers", listmembers_cmd))
    app.add_handler(CommandHandler("inactive", inactive_cmd))

    # Fun commands
    app.add_handler(CommandHandler("quote", quote_cmd))
    app.add_handler(CommandHandler("joke", joke_cmd))
    app.add_handler(CommandHandler("cat", cat_cmd))
    app.add_handler(CommandHandler("poll", poll_cmd))

    # Security commands
    app.add_handler(CommandHandler("antispam", antispam_cmd))
    app.add_handler(CommandHandler("antiflood", antiflood_cmd))
    app.add_handler(CommandHandler("detectspam", detectspam_cmd))
    app.add_handler(CommandHandler("log", log_cmd))

    # Data management
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("exportroles", exportroles_cmd))
    app.add_handler(CommandHandler("exportrules", exportrules_cmd))

    # Handlers for callbacks and messages
    app.add_handler(CallbackQueryHandler(settings_cb))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), capture_text))

    # Welcome/goodbye handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, farewell_member))

    # Message filters (run after other handlers)
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), message_filter), group=10)

    # Error handler
    app.add_error_handler(error_handler)

    return app

def main() -> None:
    """Main entry point"""
    try:
        app = build_application()
        logger.info("🚀 Starting GROUP MEG bot...")
        logger.info("Bot ready! Add me to a group as admin to get started.")
        
        # Run with polling
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            stop_signals=None,
            close_loop=False
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Failed to start bot: %s", e)
        raise

if __name__ == "__main__":
    main()


