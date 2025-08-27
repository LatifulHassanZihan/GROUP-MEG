#!/usr/bin/env python3
"""
GROUP MEG Bot 🇵🇸 - Telegram Group Management Bot
Bot Username: @group_meg_bot
Developer: Latiful Hassan Zihan 🇵🇸
Nationality: Bangladeshi 🇧🇩
Username: @alwayszihan
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import random
import re
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ChatPermissions, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus
from keep_alive import keep_alive
keep_alive()

# --- Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('data/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GroupMegBot:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.config = self.load_config()
        self.groups_data = self.load_json_file("groups.json", {})
        self.users_data = self.load_json_file("users.json", {})
        self.reputation_data = self.load_json_file("reputation.json", {})
        self.user_messages = defaultdict(list)
        self.stats = {
            "commands_used": 0,
            "groups_managed": len(self.groups_data),
            "users_registered": len(self.users_data),
            "start_time": datetime.now().isoformat(),
            "messages_filtered": 0,
            "spam_blocked": 0,
            "adult_content_blocked": 0
        }
        self.adult_keywords = [
            'porn', 'sex', 'nude', 'naked', 'xxx', 'adult', 'nsfw',
            'explicit', 'erotic', 'sexual', 'sexx', 'p0rn', 'n00des'
        ]
        self.spam_patterns = [
            r'(https?://\S+)',
            r'(@\w+)',
            r'(\d{10,})',
            r'(₹|\$|€|£)\d+',
        ]

    def load_config(self) -> Dict[str, Any]:
        config_path = self.data_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "bot_name": "GROUP MEG 🇵🇸",
            "bot_username": "@group_meg_bot",
            "developer": {
                "name": "Latiful Hassan Zihan 🇵🇸",
                "nationality": "Bangladeshi 🇧🇩",
                "username": "@alwayszihan",
                "github": "https://github.com/LatifulHassanZihan",
                "contact": "Contact me for bot development services!"
            },
            "default_rules": [
                "🚫 No spam or excessive posting",
                "🤝 Be respectful to all members",
                "📵 No adult content or inappropriate material",
                "🔇 No promotion without admin permission",
                "💬 Use appropriate language",
                "📝 Follow group topic discussions",
                "⚠️ Admins have the final say"
            ],
            "role_permissions": {
                "admin": ["all"],
                "moderator": ["warn", "kick", "mute", "delete", "addrules"],
                "helper": ["warn", "info"],
                "vip": ["games", "fun"],
                "trusted": ["bypass_filters"]
            },
            "welcome_message": "🎉 Welcome to our group, {name}!\n\n📋 Please read our rules with /rules\n💡 Use /help to see available commands",
            "goodbye_message": "👋 Goodbye {name}! Thanks for being part of our community!",
            "warn_limit": 3,
            "flood_limit": 5,
            "flood_time": 60,
            "adult_protection": True,
            "anti_spam": True,
            "auto_delete_joins": False,
            "flood_control": True,
            "welcome_enabled": True,
            "reputation_system": True
        }

    def load_json_file(self, filename: str, default: Any) -> Any:
        filepath = self.data_dir / filename
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error loading {filename}, using defaults")
        return default

    def save_json_file(self, filename: str, data: Any) -> None:
        filepath = self.data_dir / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

    def get_user_roles(self, user_id: int, chat_id: int) -> List[str]:
        user_key = f"{chat_id}_{user_id}"
        return self.users_data.get(user_key, {}).get("roles", [])

    def has_permission(self, user_id: int, chat_id: int, permission: str) -> bool:
        roles = self.get_user_roles(user_id, chat_id)
        for role in roles:
            if role in self.config["role_permissions"]:
                perms = self.config["role_permissions"][role]
                if "all" in perms or permission in perms:
                    return True
        return False

    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not update.effective_chat or not update.effective_user:
            return False
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return True
        except: pass
        return self.has_permission(update.effective_user.id, update.effective_chat.id, "admin")

    async def is_admin_callback(self, query) -> bool:
        try:
            member = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return True
        except: pass
        return self.has_permission(query.from_user.id, query.message.chat.id, "admin")

    # Protection/Spam/Flood helpers:
    def is_flood(self, user_id: int, chat_id: int) -> bool:
        now = datetime.now()
        key = f"{chat_id}_{user_id}"
        cutoff = now - timedelta(seconds=self.config["flood_time"])
        self.user_messages[key] = [msg_time for msg_time in self.user_messages[key] if msg_time > cutoff]
        self.user_messages[key].append(now)
        return len(self.user_messages[key]) > self.config["flood_limit"]

    def contains_adult_content(self, text: str) -> bool:
        if not self.config.get("adult_protection", True):
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.adult_keywords)

    def is_spam_message(self, text: str) -> bool:
        if not self.config.get("anti_spam", True):
            return False
        spam_score = 0
        for pattern in self.spam_patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            spam_score += matches
        words = text.split()
        if len(words) > 5:
            unique_words = len(set(words))
            if unique_words / len(words) < 0.3: spam_score += 2
        return spam_score >= 3

    def update_reputation(self, user_id: int, chat_id: int, change: int) -> None:
        if not self.config.get("reputation_system", True):
            return
        key = f"{chat_id}_{user_id}"
        if key not in self.reputation_data:
            self.reputation_data[key] = {"score": 0, "warnings": 0, "kicks": 0}
        self.reputation_data[key]["score"] += change
        self.save_json_file("reputation.json", self.reputation_data)

    # All menu buttons including Add Me to Group
    def create_main_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("➕ Add me to Group or Channel", url=f"https://t.me/{self.config['bot_username'].replace('@','')}?startgroup=new")],
            [InlineKeyboardButton("📋 Rules", callback_data="show_rules"),
             InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")],
            [InlineKeyboardButton("🛡️ Moderation", callback_data="show_moderation"),
             InlineKeyboardButton("🎮 Games & Fun", callback_data="show_games")],
            [InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
             InlineKeyboardButton("🔧 Utilities", callback_data="show_utilities")],
            [InlineKeyboardButton("🏆 Reputation", callback_data="show_reputation"),
             InlineKeyboardButton("🛡️ Protection", callback_data="show_protection")],
            [InlineKeyboardButton("👨‍💻 Developer Info", callback_data="show_developer"),
             InlineKeyboardButton("❓ Help & Commands", callback_data="show_help")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_settings_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🔞 Adult Filter", callback_data="setting_adult"),
             InlineKeyboardButton("🚫 Anti-Spam", callback_data="setting_spam")],
            [InlineKeyboardButton("💬 Flood Control", callback_data="setting_flood"),
             InlineKeyboardButton("🎉 Welcome Settings", callback_data="setting_welcome")],
            [InlineKeyboardButton("🤖 Auto-Delete", callback_data="setting_autodelete"),
             InlineKeyboardButton("🏆 Reputation", callback_data="setting_reputation")],
            [InlineKeyboardButton("📊 Group Analytics", callback_data="setting_analytics"),
             InlineKeyboardButton("⚙️ Advanced", callback_data="setting_advanced")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # --- Main commands (all from your command list)
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.stats["commands_used"] += 1
        welcome_text = (
            "🎉 **Welcome to GROUP MEG Bot!** 🇵🇸\n\n"
            f"👋 Hello {update.effective_user.first_name}!\n\n"
            "🏠 Main Menu - Choose an option:"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.create_main_keyboard())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = "**📚 GROUP MEG Bot Command List**\n\n"
        help_text += (
            "Use /start to see the main menu.\n\n"
            "• /help — Show this help list\n"
            "• /about — Bot & developer info\n"
            "• /rules — Show group rules\n"
            "• /settings — Settings panel (admin only)\n"
            "• /kick [reply] — Kick user\n"
            "• /ban [reply] — Ban user\n"
            "• /mute <seconds> [reply] — Mute user\n"
            "• /unban <id> — Unban user\n"
            "• /unmute [reply] — Unmute user\n"
            "• /purge <count> — Purge recent messages\n"
            "• /warn [reply+reason] — Warn user\n"
            "• /warnings [reply] — Warning count\n"
            "• /addrole <role> [reply] — Add role\n"
            "• /removerole <role> [reply] — Remove role\n"
            "• /userroles [reply] — Show user roles\n"
            "• /roles — List all roles\n"
            "• /admins — List admins\n"
            "• /setwelcome <text> — Set welcome\n"
            "• /setgoodbye <text> — Set goodbye\n"
            "• /welcome — Show welcome text\n"
            "• /goodbye — Show goodbye text\n"
            "• /setrules <text> — Set rules message\n"
            "• /langue <code> — Set reply language\n"
            "• /reloadconfig — Reload config\n"
            "• /info [reply] — User info\n"
            "• /stats — Group stats\n"
            "• /panel — Show control panel\n"
            "And many more! Use inline menu for all options."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        dev = self.config["developer"]
        about_text = (
            f"👨‍💻 **About GROUP MEG Bot** 🇵🇸\n\n"
            f"🤖 **Bot Name:** {self.config['bot_name']}\n"
            f"🆔 **Username:** {self.config['bot_username']}\n"
            f"🔧 **Version:** 2.5.0 Enhanced\n"
            f"👨‍💻 **Developer:** {dev['name']}\n"
            f"🌍 **Nationality:** {dev['nationality']}\n"
            f"📱 **Contact:** {dev['username']}\n"
            f"🔗 **GitHub:** {dev.get('github', 'Not available')}\n\n"
            "💡 **Purpose:** Making Telegram groups safer and more engaging!"
        )
        await update.message.reply_text(about_text, parse_mode=ParseMode.MARKDOWN)

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Only admins can access settings!")
            return
        await update.message.reply_text(
            "⚙️ **Group Settings Panel**\n\nUse the interactive menu below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_settings_keyboard()
        )

    # You would implement similar async command handlers for ALL other commands from the images: 
    # /kick, /ban, /unban, /mute, /unmute, /purge, /warn, /warnings, /addrole, /removerole, /userroles, /roles, /admins,
    # /setwelcome, /setgoodbye, /welcome, /goodbye, /setrules, /langue, /reloadconfig, /info, /stats, /panel, /lock, /unlock, /restrict, /clearwarns,
    # /detectspam, /antispm, /antiflood, /log, /promote, /demote, /listmembers, /inactive, /profile, /backup, /restore, /exportroles, /exportrules,
    # /topwarned, /topactive, /activity, /delmedia, /pin, /unpin, /settimezone, /autodelete, /captcha, /nightmode, /notify, /quote, /poll, /joke, /cat,
    # /contactadmin, /adminhelp, /report, /menu, /setprefix, /setrolecolor ... etc.
    # [Paste your custom logic for each command as you had them before.]

    # Inline menu/keyboard handlers
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "main_menu":
            await query.edit_message_text(
                "🏠 **Main Menu** - Choose an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_main_keyboard()
            )
        elif data == "show_settings":
            await self.settings_command(query, context)
        elif data == "show_help":
            await query.edit_message_text(
                "**📚 GROUP MEG Bot Command List**\n\nUse /help to see full command list.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]])
            )
        # Add all other handlers for inline menu options...

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error('Update "%s" caused error "%s"', update, context.error)
        error_str = str(context.error).lower()
        if any(ignore in error_str for ignore in ['message not modified', 'query is too old', 'message to delete not found']):
            return
        if isinstance(update, Update) and getattr(update, "effective_message", None):
            try:
                await update.effective_message.reply_text(
                    "⚡ **Command processed. If you experience issues, please try again.**"
                )
            except Exception:
                pass

def main():
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not found!")
        return
    bot = GroupMegBot()
    application = Application.builder().token(bot_token).build()
    # Register all command handlers (for all commands on your images)
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("about", bot.about_command))
    application.add_handler(CommandHandler("rules", bot.rules_command))
    application.add_handler(CommandHandler("settings", bot.settings_command))
    # Register all your other commands here, e.g.:
    # application.add_handler(CommandHandler("kick", bot.kick_command))
    # application.add_handler(CommandHandler("ban", bot.ban_command))
    # application.add_handler(CommandHandler("mute", bot.mute_command))
    # ... repeat for all extra commands shown on your images ...

    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_error_handler(bot.error_handler)

    async def set_bot_commands(app):
    commands = [
        # 🚀 Basic Commands
        BotCommand("start", "🚀 Start the bot & Add to Group button"),
        BotCommand("help", "❓ List all available commands"),
        BotCommand("about", "👤 Show bot, developer, & project info"),
        BotCommand("rules", "📋 Displays group rules"),
        BotCommand("settings", "⚙️ Opens interactive config panel"),
        
        # 👮‍♂️ Admin & Moderation
        BotCommand("kick", "🦵 Kick replied user (admin only)"),
        BotCommand("ban", "🔨 Ban replied user (admin only)"),
        BotCommand("unban", "🔓 Unban user by ID (admin only)"),
        BotCommand("mute", "🔇 Mute replied user (admin only)"),
        BotCommand("unmute", "🔊 Unmute replied user (admin only)"),
        BotCommand("purge", "🗑️ Purge recent messages (admin only)"),
        
        # ⚠️ Warning & Report
        BotCommand("warn", "⚠️ Warn a user (admin only)"),
        BotCommand("warnings", "📒 Show user warnings"),
        
        # 🏷 Role Commands
        BotCommand("addrole", "🎭 Assign role to user [reply]"),
        BotCommand("removerole", "❌ Remove role from user [reply]"),
        BotCommand("userroles", "🧑‍💼 Show user roles [reply]"),
        BotCommand("roles", "🧩 List all roles"),
        BotCommand("admins", "👮 List all admins"),
        
        # 👋 Welcome & Goodbye
        BotCommand("setwelcome", "🎉 Set custom welcome message"),
        BotCommand("setgoodbye", "👋 Set custom goodbye message"),
        BotCommand("welcome", "👋 Show welcome message"),
        BotCommand("goodbye", "👋 Show goodbye message"),
        
        # 🛠️ Configuration
        BotCommand("setrules", "📝 Set group rules message"),
        BotCommand("langue", "🌏 Set bot language"),
        BotCommand("reloadconfig", "🔄 Reload config from file"),
        
        # ℹ️ Info
        BotCommand("info", "🔍 Show user info [reply]"),
        BotCommand("stats", "📊 Show group stats"),
        
        # 🟩 Panel/Menu
        BotCommand("panel", "🟩 Show main control panel"),
        BotCommand("menu", "🎛 Show interactive main menu"),
        
        # ⚡ Moderation & Security
        BotCommand("lock", "🔒 Lock group for members"),
        BotCommand("unlock", "🔓 Unlock group"),
        BotCommand("restrict", "🚷 Restrict user temporarily"),
        BotCommand("clearwarns", "🧹 Clear warnings [reply]"),
        BotCommand("detectspam", "🤖 Scan & delete spam"),
        BotCommand("antispam", "💣 Enable/disable anti-spam"),
        BotCommand("antiflood", "🌊 Enable/disable flood control"),
        BotCommand("log", "📜 Show recent actions"),
        
        # 👥 Member Management
        BotCommand("promote", "⬆️ Promote member to admin"),
        BotCommand("demote", "⬇️ Demote admin to user"),
        BotCommand("listmembers", "👥 List all members"),
        BotCommand("inactive", "😴 List inactive users"),
        BotCommand("profile", "🪪 Show user profile [reply]"),
        
        # ✏️ Content & Rule Handling
        BotCommand("setlang", "🌎 Set bot language"),
        BotCommand("antinsfw", "🚫 Enable/disable NSFW filter"),
        BotCommand("antiilink", "🔗 Enable/disable link blocking"),
        
        # 💾 Storage & Export
        BotCommand("backup", "📦 Export group+user data"),
        BotCommand("restore", "📥 Restore data from backup"),
        BotCommand("exportroles", "🏷 Export roles as CSV"),
        BotCommand("exportrules", "📄 Export rules as text"),
        
        # 📊 Statistics & Analytics
        BotCommand("userstats", "📑 User stats [reply]"),
        BotCommand("topwarned", "⚠️ Show top warned users"),
        BotCommand("topactive", "🏆 List top active members"),
        BotCommand("activity", "📉 Group activity graph"),
        
        # 📁 Media & Files
        BotCommand("delmedia", "🗑️ Delete recent group media"),
        BotCommand("pin", "📌 Pin a message"),
        BotCommand("unpin", "📍 Unpin current message"),
        
        # 🔧 Utilities & Automation
        BotCommand("settimezone", "🌐 Set group timezone"),
        BotCommand("autodelete", "⏰ Remove old messages"),
        BotCommand("captcha", "🤖 Enable/disable captcha"),
        BotCommand("nightmode", "🌙 Enable/disable night mode"),
        BotCommand("notify", "🔔 Notify all members"),
        
        # 😍 Fun & Engagement
        BotCommand("quote", "💬 Random motivational quote"),
        BotCommand("poll", "📊 Create group poll"),
        BotCommand("joke", "😂 Tell a joke!"),
        BotCommand("cat", "🐱 Random cat picture"),
        
        # 🆘 Admin Help & Contact
        BotCommand("contactadmin", "📞 Call admins for help"),
        BotCommand("adminhelp", "🆘 List all admin commands"),
        BotCommand("report", "🚨 Report user to admin"),
        
        # 🧩 Customization & Advanced
        BotCommand("setprefix", "🏷 Set group command prefix"),
        BotCommand("setrolecolor", "🎨 Set color for roles"),
    ]
    await app.bot.set_my_commands(commands)

application.post_init = set_bot_commands
logger.info("🚀 Starting GROUP MEG Bot v2.5 Enhanced with all options...")

        await app.bot.set_my_commands(commands)
    application.post_init = set_bot_commands
    logger.info("🚀 Starting GROUP MEG Bot v2.5 Enhanced...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
