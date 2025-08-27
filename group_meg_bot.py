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

    # Main Keyboard
    def create_main_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("📋 Rules", callback_data="show_rules"),
             InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")],
            [InlineKeyboardButton("🛡️ Moderation", callback_data="show_moderation"),
             InlineKeyboardButton("🎮 Games & Fun", callback_data="show_games")],
            [InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
             InlineKeyboardButton("🔧 Utilities", callback_data="show_utilities")],
            [InlineKeyboardButton("🏆 Reputation", callback_data="show_reputation"),
             InlineKeyboardButton("🛡️ Protection", callback_data="show_protection")],
            [InlineKeyboardButton("👨‍💻 Developer Info", callback_data="show_developer"),
             InlineKeyboardButton("❓ Help", callback_data="show_help")]
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

    # --- Main commands
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.stats["commands_used"] += 1
        welcome_text = (
            "🎉 **Welcome to GROUP MEG Bot!** 🇵🇸\n\n"
            f"👋 Hello {update.effective_user.first_name}!\n\n"
            "🏠 Main Menu - Choose an option:"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.create_main_keyboard())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = "📚 **GROUP MEG Bot Help** 🇵🇸\n\nUse buttons for all features!"
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.create_main_keyboard())

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id)
        rules = self.groups_data.get(chat_id, {}).get("rules", self.config["default_rules"])
        rules_text = "📋 **Group Rules:**\n\n" + "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(rules)])
        rules_text += "\n\n⚠️ Breaking rules may result in warnings, kicks, or bans."
        await update.message.reply_text(rules_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]))

    # --- Inline Settings Handler
    async def show_settings_inline(self, query) -> None:
        if not await self.is_admin_callback(query):
            await query.edit_message_text(
                "❌ **Access Denied**\n\nOnly admins can access settings!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
                ])
            )
            return
        chat_id = str(query.message.chat.id)
        group_data = self.groups_data.get(chat_id, {})
        settings_text = (
            f"⚙️ **Group Settings**\n\n"
            f"🔞 **Adult Filter:** {'✅ ON' if group_data.get('adult_protection', True) else '❌ OFF'}\n"
            f"🚫 **Anti-Spam:** {'✅ ON' if group_data.get('anti_spam', True) else '❌ OFF'}\n"
            f"💬 **Flood Control:** {'✅ ON' if group_data.get('flood_control', True) else '❌ OFF'}\n"
            f"🎉 **Welcome Messages:** {'✅ ON' if group_data.get('welcome_enabled', True) else '❌ OFF'}\n"
            f"🤖 **Auto-Delete Joins:** {'✅ ON' if group_data.get('auto_delete_joins', False) else '❌ OFF'}\n"
            f"🏆 **Reputation System:** {'✅ ON' if group_data.get('reputation_system', True) else '❌ OFF'}\n\n"
            f"👮 **Warning Limit:** {self.config['warn_limit']}\n"
            f"💬 **Flood Limit:** {self.config['flood_limit']} msgs/{self.config['flood_time']}s\n\n"
            f"💡 Click buttons below to configure settings"
        )
        await query.edit_message_text(settings_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.create_settings_keyboard())

    async def handle_settings_callback(self, query, data: str) -> None:
        if not await self.is_admin_callback(query):
            await query.answer("❌ Only admins can change settings!", show_alert=True)
            return
        chat_id = str(query.message.chat.id)
        if chat_id not in self.groups_data:
            self.groups_data[chat_id] = {}
        def update_and_show(name, flag, doc):
            current = self.groups_data[chat_id].get(flag, self.config.get(flag, True))
            self.groups_data[chat_id][flag] = not current
            status = "✅ ENABLED" if not current else "❌ DISABLED"
            self.save_json_file("groups.json", self.groups_data)
            text = f"{name}\n\nStatus: {status}\n\n{doc}\n⚡ **Change applied instantly!**"
            return text
        docs = {
            "setting_adult": ("🔞 **Adult Content Filter**",
                "adult_protection",
                "Blocks messages with adult keywords. Action: delete & warn."),
            "setting_spam": ("🚫 **Anti-Spam Filter**",
                "anti_spam",
                "Blocks spam links, usernames, advertising, repetition. Action: delete & warn."),
            "setting_flood": ("💬 **Flood Control**",
                "flood_control",
                f"Limits: {self.config['flood_limit']} messages/{self.config['flood_time']}s. Mutes violators."),
            "setting_welcome": ("🎉 **Welcome Messages**",
                "welcome_enabled",
                "Toggle welcome messages for new users."),
            "setting_autodelete": ("🤖 **Auto-Delete Join Messages**",
                "auto_delete_joins",
                "Deletes join/leave messages after 2/1 minutes."),
            "setting_reputation": ("🏆 **Reputation System**",
                "reputation_system",
                "Scores users for activity & rule-following."),
        }
        if data in docs:
            name, flag, doc = docs[data]
            await query.edit_message_text(
                update_and_show(name, flag, doc),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Settings", callback_data="show_settings")]
                ])
            )
        elif data == "setting_analytics":
            await query.edit_message_text(
                "📊 **Group Analytics**\n\nShows statistics via /filterstats & /stats.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Settings", callback_data="show_settings")]
                ])
            )
        elif data == "setting_advanced":
            await query.edit_message_text(
                f"⚙️ **Advanced Settings**\n\nWarning Limit: {self.config['warn_limit']}\nFlood: {self.config['flood_limit']}msgs/{self.config['flood_time']}s\n\nFor full config, use commands or contact developer.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Settings", callback_data="show_settings")]
                ])
            )

    # Button Handling:
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "main_menu":
            await query.edit_message_text("🏠 **Main Menu** - Choose an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_main_keyboard())
        elif data == "show_settings":
            await self.show_settings_inline(query)
        elif data.startswith("setting_"):
            await self.handle_settings_callback(query, data)
        # Add your other menu data cases here (games, moderation, rules, protection, etc.)

    # Error Handler:
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error('Update "%s" caused error "%s"', update, context.error)
        error_str = str(context.error).lower()
        if any(ignore in error_str for ignore in ['message not modified', 'query is too old', 'message to delete not found']):
            return
        if isinstance(update, Update) and getattr(update, "effective_message", None):
            try:
                if "permission" in error_str:
                    await update.effective_message.reply_text(
                        "⚠️ **Permission Error**\n\nThe bot needs admin permission to perform this action."
                    )
                elif "not found" in error_str:
                    await update.effective_message.reply_text(
                        "❓ **User Not Found**\n\nPlease reply to a message or use @username."
                    )
                else:
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
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("rules", bot.rules_command))
    # Add ALL your previous command handlers here

    application.add_handler(CallbackQueryHandler(bot.button_handler))
    # Add message handlers for join, leave, filter, games, etc.
    # application.add_error_handler(bot.error_handler)

    async def set_bot_commands(app):
        commands = [
            BotCommand("start", "🚀 Start the bot and see main menu"),
            BotCommand("help", "❓ Get help and command list"),
            BotCommand("rules", "📋 Show group rules"),
            BotCommand("stats", "📊 Show bot statistics"),
            BotCommand("ping", "🏓 Check if bot is online"),
            BotCommand("dice", "🎲 Roll a dice"),
            BotCommand("coin", "🪙 Flip a coin"),
            BotCommand("8ball", "🎯 Ask the magic 8-ball"),
            BotCommand("joke", "🎪 Get a random joke"),
            BotCommand("warn", "⚠️ Warn a user (admin only)"),
            BotCommand("kick", "🦵 Kick a user (admin only)"),
            BotCommand("ban", "🔨 Ban a user (admin only)"),
            BotCommand("clean", "🧹 Delete messages (admin only)"),
            BotCommand("groupinfo", "ℹ️ Get group information"),
            BotCommand("membercount", "👥 Get member count"),
            BotCommand("dev", "👨‍💻 Developer information"),
        ]
        await app.bot.set_my_commands(commands)
    application.post_init = set_bot_commands
    logger.info("🚀 Starting GROUP MEG Bot v2.5 Enhanced...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()