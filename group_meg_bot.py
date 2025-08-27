#!/usr/bin/env python3
"""
GROUP MEG Bot 🇵🇸 - Telegram Group Management Bot
Bot Username: @group_meg_bot
Developer: Latiful Hassan Zihan 🇵🇸
Nationality: Bangladeshi 🇧🇩
Username: @alwayszihan

A comprehensive Telegram group management bot built with python-telegram-bot v20+
Features: User management, roles, moderation, games, utilities and more!
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import random
import re

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ChatMember, ChatPermissions, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, Forbidden, BadRequest
from keep_alive import keep_alive
keep_alive()

# Configure logging
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
        """Initialize the GROUP MEG Bot 🇵🇸"""
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize data storage
        self.groups_data = self.load_json_file("groups.json", {})
        self.users_data = self.load_json_file("users.json", {})
        
        # Bot statistics
        self.stats = {
            "commands_used": 0,
            "groups_managed": len(self.groups_data),
            "users_registered": len(self.users_data),
            "start_time": datetime.now().isoformat()
        }

    def load_config(self) -> Dict[str, Any]:
        """Load bot configuration from config.json"""
        config_path = self.data_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Get default bot configuration"""
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
                "moderator": ["warn", "kick", "mute", "delete"],
                "helper": ["warn", "info"],
                "vip": ["games", "fun"]
            },
            "welcome_message": "🎉 Welcome to our group, {name}!\n\n📋 Please read our rules with /rules\n💡 Use /help to see available commands",
            "goodbye_message": "👋 Goodbye {name}! Thanks for being part of our community!",
            "warn_limit": 3
        }

    def load_json_file(self, filename: str, default: Any) -> Any:
        """Load JSON file with default fallback"""
        filepath = self.data_dir / filename
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error loading {filename}, using defaults")
        return default

    def save_json_file(self, filename: str, data: Any) -> None:
        """Save data to JSON file"""
        filepath = self.data_dir / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

    def get_user_roles(self, user_id: int, chat_id: int) -> List[str]:
        """Get user roles for a specific chat"""
        user_key = f"{chat_id}_{user_id}"
        return self.users_data.get(user_key, {}).get("roles", [])

    def has_permission(self, user_id: int, chat_id: int, permission: str) -> bool:
        """Check if user has specific permission"""
        roles = self.get_user_roles(user_id, chat_id)
        for role in roles:
            if role in self.config["role_permissions"]:
                perms = self.config["role_permissions"][role]
                if "all" in perms or permission in perms:
                    return True
        return False

    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is admin or has admin role"""
        if not update.effective_chat or not update.effective_user:
            return False
        
        try:
            member = await context.bot.get_chat_member(
                update.effective_chat.id, 
                update.effective_user.id
            )
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return True
        except:
            pass
        
        return self.has_permission(update.effective_user.id, update.effective_chat.id, "admin")

    def create_main_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Rules", callback_data="show_rules"),
                InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")
            ],
            [
                InlineKeyboardButton("🛡️ Moderation", callback_data="show_moderation"),
                InlineKeyboardButton("🎮 Games & Fun", callback_data="show_games")
            ],
            [
                InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
                InlineKeyboardButton("🔧 Utilities", callback_data="show_utilities")
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer Info", callback_data="show_developer"),
                InlineKeyboardButton("❓ Help", callback_data="show_help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_moderation_keyboard(self) -> InlineKeyboardMarkup:
        """Create moderation menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("⚠️ Warn User", callback_data="cmd_warn"),
                InlineKeyboardButton("🦵 Kick User", callback_data="cmd_kick")
            ],
            [
                InlineKeyboardButton("🔨 Ban User", callback_data="cmd_ban"),
                InlineKeyboardButton("🔇 Mute User", callback_data="cmd_mute")
            ],
            [
                InlineKeyboardButton("👑 Add Role", callback_data="cmd_addrole"),
                InlineKeyboardButton("👤 User Roles", callback_data="cmd_userroles")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_games_keyboard(self) -> InlineKeyboardMarkup:
        """Create games menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🎲 Roll Dice", callback_data="game_dice"),
                InlineKeyboardButton("🪙 Flip Coin", callback_data="game_coin")
            ],
            [
                InlineKeyboardButton("🔢 Number Game", callback_data="game_number"),
                InlineKeyboardButton("❓ Quiz", callback_data="game_quiz")
            ],
            [
                InlineKeyboardButton("🎯 8Ball", callback_data="game_8ball"),
                InlineKeyboardButton("🎪 Random Joke", callback_data="game_joke")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_utilities_keyboard(self) -> InlineKeyboardMarkup:
        """Create utilities menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("ℹ️ Group Info", callback_data="util_groupinfo"),
                InlineKeyboardButton("👥 Member Count", callback_data="util_membercount")
            ],
            [
                InlineKeyboardButton("🔗 Invite Link", callback_data="util_invitelink"),
                InlineKeyboardButton("📊 User Stats", callback_data="util_userstats")
            ],
            [
                InlineKeyboardButton("🧹 Clean Messages", callback_data="util_clean"),
                InlineKeyboardButton("📝 Export Data", callback_data="util_export")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        self.stats["commands_used"] += 1
        
        welcome_text = f"""
🎉 **Welcome to GROUP MEG Bot!** 🇵🇸

👋 Hello {update.effective_user.first_name}!

I'm a powerful group management bot with tons of features:

🛡️ **Moderation Tools**
• Warn, kick, ban, mute users
• Role management system
• Anti-spam protection

🎮 **Games & Fun**
• Mini-games and entertainment
• Interactive commands
• Group activities

📊 **Statistics & Analytics**
• Group insights
• User activity tracking
• Bot performance metrics

⚙️ **Utilities**
• Group management tools
• Member utilities
• Data export features

👨‍💻 **Developer:** {self.config['developer']['name']}
🌍 **Nationality:** {self.config['developer']['nationality']}
📱 **Contact:** {self.config['developer']['username']}

Use the buttons below to explore all features! 👇
        """
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_main_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = f"""
📚 **GROUP MEG Bot Help** 🇵🇸

**🛡️ Moderation Commands:**
• `/warn @user` - Warn a user
• `/kick @user` - Kick a user
• `/ban @user` - Ban a user
• `/mute @user` - Mute a user
• `/addrole @user role` - Add role to user
• `/removerole @user role` - Remove role from user
• `/userroles @user` - Show user roles

**🎮 Fun Commands:**
• `/dice` - Roll a dice
• `/coin` - Flip a coin
• `/8ball question` - Ask the magic 8-ball
• `/joke` - Get a random joke
• `/quiz` - Start a quiz game

**📊 Info Commands:**
• `/rules` - Show group rules
• `/settings` - Group settings
• `/stats` - Bot statistics
• `/groupinfo` - Group information
• `/membercount` - Member count

**🔧 Utility Commands:**
• `/clean number` - Delete messages
• `/invitelink` - Get invite link
• `/ping` - Check bot status
• `/uptime` - Bot uptime

**👨‍💻 Developer Commands:**
• `/dev` - Developer information
• `/version` - Bot version
• `/support` - Get support

Use the inline keyboard for easy access to all features! 🎯
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_main_keyboard()
        )

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /rules command"""
        chat_id = str(update.effective_chat.id)
        rules = self.groups_data.get(chat_id, {}).get("rules", self.config["default_rules"])
        
        rules_text = "📋 **Group Rules:**\n\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule}\n"
        
        rules_text += f"\n⚠️ **Warning:** Breaking rules may result in warnings, kicks, or bans.\n"
        rules_text += f"📞 Contact admins if you have questions about the rules."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await update.message.reply_text(
            rules_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /warn command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to warn users!")
            return

        if not context.args and not update.message.reply_to_message:
            await update.message.reply_text("❓ Usage: `/warn @username reason` or reply to a message")
            return

        target_user = None
        reason = "No reason provided"

        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            reason = " ".join(context.args) if context.args else reason
        elif context.args:
            username = context.args[0].replace('@', '')
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else reason
            # Note: In a real bot, you'd need to resolve username to user_id

        if not target_user:
            await update.message.reply_text("❌ Could not find the user to warn!")
            return

        # Record warning
        user_key = f"{update.effective_chat.id}_{target_user.id}"
        if user_key not in self.users_data:
            self.users_data[user_key] = {"warnings": 0, "roles": []}
        
        self.users_data[user_key]["warnings"] += 1
        warnings = self.users_data[user_key]["warnings"]
        
        self.save_json_file("users.json", self.users_data)

        warn_text = f"⚠️ **User Warned!**\n\n"
        warn_text += f"👤 **User:** {target_user.first_name}\n"
        warn_text += f"📝 **Reason:** {reason}\n"
        warn_text += f"📊 **Warnings:** {warnings}/{self.config['warn_limit']}\n"
        
        if warnings >= self.config["warn_limit"]:
            warn_text += f"\n🔨 **Action:** User will be kicked for exceeding warning limit!"
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
                await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
            except Exception as e:
                logger.error(f"Error kicking user: {e}")

        await update.message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)

    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /kick command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to kick users!")
            return

        if not update.message.reply_to_message:
            await update.message.reply_text("❓ Reply to a message to kick the user!")
            return

        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"

        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
            
            kick_text = f"🦵 **User Kicked!**\n\n"
            kick_text += f"👤 **User:** {target_user.first_name}\n"
            kick_text += f"📝 **Reason:** {reason}\n"
            kick_text += f"👮 **By:** {update.effective_user.first_name}"
            
            await update.message.reply_text(kick_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to kick user: {str(e)}")

    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ban command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to ban users!")
            return

        if not update.message.reply_to_message:
            await update.message.reply_text("❓ Reply to a message to ban the user!")
            return

        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"

        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            
            ban_text = f"🔨 **User Banned!**\n\n"
            ban_text += f"👤 **User:** {target_user.first_name}\n"
            ban_text += f"📝 **Reason:** {reason}\n"
            ban_text += f"👮 **By:** {update.effective_user.first_name}"
            
            await update.message.reply_text(ban_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")

    async def dice_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle dice game"""
        dice_result = random.randint(1, 6)
        dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][dice_result - 1]
        
        result_text = f"🎲 **Dice Roll Result!**\n\n"
        result_text += f"{dice_emoji} You rolled: **{dice_result}**\n\n"
        
        if dice_result == 6:
            result_text += "🎉 Lucky six! You're on fire! 🔥"
        elif dice_result == 1:
            result_text += "😅 Oops! Better luck next time!"
        else:
            result_text += "👍 Nice roll!"
        
        keyboard = [
            [InlineKeyboardButton("🎲 Roll Again", callback_data="game_dice")],
            [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
        ]
        
        await update.message.reply_text(
            result_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def coin_flip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle coin flip game"""
        result = random.choice(["heads", "tails"])
        emoji = "👑" if result == "heads" else "⚪"
        
        result_text = f"🪙 **Coin Flip Result!**\n\n"
        result_text += f"{emoji} It's **{result.upper()}**!\n\n"
        
        if result == "heads":
            result_text += "👑 Heads wins! Royal choice!"
        else:
            result_text += "⚪ Tails it is! Classic outcome!"
        
        keyboard = [
            [InlineKeyboardButton("🪙 Flip Again", callback_data="game_coin")],
            [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
        ]
        
        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def magic_8ball(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle magic 8-ball game"""
        responses = [
            "🔮 It is certain",
            "🔮 Without a doubt",
            "🔮 Yes definitely",
            "🔮 You may rely on it",
            "🔮 As I see it, yes",
            "🔮 Most likely",
            "🔮 Reply hazy, try again",
            "🔮 Ask again later",
            "🔮 Better not tell you now",
            "🔮 Cannot predict now",
            "🔮 Don't count on it",
            "🔮 My reply is no",
            "🔮 Very doubtful"
        ]
        
        question = " ".join(context.args) if context.args else "Will I have a good day?"
        answer = random.choice(responses)
        
        result_text = f"🎯 **Magic 8-Ball**\n\n"
        result_text += f"❓ **Question:** {question}\n"
        result_text += f"💫 **Answer:** {answer}"
        
        keyboard = [
            [InlineKeyboardButton("🎯 Ask Again", callback_data="game_8ball")],
            [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
        ]
        
        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def random_joke(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle random joke command"""
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything! 😄",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
            "Why don't eggs tell jokes? They'd crack each other up! 🥚",
            "What do you call a fake noodle? An impasta! 🍝",
            "Why did the math book look so sad? Because it had too many problems! 📚",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why can't a bicycle stand up by itself? It's two tired! 🚲",
            "What do you call a sleeping bull? A bulldozer! 🐂"
        ]
        
        joke = random.choice(jokes)
        
        result_text = f"🎪 **Random Joke Time!**\n\n{joke}\n\n😂 Hope that made you smile!"
        
        keyboard = [
            [InlineKeyboardButton("🎪 Another Joke", callback_data="game_joke")],
            [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
        ]
        
        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command"""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        
        stats_text = f"📊 **GROUP MEG Bot Statistics** 🇵🇸\n\n"
        stats_text += f"⚡ **Commands Used:** {self.stats['commands_used']}\n"
        stats_text += f"🏢 **Groups Managed:** {len(self.groups_data)}\n"
        stats_text += f"👥 **Users Registered:** {len(self.users_data)}\n"
        stats_text += f"⏰ **Uptime:** {str(uptime).split('.')[0]}\n"
        stats_text += f"🚀 **Status:** Online and Active\n"
        stats_text += f"🔧 **Version:** 2.0.0\n"
        stats_text += f"🐍 **Python Version:** 3.9+\n"
        stats_text += f"📡 **Library:** python-telegram-bot v20+"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def developer_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle developer info command"""
        dev = self.config["developer"]
        
        dev_text = f"👨‍💻 **Developer Information**\n\n"
        dev_text += f"🏷️ **Name:** {dev['name']}\n"
        dev_text += f"🌍 **Nationality:** {dev['nationality']}\n"
        dev_text += f"📱 **Username:** {dev['username']}\n"
        dev_text += f"🔗 **GitHub:** {dev.get('github', 'Not provided')}\n\n"
        dev_text += f"💼 **Services:**\n"
        dev_text += f"• Custom Telegram Bot Development\n"
        dev_text += f"• Python Programming & Automation\n"
        dev_text += f"• Web Scraping & Data Analysis\n"
        dev_text += f"• API Integration & Backend Development\n\n"
        dev_text += f"💬 **Contact:** {dev['contact']}\n\n"
        dev_text += f"⭐ **About This Bot:**\n"
        dev_text += f"GROUP MEG Bot is a comprehensive group management solution "
        dev_text += f"built with modern Python practices and the latest Telegram Bot API features."
        
        keyboard = [
            [InlineKeyboardButton("📱 Contact Developer", url=f"https://t.me/{dev['username'].replace('@', '')}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            dev_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "main_menu":
            await query.edit_message_text(
                "🏠 **Main Menu** - Choose an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_main_keyboard()
            )
            
        elif data == "show_moderation":
            await query.edit_message_text(
                "🛡️ **Moderation Tools** - Choose an action:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_moderation_keyboard()
            )
            
        elif data == "show_games":
            await query.edit_message_text(
                "🎮 **Games & Fun** - Choose a game:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_games_keyboard()
            )
            
        elif data == "show_utilities":
            await query.edit_message_text(
                "🔧 **Utilities** - Choose a utility:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_utilities_keyboard()
            )
            
        elif data == "show_rules":
            await self.show_rules_inline(query)
            
        elif data == "show_stats":
            await self.show_stats_inline(query)
            
        elif data == "show_developer":
            await self.show_developer_inline(query)
            
        elif data == "show_help":
            await self.show_help_inline(query)
            
        elif data.startswith("game_"):
            await self.handle_game_callback(query, data)

    async def show_rules_inline(self, query) -> None:
        """Show rules in inline mode"""
        chat_id = str(query.message.chat.id)
        rules = self.groups_data.get(chat_id, {}).get("rules", self.config["default_rules"])
        
        rules_text = "📋 **Group Rules:**\n\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await query.edit_message_text(
            rules_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_stats_inline(self, query) -> None:
        """Show stats in inline mode"""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        
        stats_text = f"📊 **Bot Statistics**\n\n"
        stats_text += f"⚡ **Commands Used:** {self.stats['commands_used']}\n"
        stats_text += f"🏢 **Groups Managed:** {len(self.groups_data)}\n"
        stats_text += f"👥 **Users Registered:** {len(self.users_data)}\n"
        stats_text += f"⏰ **Uptime:** {str(uptime).split('.')[0]}\n"
        stats_text += f"🚀 **Status:** Online and Active"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await query.edit_message_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_developer_inline(self, query) -> None:
        """Show developer info in inline mode"""
        dev = self.config["developer"]
        
        dev_text = f"👨‍💻 **Developer Information**\n\n"
        dev_text += f"🏷️ **Name:** {dev['name']}\n"
        dev_text += f"🌍 **Nationality:** {dev['nationality']}\n"
        dev_text += f"📱 **Username:** {dev['username']}\n\n"
        dev_text += f"💼 **Services:**\n"
        dev_text += f"• Custom Telegram Bot Development\n"
        dev_text += f"• Python Programming & Automation\n"
        dev_text += f"• Web Scraping & Data Analysis\n"
        dev_text += f"• API Integration\n\n"
        dev_text += f"💬 Contact for bot development services!"
        
        keyboard = [
            [InlineKeyboardButton("📱 Contact", url=f"https://t.me/{dev['username'].replace('@', '')}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            dev_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_help_inline(self, query) -> None:
        """Show help in inline mode"""
        help_text = f"❓ **Quick Help**\n\n"
        help_text += f"🛡️ **Moderation:** Warn, kick, ban users\n"
        help_text += f"🎮 **Games:** Dice, coin flip, 8-ball, jokes\n"
        help_text += f"📊 **Stats:** Bot and group statistics\n"
        help_text += f"🔧 **Utils:** Group info, member count, etc.\n\n"
        help_text += f"💡 Use `/help` for detailed command list"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_game_callback(self, query, data: str) -> None:
        """Handle game callback queries"""
        if data == "game_dice":
            dice_result = random.randint(1, 6)
            dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][dice_result - 1]
            
            result_text = f"🎲 **Dice Roll!**\n\n{dice_emoji} You rolled: **{dice_result}**"
            
            if dice_result == 6:
                result_text += "\n🎉 Lucky six!"
            elif dice_result == 1:
                result_text += "\n😅 Better luck next time!"
            
            keyboard = [
                [InlineKeyboardButton("🎲 Roll Again", callback_data="game_dice")],
                [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
            ]
            
        elif data == "game_coin":
            result = random.choice(["heads", "tails"])
            emoji = "👑" if result == "heads" else "⚪"
            
            result_text = f"🪙 **Coin Flip!**\n\n{emoji} It's **{result.upper()}**!"
            
            keyboard = [
                [InlineKeyboardButton("🪙 Flip Again", callback_data="game_coin")],
                [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
            ]
            
        elif data == "game_8ball":
            responses = [
                "🔮 It is certain", "🔮 Without a doubt", "🔮 Yes definitely",
                "🔮 You may rely on it", "🔮 Most likely", "🔮 Reply hazy, try again",
                "🔮 Ask again later", "🔮 Don't count on it", "🔮 My reply is no"
            ]
            answer = random.choice(responses)
            
            result_text = f"🎯 **Magic 8-Ball**\n\n💫 **Answer:** {answer}"
            
            keyboard = [
                [InlineKeyboardButton("🎯 Ask Again", callback_data="game_8ball")],
                [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
            ]
            
        elif data == "game_joke":
            jokes = [
                "Why don't scientists trust atoms? Because they make up everything! 😄",
                "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                "What do you call a fake noodle? An impasta! 🍝",
                "Why did the math book look so sad? Because it had too many problems! 📚"
            ]
            joke = random.choice(jokes)
            
            result_text = f"🎪 **Random Joke!**\n\n{joke}"
            
            keyboard = [
                [InlineKeyboardButton("🎪 Another Joke", callback_data="game_joke")],
                [InlineKeyboardButton("🔙 Back to Games", callback_data="show_games")]
            ]
            
        else:
            return
            
        await query.edit_message_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ping command"""
        await update.message.reply_text("🏓 Pong! Bot is online and responsive! ✅")

    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /uptime command"""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        
        uptime_text = f"⏰ **Bot Uptime**\n\n"
        uptime_text += f"🚀 **Online for:** {str(uptime).split('.')[0]}\n"
        uptime_text += f"📅 **Started:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        uptime_text += f"✅ **Status:** Fully Operational"
        
        await update.message.reply_text(uptime_text, parse_mode=ParseMode.MARKDOWN)

    async def clean_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clean command to delete messages"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to clean messages!")
            return

        try:
            count = int(context.args[0]) if context.args else 10
            count = min(count, 100)  # Limit to 100 messages
            
            # This is a simplified version - in practice you'd need to store message IDs
            await update.message.reply_text(f"🧹 Would clean {count} messages (feature needs message storage implementation)")
            
        except (ValueError, IndexError):
            await update.message.reply_text("❓ Usage: `/clean <number>` (max 100)")

    async def groupinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /groupinfo command"""
        chat = update.effective_chat
        
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
            admins = await context.bot.get_chat_administrators(chat.id)
            admin_count = len(admins)
            
            info_text = f"ℹ️ **Group Information**\n\n"
            info_text += f"🏷️ **Name:** {chat.title}\n"
            info_text += f"🆔 **ID:** `{chat.id}`\n"
            info_text += f"👥 **Members:** {member_count}\n"
            info_text += f"👮 **Admins:** {admin_count}\n"
            info_text += f"📝 **Type:** {chat.type.title()}\n"
            
            if chat.description:
                info_text += f"📄 **Description:** {chat.description[:100]}...\n"
                
        except Exception as e:
            info_text = f"❌ Could not fetch group information: {str(e)}"
            
        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)

    async def membercount_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /membercount command"""
        try:
            count = await context.bot.get_chat_member_count(update.effective_chat.id)
            await update.message.reply_text(f"👥 **Member Count:** {count} members")
        except Exception as e:
            await update.message.reply_text(f"❌ Could not get member count: {str(e)}")

    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle new member joining"""
        for member in update.message.new_chat_members:
            welcome_msg = self.config["welcome_message"].format(
                name=member.first_name,
                username=member.username or "N/A"
            )
            
            keyboard = [
                [InlineKeyboardButton("📋 Read Rules", callback_data="show_rules")],
                [InlineKeyboardButton("❓ Get Help", callback_data="show_help")]
            ]
            
            await update.message.reply_text(
                welcome_msg,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def goodbye_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle member leaving"""
        member = update.message.left_chat_member
        goodbye_msg = self.config["goodbye_message"].format(
            name=member.first_name,
            username=member.username or "N/A"
        )
        
        await update.message.reply_text(goodbye_msg)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error('Update "%s" caused error "%s"', update, context.error)
        
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ **An error occurred!**\n\n"
                    "The bot encountered an unexpected error. "
                    "Please try again or contact support if the problem persists."
                )
            except Exception:
                pass  # If we can't send error message, just log it

def main():
    """Main function to run the bot"""
    # Get bot token from environment variable
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not found!")
        return

    # Initialize bot
    bot = GroupMegBot()
    
    # Create application
    application = Application.builder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("rules", bot.rules_command))
    application.add_handler(CommandHandler("warn", bot.warn_command))
    application.add_handler(CommandHandler("kick", bot.kick_command))
    application.add_handler(CommandHandler("ban", bot.ban_command))
    application.add_handler(CommandHandler("dice", bot.dice_game))
    application.add_handler(CommandHandler("coin", bot.coin_flip))
    application.add_handler(CommandHandler("8ball", bot.magic_8ball))
    application.add_handler(CommandHandler("joke", bot.random_joke))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(CommandHandler("dev", bot.developer_info))
    application.add_handler(CommandHandler("ping", bot.ping_command))
    application.add_handler(CommandHandler("uptime", bot.uptime_command))
    application.add_handler(CommandHandler("clean", bot.clean_command))
    application.add_handler(CommandHandler("groupinfo", bot.groupinfo_command))
    application.add_handler(CommandHandler("membercount", bot.membercount_command))

    # Add callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(bot.button_handler))

    # Add message handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot.welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, bot.goodbye_member))

    # Add error handler
    application.add_error_handler(bot.error_handler)

    # Set bot commands
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

    # Start the bot
    logger.info("🚀 Starting GROUP MEG Bot...")
    logger.info(f"👨‍💻 Developer: {bot.config['developer']['name']}")
    logger.info(f"🇧🇩 Nationality: {bot.config['developer']['nationality']}")
    logger.info(f"📱 Contact: {bot.config['developer']['username']}")
    
    # Run the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

