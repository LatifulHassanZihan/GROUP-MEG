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
from collections import defaultdict

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
        self.reputation_data = self.load_json_file("reputation.json", {})
        
        # Anti-spam tracking
        self.user_messages = defaultdict(list)
        self.user_joins = defaultdict(list)
        
        # Adult content keywords (expandable)
        self.adult_keywords = [
            'porn', 'sex', 'nude', 'naked', 'xxx', 'adult', 'nsfw',
            'explicit', 'erotic', 'sexual', 'sexx', 'p0rn', 'n00des'
        ]
        
        # Spam patterns
        self.spam_patterns = [
            r'(https?://\S+)',  # URLs
            r'(@\w+)',          # Mentions
            r'(\d{10,})',       # Long numbers (phone numbers)
            r'(₹|\$|€|£)\d+',   # Money patterns
        ]
        
        # Bot statistics
        self.stats = {
            "commands_used": 0,
            "groups_managed": len(self.groups_data),
            "users_registered": len(self.users_data),
            "start_time": datetime.now().isoformat(),
            "messages_filtered": 0,
            "spam_blocked": 0,
            "adult_content_blocked": 0
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
            "reputation_system": True
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

    def is_flood(self, user_id: int, chat_id: int) -> bool:
        """Check if user is flooding"""
        now = datetime.now()
        key = f"{chat_id}_{user_id}"
        
        # Clean old messages
        cutoff = now - timedelta(seconds=self.config["flood_time"])
        self.user_messages[key] = [
            msg_time for msg_time in self.user_messages[key] 
            if msg_time > cutoff
        ]
        
        # Add current message
        self.user_messages[key].append(now)
        
        return len(self.user_messages[key]) > self.config["flood_limit"]

    def contains_adult_content(self, text: str) -> bool:
        """Check if text contains adult content"""
        if not self.config.get("adult_protection", True):
            return False
            
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.adult_keywords)

    def is_spam_message(self, text: str) -> bool:
        """Check if message is spam"""
        if not self.config.get("anti_spam", True):
            return False
            
        # Check for spam patterns
        spam_score = 0
        for pattern in self.spam_patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            spam_score += matches
            
        # Check for excessive repetition
        words = text.split()
        if len(words) > 5:
            unique_words = len(set(words))
            if unique_words / len(words) < 0.3:  # Less than 30% unique words
                spam_score += 2
                
        return spam_score >= 3

    def update_reputation(self, user_id: int, chat_id: int, change: int) -> None:
        """Update user reputation"""
        if not self.config.get("reputation_system", True):
            return
            
        key = f"{chat_id}_{user_id}"
        if key not in self.reputation_data:
            self.reputation_data[key] = {"score": 0, "warnings": 0, "kicks": 0}
        
        self.reputation_data[key]["score"] += change
        self.save_json_file("reputation.json", self.reputation_data)

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
                InlineKeyboardButton("🏆 Reputation", callback_data="show_reputation"),
                InlineKeyboardButton("🛡️ Protection", callback_data="show_protection")
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
            [
                InlineKeyboardButton("📋 Add Rules", callback_data="cmd_addrules"),
                InlineKeyboardButton("🧹 Clean Chat", callback_data="cmd_clean")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_protection_keyboard(self) -> InlineKeyboardMarkup:
        """Create protection menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🔞 Adult Filter", callback_data="toggle_adult"),
                InlineKeyboardButton("🚫 Anti-Spam", callback_data="toggle_spam")
            ],
            [
                InlineKeyboardButton("💬 Flood Control", callback_data="config_flood"),
                InlineKeyboardButton("🤖 Auto-Delete", callback_data="toggle_autodelete")
            ],
            [
                InlineKeyboardButton("🏆 Reputation", callback_data="toggle_reputation"),
                InlineKeyboardButton("📊 Filter Stats", callback_data="show_filter_stats")
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
            [
                InlineKeyboardButton("🎮 Mini Games", callback_data="show_minigames"),
                InlineKeyboardButton("🏆 Leaderboard", callback_data="game_leaderboard")
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
            [
                InlineKeyboardButton("⚙️ Welcome Setup", callback_data="util_welcome"),
                InlineKeyboardButton("📋 Rules Manager", callback_data="util_rules")
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

🛡️ **Advanced Protection**
• Adult content filtering
• Anti-spam & flood control
• Auto-moderation system
• Smart reputation system

🛡️ **Moderation Tools**
• Warn, kick, ban, mute users
• Role management system
• Custom rules management
• Message filtering & cleanup

🎮 **Games & Fun**
• Mini-games and entertainment
• Interactive commands
• Group activities & competitions
• Leaderboard system

📊 **Statistics & Analytics**
• Group insights & analytics
• User activity tracking
• Bot performance metrics
• Reputation tracking

⚙️ **Advanced Utilities**
• Smart welcome messages
• Auto-delete system
• Data export features
• Customizable settings

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
• `/addrules` - Add custom rules (admin)
• `/delrule number` - Delete rule (admin)

**🛡️ Protection Commands:**
• `/filter on/off` - Toggle content filtering
• `/antispam on/off` - Toggle anti-spam
• `/adultfilter on/off` - Toggle adult filter
• `/floodlimit number` - Set flood limit
• `/reputation @user` - Check user reputation

**🎮 Fun Commands:**
• `/dice` - Roll a dice
• `/coin` - Flip a coin
• `/8ball question` - Ask the magic 8-ball
• `/joke` - Get a random joke
• `/quiz` - Start a quiz game
• `/rps rock/paper/scissors` - Rock paper scissors

**📊 Info Commands:**
• `/rules` - Show group rules
• `/settings` - Group settings
• `/stats` - Bot statistics
• `/groupinfo` - Group information
• `/membercount` - Member count
• `/filterstats` - Protection statistics

**🔧 Utility Commands:**
• `/clean number` - Delete messages
• `/invitelink` - Get invite link
• `/ping` - Check bot status
• `/uptime` - Bot uptime
• `/setwelcome message` - Set welcome message
• `/export type` - Export group data

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
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Rule", callback_data="cmd_addrules")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            rules_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def addrules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /addrules command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to add rules!")
            return

        if not context.args:
            await update.message.reply_text(
                "📋 **Add Rules**\n\n"
                "Usage: `/addrules Your new rule here`\n\n"
                "Example: `/addrules No sharing personal information`\n\n"
                "💡 You can add multiple rules by using this command multiple times!"
            )
            return

        rule_text = " ".join(context.args)
        chat_id = str(update.effective_chat.id)
        
        if chat_id not in self.groups_data:
            self.groups_data[chat_id] = {"rules": self.config["default_rules"].copy()}
        
        if "rules" not in self.groups_data[chat_id]:
            self.groups_data[chat_id]["rules"] = self.config["default_rules"].copy()
        
        self.groups_data[chat_id]["rules"].append(rule_text)
        self.save_json_file("groups.json", self.groups_data)
        
        rule_number = len(self.groups_data[chat_id]["rules"])
        
        success_text = f"✅ **Rule Added Successfully!**\n\n"
        success_text += f"📋 **Rule #{rule_number}:** {rule_text}\n\n"
        success_text += f"📝 **Total Rules:** {rule_number}\n"
        success_text += f"👀 Use `/rules` to see all rules"
        
        keyboard = [
            [InlineKeyboardButton("📋 View All Rules", callback_data="show_rules")],
            [InlineKeyboardButton("➕ Add Another Rule", callback_data="cmd_addrules")]
        ]
        
        await update.message.reply_text(
            success_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def delrule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /delrule command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to delete rules!")
            return

        if not context.args:
            await update.message.reply_text("❓ Usage: `/delrule <rule_number>`")
            return

        try:
            rule_num = int(context.args[0]) - 1
            chat_id = str(update.effective_chat.id)
            
            if chat_id not in self.groups_data or "rules" not in self.groups_data[chat_id]:
                await update.message.reply_text("❌ No custom rules found!")
                return
            
            rules = self.groups_data[chat_id]["rules"]
            
            if rule_num < 0 or rule_num >= len(rules):
                await update.message.reply_text(f"❌ Invalid rule number! Must be between 1-{len(rules)}")
                return
            
            deleted_rule = rules.pop(rule_num)
            self.save_json_file("groups.json", self.groups_data)
            
            await update.message.reply_text(
                f"🗑️ **Rule Deleted!**\n\n"
                f"❌ **Deleted:** {deleted_rule}\n"
                f"📝 **Remaining Rules:** {len(rules)}"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid rule number!")

    async def message_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Filter and moderate messages"""
        if not update.message or not update.message.text:
            return
            
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_text = update.message.text
        
        # Skip filtering for trusted users
        if self.has_permission(user_id, chat_id, "bypass_filters"):
            return
        
        # Check for adult content
        if self.contains_adult_content(message_text):
            self.stats["adult_content_blocked"] += 1
            try:
                await update.message.delete()
                await self.auto_warn_user(update, context, "Adult content detected")
                
                warning_msg = await context.bot.send_message(
                    chat_id,
                    f"🔞 **Content Filtered!**\n\n"
                    f"👤 {update.effective_user.first_name}, your message contained inappropriate content.\n"
                    f"⚠️ This is an automatic warning. Please follow group rules!"
                )
                
                # Auto-delete warning after 10 seconds
                await asyncio.sleep(10)
                try:
                    await warning_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error filtering adult content: {e}")
        
        # Check for spam
        elif self.is_spam_message(message_text):
            self.stats["spam_blocked"] += 1
            try:
                await update.message.delete()
                await self.auto_warn_user(update, context, "Spam message detected")
                
                warning_msg = await context.bot.send_message(
                    chat_id,
                    f"🚫 **Spam Detected!**\n\n"
                    f"👤 {update.effective_user.first_name}, your message appears to be spam.\n"
                    f"⚠️ Please avoid repetitive or promotional content!"
                )
                
                await asyncio.sleep(8)
                try:
                    await warning_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error filtering spam: {e}")
        
        # Check for flooding
        elif self.is_flood(user_id, chat_id):
            try:
                await update.message.delete()
                
                # Mute user for 5 minutes
                mute_permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False
                )
                
                until_date = datetime.now() + timedelta(minutes=5)
                await context.bot.restrict_chat_member(
                    chat_id, user_id, mute_permissions, until_date=until_date
                )
                
                flood_msg = await context.bot.send_message(
                    chat_id,
                    f"🌊 **Flood Control Activated!**\n\n"
                    f"👤 {update.effective_user.first_name} has been muted for 5 minutes.\n"
                    f"💬 **Reason:** Too many messages in a short time\n"
                    f"⏰ **Unmuted:** Automatically in 5 minutes"
                )
                
                await asyncio.sleep(15)
                try:
                    await flood_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error handling flood: {e}")

    async def auto_warn_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str) -> None:
        """Automatically warn a user"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_key = f"{chat_id}_{user_id}"
        
        if user_key not in self.users_data:
            self.users_data[user_key] = {"warnings": 0, "roles": []}
        
        self.users_data[user_key]["warnings"] += 1
        warnings = self.users_data[user_key]["warnings"]
        
        # Update reputation
        self.update_reputation(user_id, chat_id, -2)
        
        self.save_json_file("users.json", self.users_data)
        
        # Auto-kick if warnings exceed limit
        if warnings >= self.config["warn_limit"]:
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.unban_chat_member(chat_id, user_id)
                
                kick_msg = await context.bot.send_message(
                    chat_id,
                    f"🦵 **Auto-Kick Executed!**\n\n"
                    f"👤 {update.effective_user.first_name} has been kicked\n"
                    f"📊 **Warnings:** {warnings}/{self.config['warn_limit']}\n"
                    f"📝 **Final Reason:** {reason}"
                )
                
                await asyncio.sleep(12)
                try:
                    await kick_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error auto-kicking user: {e}")

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
        
        # Update reputation
        self.update_reputation(target_user.id, update.effective_chat.id, -3)
        
        self.save_json_file("users.json", self.users_data)

        warn_text = f"⚠️ **User Warned!**\n\n"
        warn_text += f"👤 **User:** {target_user.first_name}\n"
        warn_text += f"📝 **Reason:** {reason}\n"
        warn_text += f"📊 **Warnings:** {warnings}/{self.config['warn_limit']}\n"
        warn_text += f"👮 **By:** {update.effective_user.first_name}"
        
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
            
            # Update reputation
            self.update_reputation(target_user.id, update.effective_chat.id, -5)
            
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
            
            # Update reputation
            self.update_reputation(target_user.id, update.effective_chat.id, -10)
            
            ban_text = f"🔨 **User Banned!**\n\n"
            ban_text += f"👤 **User:** {target_user.first_name}\n"
            ban_text += f"📝 **Reason:** {reason}\n"
            ban_text += f"👮 **By:** {update.effective_user.first_name}"
            
            await update.message.reply_text(ban_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")

    async def reputation_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reputation command"""
        target_user = None
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        elif context.args:
            # In a real bot, resolve username to user
            await update.message.reply_text("❓ Reply to a message to check reputation!")
            return
        else:
            target_user = update.effective_user
        
        user_key = f"{update.effective_chat.id}_{target_user.id}"
        rep_data = self.reputation_data.get(user_key, {"score": 0, "warnings": 0, "kicks": 0})
        
        # Determine reputation level
        score = rep_data["score"]
        if score >= 50:
            level = "🌟 Excellent"
            emoji = "🏆"
        elif score >= 20:
            level = "😊 Good"
            emoji = "👍"
        elif score >= 0:
            level = "😐 Average"
            emoji = "⚖️"
        elif score >= -20:
            level = "😟 Poor"
            emoji = "👎"
        else:
            level = "💀 Terrible"
            emoji = "⚠️"
        
        rep_text = f"🏆 **Reputation Report**\n\n"
        rep_text += f"👤 **User:** {target_user.first_name}\n"
        rep_text += f"{emoji} **Level:** {level}\n"
        rep_text += f"📊 **Score:** {score}\n"
        rep_text += f"⚠️ **Warnings:** {rep_data.get('warnings', 0)}\n"
        rep_text += f"🦵 **Kicks:** {rep_data.get('kicks', 0)}\n\n"
        rep_text += f"💡 **Tips:**\n"
        rep_text += f"• Be active and helpful (+points)\n"
        rep_text += f"• Avoid breaking rules (-points)\n"
        rep_text += f"• Participate in group activities"
        
        await update.message.reply_text(rep_text, parse_mode=ParseMode.MARKDOWN)

    async def filterstats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /filterstats command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Only admins can view filter statistics!")
            return
        
        stats_text = f"📊 **Filter Statistics**\n\n"
        stats_text += f"🔞 **Adult Content Blocked:** {self.stats['adult_content_blocked']}\n"
        stats_text += f"🚫 **Spam Messages Blocked:** {self.stats['spam_blocked']}\n"
        stats_text += f"📝 **Total Messages Filtered:** {self.stats['messages_filtered']}\n\n"
        
        # Protection status
        chat_id = str(update.effective_chat.id)
        group_settings = self.groups_data.get(chat_id, {})
        
        stats_text += f"🛡️ **Protection Status:**\n"
        stats_text += f"• Adult Filter: {'✅ ON' if group_settings.get('adult_protection', True) else '❌ OFF'}\n"
        stats_text += f"• Anti-Spam: {'✅ ON' if group_settings.get('anti_spam', True) else '❌ OFF'}\n"
        stats_text += f"• Flood Control: {'✅ ON' if group_settings.get('flood_control', True) else '❌ OFF'}\n"
        stats_text += f"• Reputation System: {'✅ ON' if group_settings.get('reputation_system', True) else '❌ OFF'}\n"
        
        stats_text += f"\n⚙️ **Limits:**\n"
        stats_text += f"• Warning Limit: {self.config['warn_limit']}\n"
        stats_text += f"• Flood Limit: {self.config['flood_limit']} msgs/{self.config['flood_time']}s"
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    # [Continue with existing game methods: dice_game, coin_flip, magic_8ball, random_joke]
    async def dice_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle dice game"""
        dice_result = random.randint(1, 6)
        dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][dice_result - 1]
        
        # Update reputation for participation
        self.update_reputation(update.effective_user.id, update.effective_chat.id, 1)
        
        result_text = f"🎲 **Dice Roll Result!**\n\n"
        result_text += f"{dice_emoji} You rolled: **{dice_result}**\n\n"
        
        if dice_result == 6:
            result_text += "🎉 Lucky six! You're on fire! 🔥\n+3 reputation points!"
            self.update_reputation(update.effective_user.id, update.effective_chat.id, 3)
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
        
        # Update reputation for participation
        self.update_reputation(update.effective_user.id, update.effective_chat.id, 1)
        
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
        
        # Update reputation for participation
        self.update_reputation(update.effective_user.id, update.effective_chat.id, 1)
        
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
            "What do you call a sleeping bull? A bulldozer! 🐂",
            "Why don't programmers like nature? It has too many bugs! 🐛",
            "What do you call a fish wearing a bowtie? Sofishticated! 🐟"
        ]
        
        joke = random.choice(jokes)
        
        # Update reputation for participation
        self.update_reputation(update.effective_user.id, update.effective_chat.id, 1)
        
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

    # [Continue with existing stats and other methods]
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command"""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        
        stats_text = f"📊 **GROUP MEG Bot Statistics** 🇵🇸\n\n"
        stats_text += f"⚡ **Commands Used:** {self.stats['commands_used']}\n"
        stats_text += f"🏢 **Groups Managed:** {len(self.groups_data)}\n"
        stats_text += f"👥 **Users Registered:** {len(self.users_data)}\n"
        stats_text += f"🛡️ **Messages Filtered:** {self.stats['messages_filtered']}\n"
        stats_text += f"🚫 **Spam Blocked:** {self.stats['spam_blocked']}\n"
        stats_text += f"🔞 **Adult Content Blocked:** {self.stats['adult_content_blocked']}\n"
        stats_text += f"⏰ **Uptime:** {str(uptime).split('.')[0]}\n"
        stats_text += f"🚀 **Status:** Online and Active\n"
        stats_text += f"🔧 **Version:** 2.5.0 Enhanced\n"
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
        dev_text += f"• Advanced Group Management Systems\n"
        dev_text += f"• AI-Powered Content Filtering\n"
        dev_text += f"• Python Programming & Automation\n"
        dev_text += f"• Web Scraping & Data Analysis\n"
        dev_text += f"• API Integration & Backend Development\n\n"
        dev_text += f"✨ **Latest Features Added:**\n"
        dev_text += f"• Smart adult content detection\n"
        dev_text += f"• Advanced anti-spam protection\n"
        dev_text += f"• User reputation system\n"
        dev_text += f"• Custom rules management\n"
        dev_text += f"• Flood control & auto-moderation\n\n"
        dev_text += f"💬 **Contact:** {dev['contact']}\n\n"
        dev_text += f"⭐ **About This Bot:**\n"
        dev_text += f"GROUP MEG Bot v2.5 is a next-generation group management solution "
        dev_text += f"featuring AI-powered content filtering, advanced anti-spam protection, "
        dev_text += f"and comprehensive moderation tools built with modern Python practices."
        
        keyboard = [
            [InlineKeyboardButton("📱 Contact Developer", url=f"https://t.me/{dev['username'].replace('@', '')}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            dev_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # [Continue with button handlers and other methods...]
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
            
        elif data == "show_protection":
            await query.edit_message_text(
                "🛡️ **Protection Settings** - Configure security:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.create_protection_keyboard()
            )
            
        elif data == "show_rules":
            await self.show_rules_inline(query)
            
        elif data == "show_stats":
            await self.show_stats_inline(query)
            
        elif data == "show_developer":
            await self.show_developer_inline(query)
            
        elif data == "show_help":
            await self.show_help_inline(query)
            
        elif data == "show_reputation":
            await self.show_reputation_inline(query)
            
        elif data.startswith("game_"):
            await self.handle_game_callback(query, data)
            
        elif data.startswith("toggle_") or data.startswith("config_"):
            await self.handle_protection_callback(query, data)

    async def show_reputation_inline(self, query) -> None:
        """Show reputation system info"""
        user_key = f"{query.message.chat.id}_{query.from_user.id}"
        rep_data = self.reputation_data.get(user_key, {"score": 0})
        
        score = rep_data["score"]
        if score >= 50:
            level = "🌟 Excellent"
        elif score >= 20:
            level = "😊 Good"
        elif score >= 0:
            level = "😐 Average"
        else:
            level = "😟 Poor"
        
        rep_text = f"🏆 **Your Reputation**\n\n"
        rep_text += f"📊 **Score:** {score}\n"
        rep_text += f"🎖️ **Level:** {level}\n\n"
        rep_text += f"💡 **How to improve:**\n"
        rep_text += f"• Participate in games (+1 each)\n"
        rep_text += f"• Help other members (+2)\n"
        rep_text += f"• Follow group rules (+3)\n"
        rep_text += f"• Avoid warnings (-3 each)\n"
        rep_text += f"• Avoid kicks/bans (-5/-10)"
        
        keyboard = [
            [InlineKeyboardButton("📊 Group Leaderboard", callback_data="show_leaderboard")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            rep_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_protection_callback(self, query, data: str) -> None:
        """Handle protection setting callbacks"""
        chat_id = str(query.message.chat.id)
        
        if chat_id not in self.groups_data:
            self.groups_data[chat_id] = {}
        
        if data == "toggle_adult":
            current = self.groups_data[chat_id].get("adult_protection", True)
            self.groups_data[chat_id]["adult_protection"] = not current
            status = "✅ ENABLED" if not current else "❌ DISABLED"
            
            await query.edit_message_text(
                f"🔞 **Adult Content Filter**\n\n"
                f"**Status:** {status}\n\n"
                f"This filter automatically detects and removes inappropriate content.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Protection", callback_data="show_protection")]
                ])
            )
            
        elif data == "toggle_spam":
            current = self.groups_data[chat_id].get("anti_spam", True)
            self.groups_data[chat_id]["anti_spam"] = not current
            status = "✅ ENABLED" if not current else "❌ DISABLED"
            
            await query.edit_message_text(
                f"🚫 **Anti-Spam Filter**\n\n"
                f"**Status:** {status}\n\n"
                f"This filter detects and blocks spam messages automatically.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Protection", callback_data="show_protection")]
                ])
            )
        
        self.save_json_file("groups.json", self.groups_data)

    # [Continue with existing methods: show_rules_inline, show_stats_inline, etc...]
    
    async def show_rules_inline(self, query) -> None:
        """Show rules in inline mode"""
        chat_id = str(query.message.chat.id)
        rules = self.groups_data.get(chat_id, {}).get("rules", self.config["default_rules"])
        
        rules_text = "📋 **Group Rules:**\n\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule}\n"
        
        rules_text += f"\n⚠️ **Breaking rules may result in warnings, kicks, or bans.**"
        
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
        stats_text += f"🛡️ **Messages Filtered:** {self.stats['messages_filtered']}\n"
        stats_text += f"🚫 **Spam Blocked:** {self.stats['spam_blocked']}\n"
        stats_text += f"🔞 **Adult Content Blocked:** {self.stats['adult_content_blocked']}\n"
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
        dev_text += f"• Advanced Group Management Systems\n"
        dev_text += f"• AI-Powered Content Filtering\n"
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
        help_text += f"🛡️ **Moderation:** Warn, kick, ban users + custom rules\n"
        help_text += f"🔞 **Protection:** Adult filter, anti-spam, flood control\n"
        help_text += f"🎮 **Games:** Dice, coin flip, 8-ball, jokes + reputation\n"
        help_text += f"📊 **Stats:** Bot, group statistics + filter reports\n"
        help_text += f"🔧 **Utils:** Group info, member count, data export\n"
        help_text += f"🏆 **Reputation:** User ranking and reward system\n\n"
        help_text += f"💡 Use `/help` for detailed command list"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]]
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_game_callback(self, query, data: str) -> None:
        """Handle game callback queries"""
        # Update reputation for game participation
        self.update_reputation(query.from_user.id, query.message.chat.id, 1)
        
        if data == "game_dice":
            dice_result = random.randint(1, 6)
            dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][dice_result - 1]
            
            result_text = f"🎲 **Dice Roll!**\n\n{dice_emoji} You rolled: **{dice_result}**"
            
            if dice_result == 6:
                result_text += "\n🎉 Lucky six! +2 reputation!"
                self.update_reputation(query.from_user.id, query.message.chat.id, 2)
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
                "Why did the math book look so sad? Because it had too many problems! 📚",
                "Why don't programmers like nature? It has too many bugs! 🐛"
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

    # [Continue with existing utility methods...]
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
        uptime_text += f"✅ **Status:** Fully Operational with Enhanced Protection"
        
        await update.message.reply_text(uptime_text, parse_mode=ParseMode.MARKDOWN)

    async def clean_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clean command to delete messages"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You don't have permission to clean messages!")
            return

        try:
            count = int(context.args[0]) if context.args else 10
            count = min(count, 100)  # Limit to 100 messages
            
            await update.message.reply_text(
                f"🧹 **Message Cleanup**\n\n"
                f"Would clean {count} messages\n"
                f"💡 Note: This feature requires message storage implementation\n"
                f"for full functionality in production environment."
            )
            
        except (ValueError, IndexError):
            await update.message.reply_text("❓ Usage: `/clean <number>` (max 100)")

    async def groupinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /groupinfo command"""
        chat = update.effective_chat
        
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
            admins = await context.bot.get_chat_administrators(chat.id)
            admin_count = len(admins)
            
            # Get protection status
            chat_id = str(chat.id)
            group_data = self.groups_data.get(chat_id, {})
            
            info_text = f"ℹ️ **Group Information**\n\n"
            info_text += f"🏷️ **Name:** {chat.title}\n"
            info_text += f"🆔 **ID:** `{chat.id}`\n"
            info_text += f"👥 **Members:** {member_count}\n"
            info_text += f"👮 **Admins:** {admin_count}\n"
            info_text += f"📝 **Type:** {chat.type.title()}\n\n"
            
            info_text += f"🛡️ **Protection Status:**\n"
            info_text += f"• Adult Filter: {'✅' if group_data.get('adult_protection', True) else '❌'}\n"
            info_text += f"• Anti-Spam: {'✅' if group_data.get('anti_spam', True) else '❌'}\n"
            info_text += f"• Reputation System: {'✅' if group_data.get('reputation_system', True) else '❌'}\n"
            
            if chat.description:
                info_text += f"\n📄 **Description:** {chat.description[:100]}..."
                
        except Exception as e:
            info_text = f"❌ Could not fetch group information: {str(e)}"
            
        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)

    async def membercount_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /membercount command"""
        try:
            count = await context.bot.get_chat_member_count(update.effective_chat.id)
            await update.message.reply_text(
                f"👥 **Member Count:** {count} members\n"
                f"📊 **Active Users:** {len(self.users_data)} registered\n"
                f"🏆 **With Reputation:** {len(self.reputation_data)} users"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Could not get member count: {str(e)}")

    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle new member joining"""
        for member in update.message.new_chat_members:
            # Initialize user data
            user_key = f"{update.effective_chat.id}_{member.id}"
            if user_key not in self.users_data:
                self.users_data[user_key] = {"warnings": 0, "roles": [], "join_date": datetime.now().isoformat()}
                self.save_json_file("users.json", self.users_data)
            
            # Initialize reputation
            if user_key not in self.reputation_data:
                self.reputation_data[user_key] = {"score": 5, "warnings": 0, "kicks": 0}  # Start with 5 points
                self.save_json_file("reputation.json", self.reputation_data)
            
            welcome_msg = self.config["welcome_message"].format(
                name=member.first_name,
                username=member.username or "N/A"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("📋 Read Rules", callback_data="show_rules"),
                    InlineKeyboardButton("🏆 Reputation", callback_data="show_reputation")
                ],
                [
                    InlineKeyboardButton("❓ Get Help", callback_data="show_help"),
                    InlineKeyboardButton("🎮 Play Games", callback_data="show_games")
                ]
            ]
            
            welcome_message = await update.message.reply_text(
                welcome_msg,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Auto-delete welcome message after 2 minutes if configured
            chat_id = str(update.effective_chat.id)
            if self.groups_data.get(chat_id, {}).get("auto_delete_joins", False):
                await asyncio.sleep(120)
                try:
                    await welcome_message.delete()
                    await update.message.delete()
                except:
                    pass

    async def goodbye_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle member leaving"""
        member = update.message.left_chat_member
        goodbye_msg = self.config["goodbye_message"].format(
            name=member.first_name,
            username=member.username or "N/A"
        )
        
        goodbye_message = await update.message.reply_text(goodbye_msg)
        
        # Auto-delete goodbye message after 1 minute
        await asyncio.sleep(60)
        try:
            await goodbye_message.delete()
            await update.message.delete()
        except:
            pass

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error('Update "%s" caused error "%s"', update, context.error)
        
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ **An error occurred!**\n\n"
                    "The bot encountered an unexpected error. "
                    "Please try again or contact support if the problem persists.\n\n"
                    f"🆔 **Error ID:** `{id(context.error)}`"
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
    application.add_handler(CommandHandler("addrules", bot.addrules_command))
    application.add_handler(CommandHandler("delrule", bot.delrule_command))
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
    application.add_handler(CommandHandler("reputation", bot.reputation_command))
    application.add_handler(CommandHandler("filterstats", bot.filterstats_command))

    # Add callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(bot.button_handler))

    # Add message handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot.welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, bot.goodbye_member))
    
    # Add content filter for all text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message_filter))

    # Add error handler
    application.add_error_handler(bot.error_handler)

    # Set bot commands
    async def set_bot_commands(app):
        commands = [
            BotCommand("start", "🚀 Start the bot and see main menu"),
            BotCommand("help", "❓ Get help and command list"),
            BotCommand("rules", "📋 Show group rules"),
            BotCommand("addrules", "➕ Add custom rules (admin only)"),
            BotCommand("stats", "📊 Show bot statistics"),
            BotCommand("filterstats", "🛡️ Show protection statistics"),
            BotCommand("reputation", "🏆 Check user reputation"),
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
    logger.info("🚀 Starting GROUP MEG Bot v2.5 Enhanced...")
    logger.info(f"👨‍💻 Developer: {bot.config['developer']['name']}")
    logger.info(f"🇧🇩 Nationality: {bot.config['developer']['nationality']}")
    logger.info(f"📱 Contact: {bot.config['developer']['username']}")
    logger.info("🛡️ Enhanced Features: Adult filter, Anti-spam, Reputation system")
    
    # Run the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
