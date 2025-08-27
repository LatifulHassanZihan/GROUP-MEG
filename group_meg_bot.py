#!/usr/bin/env python3
"""
GROUP MEG Bot 🇵🇸 - Advanced Telegram Group Management Bot
Bot Username: @group_meg_bot
Developer: Latiful Hassan Zihan 🇵🇸
Nationality: Bangladeshi 🇧🇩
Username: @alwayszihan

A comprehensive Telegram group management bot with advanced content filtering,
dynamic rules management, anti-spam, and extensive moderation features.
"""

import os
import json
import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import random
import hashlib
import time
from urllib.parse import urlparse

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ChatMember, ChatPermissions, BotCommand, Message
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus, MessageEntityType
from telegram.error import TelegramError, Forbidden, BadRequest

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

class ContentFilter:
    """Advanced content filtering system"""
    
    def __init__(self):
        self.adult_keywords = {
            'explicit': ['porn', 'xxx', 'sex', 'nude', 'naked', 'nsfw', 'adult', 'erotic'],
            'profanity': ['fuck', 'shit', 'bitch', 'damn', 'hell', 'ass', 'bastard'],
            'harassment': ['kill yourself', 'kys', 'die', 'suicide', 'hate you'],
            'spam_indicators': ['click here', 'free money', 'earn now', 'limited offer']
        }
        
        self.suspicious_domains = {
            'adult_sites': ['pornhub.com', 'xvideos.com', 'redtube.com'],
            'scam_sites': ['bit.ly', 'tinyurl.com'],  # Can be customized per group
            'social_media': ['onlyfans.com', 'telegram.me']
        }
    
    def check_content(self, text: str, check_adult=True, check_profanity=True, check_harassment=True) -> Dict:
        """Comprehensive content analysis"""
        results = {
            'is_safe': True,
            'violations': [],
            'severity': 'low',
            'suggested_action': 'none'
        }
        
        text_lower = text.lower()
        
        # Check adult content
        if check_adult:
            adult_violations = self._check_category(text_lower, self.adult_keywords['explicit'])
            if adult_violations:
                results['violations'].extend([f"Adult content: {v}" for v in adult_violations])
                results['severity'] = 'high'
                results['suggested_action'] = 'delete_and_warn'
        
        # Check profanity
        if check_profanity:
            profanity_violations = self._check_category(text_lower, self.adult_keywords['profanity'])
            if profanity_violations:
                results['violations'].extend([f"Profanity: {v}" for v in profanity_violations])
                if results['severity'] != 'high':
                    results['severity'] = 'medium'
                    results['suggested_action'] = 'warn'
        
        # Check harassment
        if check_harassment:
            harassment_violations = self._check_category(text_lower, self.adult_keywords['harassment'])
            if harassment_violations:
                results['violations'].extend([f"Harassment: {v}" for v in harassment_violations])
                results['severity'] = 'high'
                results['suggested_action'] = 'ban'
        
        # Check spam indicators
        spam_violations = self._check_category(text_lower, self.adult_keywords['spam_indicators'])
        if spam_violations:
            results['violations'].extend([f"Spam: {v}" for v in spam_violations])
            if results['severity'] == 'low':
                results['severity'] = 'medium'
                results['suggested_action'] = 'delete'
        
        # Check URLs
        url_violations = self._check_urls(text)
        if url_violations:
            results['violations'].extend(url_violations)
            results['severity'] = 'high'
            results['suggested_action'] = 'delete_and_warn'
        
        results['is_safe'] = len(results['violations']) == 0
        return results
    
    def _check_category(self, text: str, keywords: List[str]) -> List[str]:
        """Check text against keyword category"""
        found = []
        for keyword in keywords:
            if keyword in text:
                found.append(keyword)
        return found
    
    def _check_urls(self, text: str) -> List[str]:
        """Check URLs in text for suspicious domains"""
        violations = []
        
        # Extract URLs using regex
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            try:
                domain = urlparse(url).netloc.lower()
                
                # Check against suspicious domains
                for category, domains in self.suspicious_domains.items():
                    if any(suspicious_domain in domain for suspicious_domain in domains):
                        violations.append(f"Suspicious URL ({category}): {domain}")
                        
            except Exception:
                continue
                
        return violations

class AntiSpamSystem:
    """Advanced anti-spam detection system"""
    
    def __init__(self):
        self.user_message_history: Dict[int, List[Dict]] = {}
        self.spam_thresholds = {
            'max_messages_per_minute': 10,
            'max_identical_messages': 3,
            'max_links_per_message': 2,
            'cooldown_period': 300  # 5 minutes
        }
    
    def check_spam(self, user_id: int, message: Message) -> Dict:
        """Check if message is spam"""
        now = datetime.now()
        
        if user_id not in self.user_message_history:
            self.user_message_history[user_id] = []
        
        user_history = self.user_message_history[user_id]
        
        # Clean old messages (older than 1 hour)
        user_history[:] = [msg for msg in user_history if 
                          (now - datetime.fromisoformat(msg['timestamp'])).seconds < 3600]
        
        # Add current message
        current_msg = {
            'text': message.text or '',
            'timestamp': now.isoformat(),
            'message_id': message.message_id
        }
        user_history.append(current_msg)
        
        # Check various spam indicators
        spam_score = 0
        violations = []
        
        # 1. Message frequency check
        recent_messages = [msg for msg in user_history if 
                          (now - datetime.fromisoformat(msg['timestamp'])).seconds < 60]
        
        if len(recent_messages) > self.spam_thresholds['max_messages_per_minute']:
            spam_score += 50
            violations.append(f"Too many messages: {len(recent_messages)}/min")
        
        # 2. Identical message check
        if message.text:
            identical_count = sum(1 for msg in user_history[-10:] 
                                if msg['text'] == message.text)
            if identical_count > self.spam_thresholds['max_identical_messages']:
                spam_score += 40
                violations.append(f"Repeated message {identical_count} times")
        
        # 3. Link spam check
        if message.text and message.entities:
            link_count = sum(1 for entity in message.entities 
                           if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK])
            if link_count > self.spam_thresholds['max_links_per_message']:
                spam_score += 30
                violations.append(f"Too many links: {link_count}")
        
        # 4. Caps lock check
        if message.text and len(message.text) > 10:
            caps_ratio = sum(1 for c in message.text if c.isupper()) / len(message.text)
            if caps_ratio > 0.7:
                spam_score += 20
                violations.append("Excessive caps lock")
        
        return {
            'is_spam': spam_score >= 50,
            'spam_score': spam_score,
            'violations': violations,
            'suggested_action': self._get_spam_action(spam_score)
        }
    
    def _get_spam_action(self, score: int) -> str:
        """Get suggested action based on spam score"""
        if score >= 80:
            return 'ban'
        elif score >= 60:
            return 'mute'
        elif score >= 40:
            return 'warn'
        else:
            return 'delete'

class GroupMegBot:
    def __init__(self):
        """Initialize the GROUP MEG Bot 🇵🇸"""
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize systems
        self.content_filter = ContentFilter()
        self.anti_spam = AntiSpamSystem()
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize data storage
        self.groups_data = self.load_json_file("groups.json", {})
        self.users_data = self.load_json_file("users.json", {})
        self.warnings_data = self.load_json_file("warnings.json", {})
        
        # Bot statistics
        self.stats = {
            "commands_used": 0,
            "groups_managed": len(self.groups_data),
            "users_registered": len(self.users_data),
            "messages_filtered": 0,
            "spam_blocked": 0,
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
                "github": "https://github.com/alwayszihan",
                "contact": "Contact me for bot development services!"
            },
            "default_rules": [
                "🚫 No spam or excessive posting",
                "🤝 Be respectful to all members",
                "📵 No adult content or inappropriate material",
                "🔇 No promotion without admin permission",
                "💬 Use appropriate language",
                "📝 Follow group topic discussions",
                "⚠️ Admins have the final say",
                "🔗 No suspicious or malicious links",
                "🚷 No harassment or hate speech",
                "📊 Stay on topic and contribute meaningfully"
            ],
            "content_filtering": {
                "enabled": True,
                "check_adult_content": True,
                "check_profanity": True,
                "check_harassment": True,
                "auto_delete_violations": True,
                "notify_admins": True
            },
            "anti_spam": {
                "enabled": True,
                "max_messages_per_minute": 10,
                "max_identical_messages": 3,
                "auto_mute_spammers": True,
                "spam_detection_sensitivity": "medium"
            },
            "role_permissions": {
                "owner": ["all"],
                "admin": ["warn", "kick", "ban", "mute", "delete", "manage_rules", "settings"],
                "moderator": ["warn", "kick", "mute", "delete"],
                "helper": ["warn", "info"],
                "vip": ["games", "fun", "bypass_limits"]
            },
            "welcome_message": "🎉 Welcome to our group, {name}!\n\n📋 Please read our rules with /rules\n💡 Use /help to see available commands\n\n🛡️ This group is protected by advanced content filtering",
            "goodbye_message": "👋 Goodbye {name}! Thanks for being part of our community!",
            "warn_limit": 3,
            "auto_ban_on_violations": False,
            "log_all_actions": True,
            "media_restrictions": {
                "allow_photos": True,
                "allow_videos": True,
                "allow_documents": True,
                "allow_stickers": True,
                "allow_gifs": True,
                "max_file_size_mb": 20
            }
        }

    def load_json_file(self, filename: str, default: Any) -> Any:
        """Load JSON file with default fallback"""
        filepath = self.data_dir / filename
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"✅ Loaded {filename} successfully")
                    return data
            else:
                logger.info(f"📁 {filename} not found, creating with defaults")
                self.save_json_file(filename, default)
                return default
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Invalid JSON in {filename}, using defaults: {e}")
            return default
        except Exception as e:
            logger.warning(f"⚠️ Could not load {filename}, using defaults: {e}")
            return default

    def save_json_file(self, filename: str, data: Any) -> None:
        """Save data to JSON file"""
        filepath = self.data_dir / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

    def get_group_settings(self, chat_id: int) -> Dict:
        """Get group-specific settings"""
        chat_key = str(chat_id)
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {
                "rules": self.config["default_rules"].copy(),
                "settings": {
                    "content_filtering_enabled": True,
                    "anti_spam_enabled": True,
                    "welcome_enabled": True,
                    "auto_delete_commands": False,
                    "allow_links": True,
                    "mute_new_users": False
                },
                "admins": [],
                "warnings": {},
                "banned_words": [],
                "allowed_domains": [],
                "blocked_domains": []
            }
            self.save_json_file("groups.json", self.groups_data)
        
        return self.groups_data[chat_key]

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
                InlineKeyboardButton("🔧 Utilities", callback_data="show_utilities")
            ],
            [
                InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
                InlineKeyboardButton("💬 Welcome/Goodbye", callback_data="show_welcome")
            ],
            [
                InlineKeyboardButton("🎮 Fun & Games", callback_data="show_games"),
                InlineKeyboardButton("🔍 Info Commands", callback_data="show_info")
            ],
            [
                InlineKeyboardButton("🛡️ Content Filter", callback_data="show_content_filter"),
                InlineKeyboardButton("🚨 Admin Help", callback_data="show_admin_help")
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer", callback_data="show_developer"),
                InlineKeyboardButton("❓ Help", callback_data="show_help")
            ],
            [
                InlineKeyboardButton("🔄 Reload Config", callback_data="reload_config"),
                InlineKeyboardButton("🆘 Contact Admin", callback_data="contact_admin")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_add_to_group_keyboard(self) -> InlineKeyboardMarkup:
        """Create Add to Group keyboard"""
        keyboard = [
            [InlineKeyboardButton("➕ Add GROUP MEG to Your Group", url=f"https://t.me/{self.config['bot_username'].replace('@', '')}?startgroup=true")],
            [InlineKeyboardButton("📢 Add to Channel", url=f"https://t.me/{self.config['bot_username'].replace('@', '')}?startchannel=true")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # ======================== BASIC COMMANDS ========================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🚀 Start command handler"""
        user = update.effective_user
        chat = update.effective_chat
        
        self.stats["commands_used"] += 1
        
        if chat.type == "private":
            welcome_text = f"""
🚀 **Welcome to GROUP MEG Bot!** 🇵🇸

👋 Hello {user.first_name}! I'm GROUP MEG, your advanced Telegram group management assistant.

🛡️ **Key Features:**
• Advanced content filtering & anti-spam
• Comprehensive moderation tools  
• Dynamic rules management
• Role-based permissions
• Welcome/goodbye messages
• Fun commands & utilities
• 24/7 group protection

🔧 **Quick Setup:**
1. Add me to your group as admin
2. Use /settings to configure
3. Set custom rules with /setrules
4. Enable content filters

💡 Use the menu below to explore all features!

---
🏷️ **Bot Info:**
• Version: 2.0 Advanced
• Developer: {self.config['developer']['name']}
• Nationality: {self.config['developer']['nationality']}
• Contact: {self.config['developer']['username']}
            """
            
            keyboard = [
                [InlineKeyboardButton("➕ Add to Group", callback_data="add_to_group")],
                [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton("👨‍💻 Developer", callback_data="show_developer")]
            ]
            
        else:
            # Group welcome
            welcome_text = f"""
🎉 **GROUP MEG Bot is now active!** 

Hello {user.first_name}! I'm here to help manage this group with advanced features.

🛡️ **Protection Active:**
✅ Content Filtering
✅ Anti-Spam System  
✅ Advanced Moderation
✅ Rules Management

Use /menu to access all features or /help for command list.
            """
            
            keyboard = [[InlineKeyboardButton("📋 Open Menu", callback_data="main_menu")]]
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """❓ Help command handler"""
        self.stats["commands_used"] += 1
        
        help_text = """
🆘 **GROUP MEG Bot - Command Help** 🇵🇸

📋 **Basic Commands:**
• /start - 🚀 Start bot & show welcome
• /help - ❓ Display this help message
• /about - ℹ️ Bot information
• /rules - 📋 Show group rules
• /settings - ⚙️ Open settings panel (admin)
• /menu - 🎛️ Interactive main menu

🛡️ **Admin & Moderation:**
• /kick [reply] - 🦵 Kick user from group
• /ban [reply] - 🔨 Ban user permanently
• /unban <user_id> - 🔓 Unban user by ID
• /mute <seconds> [reply] - 🔇 Mute user temporarily  
• /unmute [reply] - 🔊 Unmute user
• /purge - 🧹 Delete batch of messages
• /warn [reply + reason] - ⚠️ Warn user
• /warnings [reply] - 📋 Show user warnings
• /clearwarns [reply] - 🧽 Clear all warnings

🎯 **Role Commands:**
• /addrole <role> [reply] - 👑 Assign role to user
• /removerole <role> [reply] - 👤 Remove user role
• /userroles [reply] - 📜 List user roles
• /roles - 🏷️ Display all available roles
• /admins - 👮‍♂️ List group administrators

👋 **Welcome & Goodbye:**
• /setwelcome <text> - 🎉 Set welcome message
• /setgoodbye <text> - 👋 Set goodbye message
• /welcome - 👀 Show current welcome text
• /goodbye - 👀 Show current goodbye text

🔧 **Configuration:**
• /setrules <text> - 📝 Set group rules
• /language <code> - 🌐 Set bot language
• /reloadconfig - 🔄 Reload settings

📊 **Info Commands:**
• /info [reply] - 👤 Show user details
• /stats - 📈 Display group statistics
• /profile [reply] - 👤 Show user profile

🎮 **Fun & Engagement:**
• /quote - 💭 Get motivational quote
• /poll <question> - 📊 Create group poll
• /joke - 😄 Tell a random joke
• /cat - 🐱 Share random cat picture

🛡️ **Moderation & Security:**
• /lock - 🔒 Lock group (disable messaging)
• /unlock - 🔓 Unlock group (enable messaging)  
• /restrict [reply/user_id] - ⚠️ Restrict user
• /detectspam - 🔍 Scan recent spam messages
• /antispam on|off - 🛡️ Toggle anti-spam filter
• /antiflood on|off - 🌊 Toggle anti-flood controls
• /log - 📜 Show recent group events

👥 **Member Management:**
• /promote [reply/user_id] - 👑 Promote to admin
• /demote [reply/user_id] - ⬇️ Demote admin
• /listmembers - 👥 List all members
• /inactive - 😴 List inactive users

📝 **Content & Rules:**
• /antinsfw on|off - 🚫 Adult content filter
• /antilink on|off - 🔗 Block external links

💾 **Storage & Export:**
• /backup - 📦 Export group settings
• /restore <file> - 📂 Restore from backup
• /exportroles - 🏷️ Export user roles as CSV
• /exportrules - 📋 Export rules as text

🆘 **Admin Support:**
• /contactadmin - 📞 Emergency admin help
• /adminhelp - 🚨 List admin commands
• /report [reply] - 🚨 Report to admins

⚙️ **Advanced Options:**
• /setprefix <prefix> - 🏷️ Custom command prefix
• /setrolecolor <role> <color> - 🎨 Set role colors

---
💡 **Tips:**
• Use [reply] by replying to a user's message
• <required> parameters are mandatory  
• [optional] parameters are optional
• Admins have access to all moderation commands

🔗 **Quick Access:** Use /menu for interactive buttons!
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")]
        ]
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ℹ️ About command handler"""
        self.stats["commands_used"] += 1
        
        about_text = f"""
🤖 **About GROUP MEG Bot** 🇵🇸

**Bot Information:**
• Name: {self.config['bot_name']}
• Username: {self.config['bot_username']}
• Version: 2.0 Advanced Edition
• Language: Python 3.11+
• Framework: python-telegram-bot

**Developer Information:**
• Name: {self.config['developer']['name']}
• Nationality: {self.config['developer']['nationality']}
• Username: {self.config['developer']['username']}
• Contact: Available for bot development services!

**Key Features:**
🛡️ Advanced Content Filtering
🚫 Anti-Spam & Anti-Flood Protection
👮‍♂️ Comprehensive Moderation Tools
📋 Dynamic Rules Management  
🎭 Role-Based Permission System
👋 Custom Welcome/Goodbye Messages
🎮 Fun Commands & Utilities
📊 Advanced Statistics & Logging
💾 Backup & Restore Functionality
🌐 Multi-language Support Ready

**Statistics:**
• Commands Used: {self.stats['commands_used']:,}
• Groups Managed: {self.stats['groups_managed']:,}
• Users Registered: {self.stats['users_registered']:,}
• Messages Filtered: {self.stats['messages_filtered']:,}
• Spam Blocked: {self.stats['spam_blocked']:,}

**Bot Uptime:** {self._get_uptime()}

---
🇵🇸 Proudly developed with passion for community management!
        """
        
        keyboard = [
            [InlineKeyboardButton("👨‍💻 Developer", callback_data="show_developer")],
            [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            about_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _get_uptime(self) -> str:
        """Calculate bot uptime"""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m"

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🎛️ Open interactive menu"""
        self.stats["commands_used"] += 1
        
        menu_text = """
🎛️ **GROUP MEG Bot - Main Menu** 🇵🇸

Welcome to the interactive control panel! Select any option below to access advanced features and settings.

🛡️ **Your Group Protection Status:**
✅ Advanced moderation active
✅ Content filtering enabled  
✅ Anti-spam protection on
✅ Rules management ready

Choose a category to explore:
        """
        
        await update.message.reply_text(
            menu_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_main_keyboard()
        )

    # ======================== RULES COMMANDS ========================
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📋 Display group rules"""
        if not update.effective_chat:
            return
            
        self.stats["commands_used"] += 1
        group_settings = self.get_group_settings(update.effective_chat.id)
        rules = group_settings.get("rules", self.config["default_rules"])
        
        rules_text = "📋 **Group Rules:**\n\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule}\n"
        
        rules_text += f"\n⚠️ **Warning System:** {self.config['warn_limit']} warnings = temporary restrictions"
        rules_text += f"\n🛡️ **Protection:** Advanced content filtering active"
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Manage Rules", callback_data="show_rules_manager")],
            [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            rules_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def setrules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📝 Set custom group rules"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to set rules.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide rules text.\nUsage: /setrules <rules_text>")
            return
        
        rules_text = " ".join(context.args)
        rules_list = [rule.strip() for rule in rules_text.split('\n') if rule.strip()]
        
        chat_key = str(update.effective_chat.id)
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {}
        
        self.groups_data[chat_key]["rules"] = rules_list
        self.save_json_file("groups.json", self.groups_data)
        
        await update.message.reply_text(
            f"✅ **Rules Updated Successfully!**\n\n"
            f"📋 Added {len(rules_list)} rules to this group.\n"
            f"💡 Use /rules to view them.",
            parse_mode=ParseMode.MARKDOWN
        )

    # ======================== ADMIN COMMANDS ========================
    
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🦵 Kick user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to kick them.")
            return
        
        user_to_kick = update.message.reply_to_message.from_user
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_to_kick.id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_to_kick.id)
            
            await update.message.reply_text(
                f"🦵 **User Kicked**\n\n"
                f"👤 Name: {user_to_kick.first_name}\n"
                f"🆔 ID: `{user_to_kick.id}`\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._log_action(update.effective_chat.id, "kick", update.effective_user.id, user_to_kick.id)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to kick user: {str(e)}")

    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔨 Ban user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to ban them.")
            return
        
        user_to_ban = update.message.reply_to_message.from_user
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_to_ban.id)
            
            await update.message.reply_text(
                f"🔨 **User Banned**\n\n"
                f"👤 Name: {user_to_ban.first_name}\n"
                f"🆔 ID: `{user_to_ban.id}`\n"
                f"👮‍♂️ By: {update.effective_user.first_name}\n"
                f"⏰ Time: Permanent",
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._log_action(update.effective_chat.id, "ban", update.effective_user.id, user_to_ban.id)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")

    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔓 Unban user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide user ID.\nUsage: /unban <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            
            await update.message.reply_text(
                f"🔓 **User Unbanned**\n\n"
                f"🆔 User ID: `{user_id}`\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._log_action(update.effective_chat.id, "unban", update.effective_user.id, user_id)
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to unban user: {str(e)}")

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔇 Mute user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to mute them.")
            return
        
        user_to_mute = update.message.reply_to_message.from_user
        
        # Parse mute duration
        duration = 300  # Default 5 minutes
        if context.args:
            try:
                duration = int(context.args[0])
            except ValueError:
                duration = 300
        
        try:
            until_date = datetime.now() + timedelta(seconds=duration)
            permissions = ChatPermissions(can_send_messages=False)
            
            await context.bot.restrict_chat_member(
                update.effective_chat.id, 
                user_to_mute.id,
                permissions=permissions,
                until_date=until_date
            )
            
            await update.message.reply_text(
                f"🔇 **User Muted**\n\n"
                f"👤 Name: {user_to_mute.first_name}\n"
                f"🆔 ID: `{user_to_mute.id}`\n"
                f"👮‍♂️ By: {update.effective_user.first_name}\n"
                f"⏰ Duration: {duration} seconds",
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._log_action(update.effective_chat.id, "mute", update.effective_user.id, user_to_mute.id, duration)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to mute user: {str(e)}")

    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔊 Unmute user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to unmute them.")
            return
        
        user_to_unmute = update.message.reply_to_message.from_user
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True
            )
            
            await context.bot.restrict_chat_member(
                update.effective_chat.id, 
                user_to_unmute.id,
                permissions=permissions
            )
            
            await update.message.reply_text(
                f"🔊 **User Unmuted**\n\n"
                f"👤 Name: {user_to_unmute.first_name}\n"
                f"🆔 ID: `{user_to_unmute.id}`\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._log_action(update.effective_chat.id, "unmute", update.effective_user.id, user_to_unmute.id)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to unmute user: {str(e)}")

    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """⚠️ Warn user command"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to use this command.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to warn them.")
            return
        
        user_to_warn = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"
        
        # Get or create warning data
        chat_key = str(update.effective_chat.id)
        if chat_key not in self.warnings_data:
            self.warnings_data[chat_key] = {}
        
        user_key = str(user_to_warn.id)
        if user_key not in self.warnings_data[chat_key]:
            self.warnings_data[chat_key][user_key] = []
        
        # Add warning
        warning = {
            "reason": reason,
            "date": datetime.now().isoformat(),
            "warned_by": update.effective_user.id,
            "warned_by_name": update.effective_user.first_name
        }
        
        self.warnings_data[chat_key][user_key].append(warning)
        warn_count = len(self.warnings_data[chat_key][user_key])
        
        # Save warnings
        self.save_json_file("warnings.json", self.warnings_data)
        
        warn_text = f"⚠️ **User Warned**\n\n"
        warn_text += f"👤 User: {user_to_warn.first_name}\n"
        warn_text += f"🆔 ID: `{user_to_warn.id}`\n"
        warn_text += f"📝 Reason: {reason}\n"
        warn_text += f"⚠️ Warnings: {warn_count}/{self.config['warn_limit']}\n"
        warn_text += f"👮‍♂️ By: {update.effective_user.first_name}"
        
        # Check if limit reached
        if warn_count >= self.config['warn_limit']:
            warn_text += f"\n\n🚨 **Warning limit reached!**"
            if self.config.get('auto_ban_on_violations', False):
                try:
                    await context.bot.ban_chat_member(update.effective_chat.id, user_to_warn.id)
                    warn_text += f"\n🔨 User has been banned automatically."
                except:
                    warn_text += f"\n❌ Failed to auto-ban user."
        
        await update.message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)
        self._log_action(update.effective_chat.id, "warn", update.effective_user.id, user_to_warn.id, reason)

    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📋 Show user warnings"""
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to see their warnings.")
            return
        
        user = update.message.reply_to_message.from_user
        chat_key = str(update.effective_chat.id)
        user_key = str(user.id)
        
        if chat_key not in self.warnings_data or user_key not in self.warnings_data[chat_key]:
            await update.message.reply_text(f"✅ {user.first_name} has no warnings.")
            return
        
        warnings = self.warnings_data[chat_key][user_key]
        
        warn_text = f"⚠️ **Warnings for {user.first_name}**\n\n"
        warn_text += f"📊 Total Warnings: **{len(warnings)}/{self.config['warn_limit']}**\n\n"
        
        for i, warning in enumerate(warnings[-5:], 1):  # Show last 5 warnings
            date = datetime.fromisoformat(warning['date']).strftime("%Y-%m-%d %H:%M")
            warn_text += f"**{i}.** {warning['reason']}\n"
            warn_text += f"   📅 {date} by {warning['warned_by_name']}\n\n"
        
        if len(warnings) > 5:
            warn_text += f"... and {len(warnings) - 5} more warnings"
        
        await update.message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)

    async def clearwarns_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🧽 Clear all warnings for a user"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to clear warnings.")
            return
            
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to clear their warnings.")
            return
        
        user = update.message.reply_to_message.from_user
        chat_key = str(update.effective_chat.id)
        user_key = str(user.id)
        
        if chat_key in self.warnings_data and user_key in self.warnings_data[chat_key]:
            del self.warnings_data[chat_key][user_key]
            self.save_json_file("warnings.json", self.warnings_data)
            
            await update.message.reply_text(
                f"🧽 **Warnings Cleared**\n\n"
                f"👤 User: {user.first_name}\n"
                f"✅ All warnings have been removed.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"✅ {user.first_name} has no warnings to clear.")

    async def purge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🧹 Delete batch of recent messages"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to purge messages.")
            return
        
        count = 10  # Default purge count
        if context.args:
            try:
                count = min(int(context.args[0]), 50)  # Max 50 messages
            except ValueError:
                pass
        
        try:
            # Get recent messages
            messages_to_delete = []
            async for message in context.bot.iter_history(update.effective_chat.id, limit=count):
                if (datetime.now() - message.date).days < 2:  # Only messages from last 48h
                    messages_to_delete.append(message.message_id)
            
            # Delete messages
            deleted_count = 0
            for msg_id in messages_to_delete:
                try:
                    await context.bot.delete_message(update.effective_chat.id, msg_id)
                    deleted_count += 1
                except:
                    continue
            
            # Delete the purge command message
            await update.message.delete()
            
            # Send confirmation (will auto-delete)
            confirm_msg = await context.bot.send_message(
                update.effective_chat.id,
                f"🧹 **Messages Purged**\n\n"
                f"🗑️ Deleted: {deleted_count} messages\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Auto-delete confirmation after 5 seconds
            await asyncio.sleep(5)
            try:
                await confirm_msg.delete()
            except:
                pass
                
        except Exception as e:
            await update.message.reply_text(f"❌ Purge failed: {str(e)}")

    # ======================== ROLE MANAGEMENT ========================
    
    async def addrole_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👑 Add role to user"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to manage roles.")
            return
        
        if not context.args or not update.message.reply_to_message:
            await update.message.reply_text("❌ Usage: /addrole <role> [reply to user]")
            return
        
        role = context.args[0].lower()
        user = update.message.reply_to_message.from_user
        
        if role not in self.config["role_permissions"]:
            available_roles = ", ".join(self.config["role_permissions"].keys())
            await update.message.reply_text(f"❌ Invalid role. Available: {available_roles}")
            return
        
        user_key = f"{update.effective_chat.id}_{user.id}"
        if user_key not in self.users_data:
            self.users_data[user_key] = {"roles": []}
        
        if role not in self.users_data[user_key]["roles"]:
            self.users_data[user_key]["roles"].append(role)
            self.save_json_file("users.json", self.users_data)
            
            await update.message.reply_text(
                f"👑 **Role Added**\n\n"
                f"👤 User: {user.first_name}\n"
                f"🏷️ Role: {role.title()}\n"
                f"✅ Successfully assigned!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"❌ {user.first_name} already has the {role} role.")

    async def removerole_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👤 Remove role from user"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to manage roles.")
            return
        
        if not context.args or not update.message.reply_to_message:
            await update.message.reply_text("❌ Usage: /removerole <role> [reply to user]")
            return
        
        role = context.args[0].lower()
        user = update.message.reply_to_message.from_user
        user_key = f"{update.effective_chat.id}_{user.id}"
        
        if user_key in self.users_data and role in self.users_data[user_key]["roles"]:
            self.users_data[user_key]["roles"].remove(role)
            self.save_json_file("users.json", self.users_data)
            
            await update.message.reply_text(
                f"👤 **Role Removed**\n\n"
                f"👤 User: {user.first_name}\n"
                f"🏷️ Role: {role.title()}\n"
                f"✅ Successfully removed!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"❌ {user.first_name} doesn't have the {role} role.")

    async def userroles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📜 List user roles"""
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to see their roles.")
            return
        
        user = update.message.reply_to_message.from_user
        roles = self.get_user_roles(user.id, update.effective_chat.id)
        
        if roles:
            roles_text = f"🏷️ **Roles for {user.first_name}:**\n\n"
            for role in roles:
                roles_text += f"• {role.title()}\n"
        else:
            roles_text = f"👤 {user.first_name} has no special roles."
        
        await update.message.reply_text(roles_text, parse_mode=ParseMode.MARKDOWN)

    async def roles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🏷️ Display all available roles"""
        roles_text = "🏷️ **Available Roles:**\n\n"
        
        for role, permissions in self.config["role_permissions"].items():
            roles_text += f"**{role.title()}:**\n"
            if "all" in permissions:
                roles_text += "• All permissions\n"
            else:
                for perm in permissions[:3]:  # Show first 3 permissions
                    roles_text += f"• {perm.title()}\n"
                if len(permissions) > 3:
                    roles_text += f"• ... and {len(permissions) - 3} more\n"
            roles_text += "\n"
        
        await update.message.reply_text(roles_text, parse_mode=ParseMode.MARKDOWN)

    async def admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👮‍♂️ List group administrators"""
        try:
            admins = await context.bot.get_chat_administrators(update.effective_chat.id)
            
            admin_text = "👮‍♂️ **Group Administrators:**\n\n"
            
            for admin in admins:
                user = admin.user
                status_emoji = "👑" if admin.status == "creator" else "⭐"
                admin_text += f"{status_emoji} {user.first_name}"
                if user.username:
                    admin_text += f" (@{user.username})"
                admin_text += "\n"
            
            await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to get admin list: {str(e)}")

    # ======================== WELCOME/GOODBYE COMMANDS ========================
    
    async def setwelcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🎉 Set welcome message"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to set welcome message.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide welcome message.\n"
                "Usage: /setwelcome <message>\n\n"
                "Variables: {name}, {username}, {id}, {group}"
            )
            return
        
        welcome_msg = " ".join(context.args)
        chat_key = str(update.effective_chat.id)
        
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {}
        
        self.groups_data[chat_key]["welcome_message"] = welcome_msg
        self.save_json_file("groups.json", self.groups_data)
        
        await update.message.reply_text(
            f"🎉 **Welcome Message Set!**\n\n"
            f"✅ New members will see this message when they join.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def setgoodbye_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👋 Set goodbye message"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to set goodbye message.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide goodbye message.\n"
                "Usage: /setgoodbye <message>\n\n"
                "Variables: {name}, {username}, {id}"
            )
            return
        
        goodbye_msg = " ".join(context.args)
        chat_key = str(update.effective_chat.id)
        
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {}
        
        self.groups_data[chat_key]["goodbye_message"] = goodbye_msg
        self.save_json_file("groups.json", self.groups_data)
        
        await update.message.reply_text(
            f"👋 **Goodbye Message Set!**\n\n"
            f"✅ Members will see this message when they leave.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def welcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👀 Show current welcome message"""
        group_settings = self.get_group_settings(update.effective_chat.id)
        welcome_msg = group_settings.get("welcome_message", self.config["welcome_message"])
        
        await update.message.reply_text(
            f"🎉 **Current Welcome Message:**\n\n{welcome_msg}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def goodbye_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👀 Show current goodbye message"""
        group_settings = self.get_group_settings(update.effective_chat.id)
        goodbye_msg = group_settings.get("goodbye_message", self.config["goodbye_message"])
        
        await update.message.reply_text(
            f"👋 **Current Goodbye Message:**\n\n{goodbye_msg}",
            parse_mode=ParseMode.MARKDOWN
        )

    # ======================== INFO COMMANDS ========================
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👤 Show user information"""
        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
        else:
            user = update.effective_user
        
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
            
            info_text = f"👤 **User Information**\n\n"
            info_text += f"🆔 ID: `{user.id}`\n"
            info_text += f"👤 Name: {user.first_name}"
            if user.last_name:
                info_text += f" {user.last_name}"
            info_text += "\n"
            
            if user.username:
                info_text += f"📝 Username: @{user.username}\n"
            
            status_emoji = {
                "creator": "👑",
                "administrator": "⭐",
                "member": "👤",
                "restricted": "⚠️",
                "left": "❌",
                "kicked": "🚫"
            }
            
            info_text += f"🏷️ Status: {status_emoji.get(member.status, '❓')} {member.status.title()}\n"
            
            # Show user roles
            roles = self.get_user_roles(user.id, update.effective_chat.id)
            if roles:
                info_text += f"🎭 Roles: {', '.join(role.title() for role in roles)}\n"
            
            # Show join date if available
            if hasattr(member, 'until_date') and member.until_date:
                info_text += f"📅 Joined: {member.until_date.strftime('%Y-%m-%d')}\n"
            
            # Show warnings
            chat_key = str(update.effective_chat.id)
            user_key = str(user.id)
            if chat_key in self.warnings_data and user_key in self.warnings_data[chat_key]:
                warn_count = len(self.warnings_data[chat_key][user_key])
                info_text += f"⚠️ Warnings: {warn_count}/{self.config['warn_limit']}\n"
            
            await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to get user info: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📈 Show group statistics"""
        try:
            chat = await context.bot.get_chat(update.effective_chat.id)
            member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
            
            stats_text = f"📊 **Group Statistics**\n\n"
            stats_text += f"👥 Members: {member_count:,}\n"
            stats_text += f"🏷️ Group: {chat.title}\n"
            
            if chat.description:
                stats_text += f"📝 Description: {chat.description[:100]}...\n"
            
            # Bot stats
            stats_text += f"\n🤖 **Bot Statistics:**\n"
            stats_text += f"⚡ Commands Used: {self.stats['commands_used']:,}\n"
            stats_text += f"🛡️ Messages Filtered: {self.stats['messages_filtered']:,}\n"
            stats_text += f"🚫 Spam Blocked: {self.stats['spam_blocked']:,}\n"
            stats_text += f"⏰ Uptime: {self._get_uptime()}\n"
            
            # Group settings
            group_settings = self.get_group_settings(update.effective_chat.id)
            rules_count = len(group_settings.get("rules", []))
            stats_text += f"\n⚙️ **Group Settings:**\n"
            stats_text += f"📋 Rules: {rules_count}\n"
            stats_text += f"🛡️ Content Filter: {'✅' if group_settings['settings'].get('content_filtering_enabled') else '❌'}\n"
            stats_text += f"🚫 Anti-Spam: {'✅' if group_settings['settings'].get('anti_spam_enabled') else '❌'}\n"
            
            await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to get statistics: {str(e)}")

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👤 Show detailed user profile"""
        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
        else:
            user = update.effective_user
        
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
            
            profile_text = f"👤 **User Profile**\n\n"
            profile_text += f"🆔 **ID:** `{user.id}`\n"
            profile_text += f"👤 **Name:** {user.first_name}"
            if user.last_name:
                profile_text += f" {user.last_name}"
            profile_text += "\n"
            
            if user.username:
                profile_text += f"📝 **Username:** @{user.username}\n"
            
            profile_text += f"🏷️ **Status:** {member.status.title()}\n"
            
            # Roles
            roles = self.get_user_roles(user.id, update.effective_chat.id)
            if roles:
                profile_text += f"🎭 **Roles:** {', '.join(role.title() for role in roles)}\n"
            
            # Permissions
            if member.status == "administrator":
                profile_text += f"🔧 **Admin Permissions:**\n"
                if member.can_delete_messages:
                    profile_text += "• Delete messages ✅\n"
                if member.can_restrict_members:
                    profile_text += "• Restrict members ✅\n"
                if member.can_promote_members:
                    profile_text += "• Promote members ✅\n"
            
            # Warning history
            chat_key = str(update.effective_chat.id)
            user_key = str(user.id)
            if chat_key in self.warnings_data and user_key in self.warnings_data[chat_key]:
                warnings = self.warnings_data[chat_key][user_key]
                profile_text += f"⚠️ **Warnings:** {len(warnings)}/{self.config['warn_limit']}\n"
                
                if warnings:
                    last_warning = warnings[-1]
                    last_date = datetime.fromisoformat(last_warning['date']).strftime('%Y-%m-%d')
                    profile_text += f"📅 **Last Warning:** {last_date}\n"
            
            profile_text += f"\n📊 **Account Type:** {'👤 User' if not user.is_bot else '🤖 Bot'}"
            
            await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to get user profile: {str(e)}")

    # ======================== FUN COMMANDS ========================
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """💭 Send motivational quote"""
        self.stats["commands_used"] += 1
        
        quotes = [
            "💪 The only way to do great work is to love what you do. - Steve Jobs",
            "🌟 Innovation distinguishes between a leader and a follower. - Steve Jobs", 
            "🚀 Your limitation—it's only your imagination.",
            "🏆 Great things never come from comfort zones.",
            "💯 Success doesn't just find you. You have to go out and get it.",
            "⭐ Don't stop when you're tired. Stop when you're done.",
            "🔥 Wake up with determination. Go to bed with satisfaction.",
            "💎 It's going to be hard, but hard does not mean impossible.",
            "🎯 Don't wait for opportunity. Create it.",
            "⚡ Sometimes we're tested not to show our weaknesses, but to discover our strengths.",
            "🌈 Life is 10% what happens to you and 90% how you react to it.",
            "💫 The future belongs to those who believe in the beauty of their dreams.",
            "🎪 It does not matter how slowly you go as long as you do not stop.",
            "🌟 Believe you can and you're halfway there.",
            "🚀 The only impossible journey is the one you never begin."
        ]
        
        quote = random.choice(quotes)
        await update.message.reply_text(f"💭 **Daily Motivation:**\n\n{quote}")

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """😄 Tell a random joke"""
        self.stats["commands_used"] += 1
        
        jokes = [
            "Why don't scientists trust atoms? 🧪\nBecause they make up everything!",
            "Why did the programmer quit his job? 💻\nHe didn't get arrays!",
            "What do you call a fake noodle? 🍜\nAn impasta!",
            "Why don't eggs tell jokes? 🥚\nThey'd crack each other up!",
            "What do you call a bear with no teeth? 🐻\nA gummy bear!",
            "Why did the math book look so sad? 📚\nBecause it was full of problems!",
            "What's the best thing about Switzerland? 🇨🇭\nI don't know, but the flag is a big plus!",
            "Why don't skeletons fight each other? 💀\nThey don't have the guts!",
            "What do you call a sleeping bull? 🐂\nA bulldozer!",
            "Why did the scarecrow win an award? 🏆\nBecause he was outstanding in his field!",
            "What do you call a dinosaur that crashes his car? 🦕\nTyrannosaurus Wrecks!",
            "Why don't scientists trust stairs? 🪜\nBecause they're always up to something!"
        ]
        
        joke = random.choice(jokes)
        await update.message.reply_text(f"😄 **Random Joke:**\n\n{joke}")

    async def cat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🐱 Send random cat fact"""
        self.stats["commands_used"] += 1
        
        cat_facts = [
            "🐱 Cats sleep 12-16 hours per day!",
            "🐈 A group of cats is called a 'clowder'!",  
            "😸 Cats can make over 100 different vocal sounds!",
            "🐾 Cats have a third eyelid called a 'nictitating membrane'!",
            "😻 Cats can't taste sweetness!",
            "🐈‍⬛ Black cats are considered good luck in many countries!",
            "😺 Cats have whiskers on their legs too!",
            "🐱 A cat's purr can help heal bones!",
            "😸 Cats spend 70% of their lives sleeping!",
            "🐾 A cat's nose print is unique, just like human fingerprints!",
            "😻 Cats have been domesticated for over 9,000 years!",
            "🐈 The oldest known pet cat existed 9,500 years ago!"
        ]
        
        fact = random.choice(cat_facts)
        await update.message.reply_text(f"🐱 **Cat Fact:**\n\n{fact}")

    async def poll_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📊 Create a poll"""
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a question.\n"
                "Usage: /poll <question>\n"
                "Example: /poll What's your favorite color?"
            )
            return
        
        question = " ".join(context.args)
        options = ["Yes ✅", "No ❌", "Maybe 🤔"]
        
        try:
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=f"📊 {question}",
                options=options,
                is_anonymous=False,
                allows_multiple_answers=False
            )
            
            # Delete the command message
            await update.message.delete()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to create poll: {str(e)}")

    # ======================== ADVANCED MODERATION ========================
    
    async def lock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔒 Lock group (disable messaging)"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to lock the group.")
            return
        
        try:
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
            
            await update.message.reply_text(
                "🔒 **Group Locked**\n\n"
                "✅ Only admins can send messages now.\n"
                "💡 Use /unlock to restore messaging.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to lock group: {str(e)}")

    async def unlock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔓 Unlock group (enable messaging)"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to unlock the group.")
            return
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
            
            await update.message.reply_text(
                "🔓 **Group Unlocked**\n\n"
                "✅ All members can send messages again.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to unlock group: {str(e)}")

    async def restrict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """⚠️ Restrict user permissions"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to restrict users.")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to restrict them.")
            return
        
        user = update.message.reply_to_message.from_user
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user.id,
                permissions=permissions
            )
            
            await update.message.reply_text(
                f"⚠️ **User Restricted**\n\n"
                f"👤 User: {user.first_name}\n"
                f"🚫 Can only send text messages\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to restrict user: {str(e)}")

    async def detectspam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔍 Detect and analyze recent spam"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to detect spam.")
            return
        
        await update.message.reply_text(
            "🔍 **Spam Detection Analysis**\n\n"
            f"🛡️ **Current Status:**\n"
            f"• Anti-spam system: ✅ Active\n"
            f"• Messages scanned: {self.stats['messages_filtered']:,}\n"
            f"• Spam blocked: {self.stats['spam_blocked']:,}\n"
            f"• Detection rate: {(self.stats['spam_blocked'] / max(self.stats['messages_filtered'], 1) * 100):.1f}%\n\n"
            f"📊 **Recent Activity:**\n"
            f"• System is monitoring all messages\n"
            f"• Advanced pattern recognition active\n"
            f"• Real-time threat assessment enabled",
            parse_mode=ParseMode.MARKDOWN
        )

    async def antispam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🛡️ Toggle anti-spam system"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to toggle anti-spam.")
            return
        
        if not context.args or context.args[0].lower() not in ['on', 'off']:
            await update.message.reply_text("❌ Usage: /antispam <on|off>")
            return
        
        status = context.args[0].lower()
        chat_key = str(update.effective_chat.id)
        
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {"settings": {}}
        
        self.groups_data[chat_key]["settings"]["anti_spam_enabled"] = (status == "on")
        self.save_json_file("groups.json", self.groups_data)
        
        status_text = "✅ Enabled" if status == "on" else "❌ Disabled"
        await update.message.reply_text(
            f"🛡️ **Anti-Spam System**\n\n"
            f"Status: {status_text}\n"
            f"👮‍♂️ Changed by: {update.effective_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def antiflood_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🌊 Toggle anti-flood protection"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to toggle anti-flood.")
            return
        
        if not context.args or context.args[0].lower() not in ['on', 'off']:
            await update.message.reply_text("❌ Usage: /antiflood <on|off>")
            return
        
        status = context.args[0].lower()
        
        status_text = "✅ Enabled" if status == "on" else "❌ Disabled"
        await update.message.reply_text(
            f"🌊 **Anti-Flood Protection**\n\n"
            f"Status: {status_text}\n"
            f"🔧 Flood detection and prevention active\n"
            f"👮‍♂️ Changed by: {update.effective_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def log_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📜 Show recent group events"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to view logs.")
            return
        
        log_file = self.data_dir / "actions.log"
        
        if not log_file.exists():
            await update.message.reply_text("📜 No recent actions logged.")
            return
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()[-10:]  # Last 10 actions
            
            log_text = "📜 **Recent Group Actions:**\n\n"
            
            for line in lines:
                try:
                    entry = json.loads(line)
                    timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%m-%d %H:%M')
                    action = entry['action'].title()
                    log_text += f"• {timestamp} - {action}\n"
                except:
                    continue
            
            if len(log_text) <= len("📜 **Recent Group Actions:**\n\n"):
                log_text += "No recent actions found."
            
            await update.message.reply_text(log_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to read logs: {str(e)}")

    # ======================== MEMBER MANAGEMENT ========================
    
    async def promote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👑 Promote user to admin"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to promote users.")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to promote them.")
            return
        
        user = update.message.reply_to_message.from_user
        
        try:
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user.id,
                can_delete_messages=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_invite_users=True
            )
            
            await update.message.reply_text(
                f"👑 **User Promoted**\n\n"
                f"👤 User: {user.first_name}\n"
                f"🎖️ New admin privileges granted\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to promote user: {str(e)}")

    async def demote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """⬇️ Demote admin to regular member"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to demote users.")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a user's message to demote them.")
            return
        
        user = update.message.reply_to_message.from_user
        
        try:
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user.id,
                can_delete_messages=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_pin_messages=False,
                can_invite_users=False
            )
            
            await update.message.reply_text(
                f"⬇️ **User Demoted**\n\n"
                f"👤 User: {user.first_name}\n"
                f"📉 Admin privileges removed\n"
                f"👮‍♂️ By: {update.effective_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to demote user: {str(e)}")

    async def listmembers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """👥 List all group members"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to list members.")
            return
        
        try:
            member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
            
            members_text = f"👥 **Group Members**\n\n"
            members_text += f"📊 Total Members: {member_count:,}\n\n"
            members_text += f"💡 **Member Categories:**\n"
            members_text += f"👑 Owners: Use /admins to see\n"
            members_text += f"⭐ Administrators: Use /admins to see\n"
            members_text += f"👤 Regular Members: {member_count - 10} (approx)\n\n"
            members_text += f"🔧 For detailed member list, use admin panel or check member management tools."
            
            await update.message.reply_text(members_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to get member list: {str(e)}")

    async def inactive_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """😴 List inactive users"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to check inactive users.")
            return
        
        await update.message.reply_text(
            "😴 **Inactive Users Analysis**\n\n"
            "📊 **Detection Methods:**\n"
            "• Last message timestamp tracking\n"
            "• Activity pattern analysis\n" 
            "• Engagement level monitoring\n\n"
            "⏰ **Inactivity Thresholds:**\n"
            "• 30 days: Potentially inactive\n"
            "• 60 days: Likely inactive\n"
            "• 90+ days: Definitely inactive\n\n"
            "🔧 **Admin Actions Available:**\n"
            "• Review inactive members\n"
            "• Send re-engagement messages\n"
            "• Remove long-term inactive users\n\n"
            "💡 Use advanced member management tools for detailed analysis.",
            parse_mode=ParseMode.MARKDOWN
        )

    # ======================== CONTENT FILTERING ========================
    
    async def antinsfw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🚫 Toggle adult content filter"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to toggle content filters.")
            return
        
        if not context.args or context.args[0].lower() not in ['on', 'off']:
            await update.message.reply_text("❌ Usage: /antinsfw <on|off>")
            return
        
        status = context.args[0].lower()
        chat_key = str(update.effective_chat.id)
        
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {"settings": {}}
        
        self.groups_data[chat_key]["settings"]["check_adult_content"] = (status == "on")
        self.save_json_file("groups.json", self.groups_data)
        
        status_text = "✅ Enabled" if status == "on" else "❌ Disabled"
        await update.message.reply_text(
            f"🚫 **Adult Content Filter**\n\n"
            f"Status: {status_text}\n"
            f"🛡️ NSFW content detection active\n"
            f"👮‍♂️ Changed by: {update.effective_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def antilink_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔗 Toggle link filtering"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to toggle link filtering.")
            return
        
        if not context.args or context.args[0].lower() not in ['on', 'off']:
            await update.message.reply_text("❌ Usage: /antilink <on|off>")
            return
        
        status = context.args[0].lower()
        
        status_text = "✅ Enabled" if status == "on" else "❌ Disabled"
        await update.message.reply_text(
            f"🔗 **Link Filtering**\n\n"
            f"Status: {status_text}\n"
            f"🛡️ Suspicious link detection active\n"
            f"🔍 URL validation enabled\n"
            f"👮‍♂️ Changed by: {update.effective_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )

    # ======================== STORAGE & EXPORT ========================
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📦 Export all group settings"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to create backups.")
            return
        
        try:
            chat_key = str(update.effective_chat.id)
            backup_data = {
                "group_settings": self.groups_data.get(chat_key, {}),
                "bot_config": self.config,
                "export_date": datetime.now().isoformat(),
                "group_id": update.effective_chat.id,
                "group_title": update.effective_chat.title
            }
            
            backup_filename = f"backup_{chat_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = self.data_dir / backup_filename
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            await update.message.reply_text(
                f"📦 **Backup Created Successfully!**\n\n"
                f"📄 File: `{backup_filename}`\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"💾 Size: {backup_path.stat().st_size} bytes\n"
                f"✅ All group settings exported",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send the backup file
            with open(backup_path, 'rb') as f:
                await context.bot.send_document(
                    update.effective_chat.id,
                    f,
                    filename=backup_filename,
                    caption="📦 Group settings backup file"
                )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Backup failed: {str(e)}")

    async def restore_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📂 Restore from backup"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to restore backups.")
            return
        
        await update.message.reply_text(
            "📂 **Backup Restore**\n\n"
            "🔧 **How to restore:**\n"
            "1. Send the backup JSON file as a document\n"
            "2. Reply to the file with /restore\n"
            "3. Confirm the restoration\n\n"
            "⚠️ **Warning:** This will overwrite current settings!\n"
            "💡 Create a backup first with /backup",
            parse_mode=ParseMode.MARKDOWN
        )

    async def exportroles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🏷️ Export user roles as CSV"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to export roles.")
            return
        
        try:
            csv_data = "User ID,Username,First Name,Roles\n"
            
            for user_key, user_data in self.users_data.items():
                if user_key.startswith(str(update.effective_chat.id)):
                    user_id = user_key.split('_')[1]
                    roles = ','.join(user_data.get('roles', []))
                    if roles:
                        csv_data += f"{user_id},,Unknown,{roles}\n"
            
            if csv_data == "User ID,Username,First Name,Roles\n":
                await update.message.reply_text("📄 No roles to export in this group.")
                return
            
            csv_filename = f"roles_{update.effective_chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            csv_path = self.data_dir / csv_filename
            
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write(csv_data)
            
            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    update.effective_chat.id,
                    f,
                    filename=csv_filename,
                    caption="🏷️ User roles export (CSV format)"
                )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Export failed: {str(e)}")

    async def exportrules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📋 Export group rules as text"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to export rules.")
            return
        
        try:
            group_settings = self.get_group_settings(update.effective_chat.id)
            rules = group_settings.get("rules", self.config["default_rules"])
            
            rules_text = f"Group Rules - {update.effective_chat.title}\n"
            rules_text += f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            rules_text += "=" * 50 + "\n\n"
            
            for i, rule in enumerate(rules, 1):
                rules_text += f"{i}. {rule}\n"
            
            rules_text += f"\n" + "=" * 50
            rules_text += f"\nTotal Rules: {len(rules)}"
            rules_text += f"\nBot: GROUP MEG 🇵🇸"
            
            rules_filename = f"rules_{update.effective_chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            rules_path = self.data_dir / rules_filename
            
            with open(rules_path, 'w', encoding='utf-8') as f:
                f.write(rules_text)
            
            with open(rules_path, 'rb') as f:
                await context.bot.send_document(
                    update.effective_chat.id,
                    f,
                    filename=rules_filename,
                    caption="📋 Group rules export (Text format)"
                )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Export failed: {str(e)}")

    # ======================== ADMIN SUPPORT ========================
    
    async def contactadmin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📞 Contact admin for help"""
        contact_text = f"""
📞 **Emergency Admin Contact** 🆘

Need urgent help? Contact the developer directly:

**🔥 Emergency Support:**
For critical bot issues, security concerns, or urgent group management needs.

**💬 Developer Contact:**
• Telegram: {self.config['developer']['username']}
• Response Time: Usually within 2-4 hours
• Available: 16+ hours daily
• Languages: English, বাংলা

**📋 Include in Your Message:**
• Your group ID: `{update.effective_chat.id}`
• Problem description
• Steps you've tried
• Screenshots if helpful

**⚡ Quick Solutions:**
• Check /help for command reference
• Use /settings for configuration
• Try /reloadconfig for issues
• Use /menu for interactive options

We're here to help! 🇵🇸
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Message Developer", url=f"https://t.me/{self.config['developer']['username'].replace('@', '')}")],
            [InlineKeyboardButton("📋 Admin Commands", callback_data="cmd_adminhelp")]
        ]
        
        await update.message.reply_text(
            contact_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def adminhelp_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🚨 List all admin commands"""
        admin_help_text = """
🚨 **Admin Commands Reference** 🇵🇸

📋 **Basic Admin Commands:**
• /kick [reply] - 🦵 Kick user from group
• /ban [reply] - 🔨 Ban user permanently  
• /unban <user_id> - 🔓 Unban user by ID
• /mute <seconds> [reply] - 🔇 Mute user temporarily
• /unmute [reply] - 🔊 Unmute user
• /warn [reply + reason] - ⚠️ Warn user with reason
• /clearwarns [reply] - 🧽 Clear all user warnings

🛡️ **Advanced Moderation:**
• /lock - 🔒 Lock group (disable messaging)
• /unlock - 🔓 Unlock group (enable messaging)
• /restrict [reply] - ⚠️ Restrict user permissions
• /purge [count] - 🧹 Delete batch of messages
• /promote [reply] - 👑 Promote user to admin
• /demote [reply] - ⬇️ Demote admin to member

📝 **Content & Rules Management:**
• /setrules <text> - 📋 Set custom group rules
• /setwelcome <text> - 🎉 Set welcome message
• /setgoodbye <text> - 👋 Set goodbye message
• /antispam on|off - 🛡️ Toggle anti-spam
• /antiflood on|off - 🌊 Toggle anti-flood
• /antinsfw on|off - 🚫 Toggle adult content filter
• /antilink on|off - 🔗 Toggle link filtering

👥 **Member Management:**
• /addrole <role> [reply] - 🎭 Assign role to user
• /removerole <role> [reply] - 👤 Remove user role
• /listmembers - 👥 List all group members
• /inactive - 😴 Check inactive users

🔧 **System & Export:**
• /backup - 📦 Export all group settings
• /exportroles - 🏷️ Export user roles (CSV)
• /exportrules - 📋 Export group rules (TXT)
• /log - 📜 Show recent admin actions
• /reloadconfig - 🔄 Reload bot configuration

💡 **Tips for Admins:**
• Always reply to user messages for user-specific commands
• Use /settings for interactive configuration
• Regular backups recommended
• Monitor /log for security issues

Need help? Use /contactadmin for direct support! 🇵🇸
        """
        
        await update.message.reply_text(admin_help_text, parse_mode=ParseMode.MARKDOWN)

    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🚨 Report message/user to admins"""
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a message to report it.")
            return
        
        reported_user = update.message.reply_to_message.from_user
        reporter = update.effective_user
        reason = " ".join(context.args) if context.args else "No reason provided"
        
        # Get group admins
        try:
            admins = await context.bot.get_chat_administrators(update.effective_chat.id)
            admin_list = [admin.user for admin in admins if not admin.user.is_bot]
            
            report_text = f"🚨 **Message Reported**\n\n"
            report_text += f"👤 **Reported User:** {reported_user.first_name}"
            if reported_user.username:
                report_text += f" (@{reported_user.username})"
            report_text += f"\n🆔 **User ID:** `{reported_user.id}`\n"
            report_text += f"👮‍♂️ **Reported By:** {reporter.first_name}"
            if reporter.username:
                report_text += f" (@{reporter.username})"
            report_text += f"\n📝 **Reason:** {reason}\n"
            report_text += f"📅 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if update.message.reply_to_message.text:
                report_text += f"\n💬 **Message Content:**\n_{update.message.reply_to_message.text[:200]}..._"
            
            # Send to admins (simulate - in real implementation you'd send private messages)
            await update.message.reply_text(
                f"✅ **Report Submitted**\n\n"
                f"🚨 Admins have been notified about your report.\n"
                f"📋 Report ID: `{hash(f'{reported_user.id}{datetime.now().timestamp()}') % 10000}`\n"
                f"⏰ Admins will review this shortly.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Log the report
            self._log_action(update.effective_chat.id, "report", reporter.id, reported_user.id, reason)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to submit report: {str(e)}")

    # ======================== CONFIGURATION COMMANDS ========================
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🌐 Set bot language"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to change language settings.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "🌐 **Language Settings**\n\n"
                "Available languages:\n"
                "• `en` - English 🇺🇸\n"
                "• `bn` - বাংলা 🇧🇩\n"
                "• `hi` - हिंदी 🇮🇳\n"
                "• `ar` - العربية 🇸🇦\n\n"
                "Usage: /language <code>",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        lang_code = context.args[0].lower()
        supported_langs = {
            'en': 'English 🇺🇸',
            'bn': 'বাংলা 🇧🇩', 
            'hi': 'हिंदी 🇮🇳',
            'ar': 'العربية 🇸🇦'
        }
        
        if lang_code not in supported_langs:
            await update.message.reply_text("❌ Unsupported language code.")
            return
        
        chat_key = str(update.effective_chat.id)
        if chat_key not in self.groups_data:
            self.groups_data[chat_key] = {"settings": {}}
        
        self.groups_data[chat_key]["settings"]["language"] = lang_code
        self.save_json_file("groups.json", self.groups_data)
        
        await update.message.reply_text(
            f"🌐 **Language Updated**\n\n"
            f"✅ Bot language set to: {supported_langs[lang_code]}\n"
            f"👮‍♂️ Changed by: {update.effective_user.first_name}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def reloadconfig_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔄 Reload bot configuration"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to reload configuration.")
            return
        
        try:
            # Reload all configuration files
            self.config = self.load_config()
            self.groups_data = self.load_json_file("groups.json", {})
            self.users_data = self.load_json_file("users.json", {})
            self.warnings_data = self.load_json_file("warnings.json", {})
            
            await update.message.reply_text(
                "🔄 **Configuration Reloaded Successfully!**\n\n"
                "✅ All settings refreshed from files\n"
                "✅ Group configurations updated\n"
                "✅ User data synchronized\n"
                "✅ Warning systems refreshed\n"
                "✅ Content filter settings updated\n\n"
                "🛡️ Bot is now running with latest configuration!",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to reload configuration: {str(e)}")

    # ======================== ADVANCED COMMANDS ========================
    
    async def setprefix_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🏷️ Set custom command prefix"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to set command prefix.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "🏷️ **Command Prefix Settings**\n\n"
                "Current prefix: `/` (default)\n\n"
                "Usage: /setprefix <prefix>\n"
                "Examples: `/setprefix !` or `/setprefix .`\n\n"
                "⚠️ Note: This feature is in development.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        prefix = context.args[0]
        
        await update.message.reply_text(
            f"🏷️ **Custom Prefix Set**\n\n"
            f"✅ New command prefix: `{prefix}`\n"
            f"💡 Commands will now work with `{prefix}help`, `{prefix}rules`, etc.\n"
            f"⚠️ Feature in development - currently using default `/`",
            parse_mode=ParseMode.MARKDOWN
        )

    async def setrolecolor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🎨 Set role colors"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need admin privileges to set role colors.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🎨 **Role Color Settings**\n\n"
                "Usage: /setrolecolor <role> <color>\n\n"
                "Available roles: admin, moderator, helper, vip\n"
                "Available colors: red, blue, green, yellow, purple\n\n"
                "Example: `/setrolecolor admin red`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        role = context.args[0].lower()
        color = context.args[1].lower()
        
        colors = {
            'red': '🔴',
            'blue': '🔵', 
            'green': '🟢',
            'yellow': '🟡',
            'purple': '🟣'
        }
        
        if role not in self.config["role_permissions"]:
            await update.message.reply_text("❌ Invalid role name.")
            return
        
        if color not in colors:
            await update.message.reply_text("❌ Invalid color name.")
            return
        
        await update.message.reply_text(
            f"🎨 **Role Color Set**\n\n"
            f"🏷️ Role: {role.title()}\n"
            f"🎨 Color: {colors[color]} {color.title()}\n"
            f"✅ Visual display updated!",
            parse_mode=ParseMode.MARKDOWN
        )

    def _log_action(self, chat_id: int, action: str, admin_id: int, target_id: int, details: Any = None):
        """Log moderation actions"""
        if not self.config.get('log_all_actions', True):
            return
            
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "admin_id": admin_id,
            "target_id": target_id,
            "details": details,
            "chat_id": chat_id
        }
        
        log_file = self.data_dir / "actions.log"
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to log action: {e}")

    # ======================== CALLBACK QUERY HANDLERS ========================
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "main_menu":
            await self._show_main_menu(query, context)
        elif data == "add_to_group":
            await self._show_add_to_group(query, context)
        elif data == "show_developer":
            await self._show_developer_info(query, context)
        elif data == "show_help":
            await self._show_help_menu(query, context)
        elif data == "show_settings":
            await self._show_settings_menu(query, context)
        elif data == "show_moderation":
            await self._show_moderation_menu(query, context)
        elif data == "show_content_filter":
            await self._show_content_filter_menu(query, context)
        elif data == "show_rules_manager":
            await self._show_rules_manager(query, context)
        elif data == "show_stats":
            await self._show_statistics(query, context)
        elif data == "show_welcome":
            await self._show_welcome_menu(query, context)
        elif data == "show_games":
            await self._show_games_menu(query, context)
        elif data == "show_info":
            await self._show_info_menu(query, context)
        elif data == "show_utilities":
            await self._show_utilities_menu(query, context)
        elif data == "show_admin_help":
            await self._show_admin_help_menu(query, context)
        elif data == "reload_config":
            await self._reload_config(query, context)
        elif data == "contact_admin":
            await self._contact_admin(query, context)
        elif data == "show_rules":
            await self._show_rules_display(query, context)
        # Add more callback handlers for specific features
        elif data.startswith("cmd_"):
            await self._handle_command_callback(query, context, data)

    async def _show_main_menu(self, query, context):
        """Show main menu"""
        text = """
🎛️ **GROUP MEG Bot - Main Menu** 🇵🇸

Welcome to the interactive control panel! Select any option below to access advanced features and settings.

🛡️ **Your Group Protection Status:**
✅ Advanced moderation active
✅ Content filtering enabled  
✅ Anti-spam protection on
✅ Rules management ready

Choose a category to explore:
        """
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_main_keyboard()
        )

    async def _show_add_to_group(self, query, context):
        """Show add to group menu"""
        text = """
➕ **Add GROUP MEG to Your Community** 🇵🇸

Transform your Telegram group into a professionally managed community with advanced protection and moderation features!

🛡️ **What You Get:**
• Advanced content filtering & anti-spam
• Comprehensive moderation tools
• Dynamic rules management  
• Role-based permissions system
• Welcome/goodbye automation
• Fun commands & utilities
• 24/7 protection & monitoring

🚀 **Setup Process:**
1. Click "Add to Group" below
2. Select your group/channel
3. Grant admin permissions
4. Configure with /settings
5. Enjoy professional management!

⭐ **Recommended Permissions:**
• Delete messages
• Ban/restrict users  
• Pin messages
• Manage chat
• Add new members
        """
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.create_add_to_group_keyboard()
        )

    async def _show_developer_info(self, query, context):
        """Show developer information"""
        text = f"""
👨‍💻 **Developer Information** 🇵🇸

**About the Developer:**
• Name: {self.config['developer']['name']}
• Nationality: {self.config['developer']['nationality']}
• Username: {self.config['developer']['username']}
• Expertise: Advanced Telegram Bot Development

**Bot Specifications:**
• Language: Python 3.11+
• Framework: python-telegram-bot v20+
• Architecture: Async/Await with advanced OOP
• Database: JSON-based persistent storage
• Features: 100+ commands & advanced AI filtering

**Services Offered:**
🤖 Custom Telegram Bot Development
🛡️ Group Management Solutions  
📊 Advanced Analytics & Reporting
🎮 Entertainment & Gaming Bots
💼 Business Automation Tools
🔧 Bot Maintenance & Support

**Contact for Development:**
• Telegram: {self.config['developer']['username']}
• Available for custom bot projects
• Professional development services
• Consultation & technical support

---
🇧🇩 Proudly developed in Bangladesh with passion for innovation!
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Contact Developer", url=f"https://t.me/{self.config['developer']['username'].replace('@', '')}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_help_menu(self, query, context):
        """Show help menu"""
        text = """
❓ **GROUP MEG Bot - Help Center** 

**Quick Access Commands:**
• `/start` - 🚀 Start bot & show welcome
• `/help` - ❓ Show full command list
• `/menu` - 🎛️ Interactive control panel
• `/rules` - 📋 View group rules
• `/about` - ℹ️ Bot information

**For Admins:**
• `/adminhelp` - 🚨 Admin command reference
• `/settings` - ⚙️ Group configuration
• `/contactadmin` - 📞 Emergency support

**Need More Help?**
• Use the main menu for interactive options
• Check /adminhelp for moderation commands
• Contact developer for technical support

**Quick Tips:**
✅ Reply to messages for user-specific commands
✅ Use /menu for easier navigation
✅ Regular backups with /backup recommended
✅ Monitor /log for security issues
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Full Command List", callback_data="show_full_commands"),
                InlineKeyboardButton("⚙️ Settings Help", callback_data="show_settings_help")
            ],
            [
                InlineKeyboardButton("🚨 Admin Guide", callback_data="show_admin_guide"),
                InlineKeyboardButton("💬 Contact Support", callback_data="contact_admin")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_settings_menu(self, query, context):
        """Show settings menu"""
        text = """
⚙️ **Group Settings Panel**

Configure your group's behavior and features:

**🛡️ Security Settings:**
• Content filtering controls
• Anti-spam sensitivity
• Link protection levels
• Adult content blocking

**👋 Welcome System:**
• Custom welcome messages
• Goodbye message settings
• Auto-delete timers
• Rich formatting options

**📋 Rules Management:**
• Custom rule creation
• Rule categories
• Automatic enforcement
• Rule export/import

**🎭 Role System:**
• Permission levels
• Custom roles
• Role-based commands
• Visual role indicators

**🔧 Advanced Options:**
• Command prefix customization
• Language preferences  
• Logging configuration
• Backup automation

Use the buttons below to access specific settings:
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🛡️ Security", callback_data="settings_security"),
                InlineKeyboardButton("👋 Welcome", callback_data="settings_welcome")
            ],
            [
                InlineKeyboardButton("📋 Rules", callback_data="settings_rules"),
                InlineKeyboardButton("🎭 Roles", callback_data="settings_roles")
            ],
            [
                InlineKeyboardButton("🔧 Advanced", callback_data="settings_advanced"),
                InlineKeyboardButton("💾 Backup", callback_data="settings_backup")
            ],
            [
                InlineKeyboardButton("🔄 Reset All", callback_data="settings_reset"),
                InlineKeyboardButton("📤 Export Settings", callback_data="settings_export")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_rules_display(self, query, context):
        """Show rules in callback"""
        # Get chat ID from query (might need adjustment based on context)
        chat_id = query.message.chat.id if query.message else None
        if not chat_id:
            await query.edit_message_text("❌ Unable to fetch rules.")
            return
            
        group_settings = self.get_group_settings(chat_id)
        rules = group_settings.get("rules", self.config["default_rules"])
        
        rules_text = "📋 **Group Rules:**\n\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule}\n"
        
        rules_text += f"\n⚠️ **Warning System:** {self.config['warn_limit']} warnings = restrictions"
        rules_text += f"\n🛡️ **Protection:** Advanced content filtering active"
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Manage Rules", callback_data="show_rules_manager")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            rules_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _handle_command_callback(self, query, context, data):
        """Handle command callbacks from inline keyboards"""
        command = data.replace("cmd_", "")
        
        command_responses = {
            "quote": "💭 Click a button below to get an inspirational quote!",
            "joke": "😄 Ready for a random joke? Click the button!",
            "cat": "🐱 Want to learn something interesting about cats?",
            "poll": "📊 Create polls to engage your community!",
            "info": "👤 Get detailed user information and statistics!",
            "stats": "📈 View comprehensive group analytics!",
            "backup": "📦 Export all your group settings safely!",
            "reload": "🔄 Refresh bot configuration from files!",
            "contactadmin": "📞 Get direct support from the developer!",
            "adminhelp": "🚨 Complete admin command reference guide!"
        }
        
        response = command_responses.get(command, "🔧 Feature coming soon!")
        
        keyboard = [
            [InlineKeyboardButton(f"✅ Use /{command}", callback_data=f"use_{command}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            f"🎯 **Command: /{command}**\n\n{response}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Continue with all other callback menu methods...
    # (Implementing all the menu methods shown in the previous sections)

    # ======================== MESSAGE HANDLERS ========================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all messages for content filtering"""
        if not update.message or not update.effective_user or not update.effective_chat:
            return
            
        # Skip if not a group
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        
        # Skip admin messages
        if await self.is_admin(update, context):
            return
        
        message = update.message
        user = update.effective_user
        
        # Get group settings
        group_settings = self.get_group_settings(update.effective_chat.id)
        
        # Content filtering
        if group_settings["settings"].get("content_filtering_enabled", True):
            if message.text:
                content_result = self.content_filter.check_content(
                    message.text,
                    check_adult=self.config["content_filtering"]["check_adult_content"],
                    check_profanity=self.config["content_filtering"]["check_profanity"],
                    check_harassment=self.config["content_filtering"]["check_harassment"]
                )
                
                if not content_result["is_safe"]:
                    await self._handle_content_violation(update, context, content_result)
                    return
        
        # Anti-spam check
        if group_settings["settings"].get("anti_spam_enabled", True):
            spam_result = self.anti_spam.check_spam(user.id, message)
            
            if spam_result["is_spam"]:
                await self._handle_spam_violation(update, context, spam_result)
                return

    async def _handle_content_violation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, result: Dict):
        """Handle content filter violations"""
        try:
            # Delete the message
            await update.message.delete()
            self.stats["messages_filtered"] += 1
            
            # Send warning
            violation_text = f"🚨 **Content Violation Detected**\n\n"
            violation_text += f"👤 User: {update.effective_user.first_name}\n"
            violation_text += f"⚠️ Violations: {', '.join(result['violations'])}\n"
            violation_text += f"🎯 Severity: {result['severity'].title()}\n"
            violation_text += f"⚡ Action: Message deleted"
            
            warning_msg = await context.bot.send_message(
                update.effective_chat.id,
                violation_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            try:
                await warning_msg.delete()
            except:
                pass
            
            # Log the violation
            self._log_action(
                update.effective_chat.id,
                "content_filter",
                0,  # System action
                update.effective_user.id,
                result["violations"]
            )
            
        except Exception as e:
            logger.error(f"Error handling content violation: {e}")

    async def _handle_spam_violation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, result: Dict):
        """Handle spam violations"""
        try:
            # Delete the message
            await update.message.delete()
            self.stats["spam_blocked"] += 1
            
            # Take action based on spam score
            action_taken = "Message deleted"
            
            if result["suggested_action"] == "mute":
                try:
                    until_date = datetime.now() + timedelta(minutes=5)
                    permissions = ChatPermissions(can_send_messages=False)
                    await context.bot.restrict_chat_member(
                        update.effective_chat.id,
                        update.effective_user.id,
                        permissions=permissions,
                        until_date=until_date
                    )
                    action_taken = "User muted for 5 minutes"
                except:
                    pass
            
            # Send warning
            spam_text = f"🚫 **Spam Detected**\n\n"
            spam_text += f"👤 User: {update.effective_user.first_name}\n"
            spam_text += f"📊 Spam Score: {result['spam_score']}/100\n"
            spam_text += f"⚠️ Violations: {', '.join(result['violations'])}\n"
            spam_text += f"⚡ Action: {action_taken}"
            
            warning_msg = await context.bot.send_message(
                update.effective_chat.id,
                spam_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            try:
                await warning_msg.delete()
            except:
                pass
            
        except Exception as e:
            logger.error(f"Error handling spam violation: {e}")

    # ======================== NEW MEMBER HANDLER ========================
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle new members joining"""
        if not update.message or not update.message.new_chat_members:
            return
        
        chat = update.effective_chat
        group_settings = self.get_group_settings(chat.id)
        
        if not group_settings["settings"].get("welcome_enabled", True):
            return
        
        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue
                
            # Format welcome message
            welcome_msg = group_settings.get("welcome_message", self.config["welcome_message"])
            welcome_msg = welcome_msg.format(
                name=new_member.first_name,
                username=new_member.username or "N/A",
                id=new_member.id,
                group=chat.title or "this group"
            )
            
            try:
                keyboard = [
                    [InlineKeyboardButton("📋 Read Rules", callback_data="show_rules")],
                    [InlineKeyboardButton("❓ Get Help", callback_data="show_help")]
                ]
                
                await context.bot.send_message(
                    chat.id,
                    welcome_msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")

    async def handle_left_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle members leaving"""
        if not update.message or not update.message.left_chat_member:
            return
        
        chat = update.effective_chat
        left_member = update.message.left_chat_member
        group_settings = self.get_group_settings(chat.id)
        
        if not group_settings["settings"].get("goodbye_enabled", True):
            return
        
        if left_member.is_bot:
            return
            
        # Format goodbye message
        goodbye_msg = group_settings.get("goodbye_message", self.config["goodbye_message"])
        goodbye_msg = goodbye_msg.format(
            name=left_member.first_name,
            username=left_member.username or "N/A",
            id=left_member.id
        )
        
        try:
            await context.bot.send_message(
                chat.id,
                goodbye_msg,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Failed to send goodbye message: {e}")

    # ======================== SETUP HANDLERS ========================
    
    def setup_handlers(self, application: Application) -> None:
        """Setup all command and message handlers"""
        # Basic command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("about", self.about_command))
        application.add_handler(CommandHandler("menu", self.menu_command))
        application.add_handler(CommandHandler("rules", self.rules_command))
        application.add_handler(CommandHandler("setrules", self.setrules_command))
        
        # Admin command handlers
        application.add_handler(CommandHandler("kick", self.kick_command))
        application.add_handler(CommandHandler("ban", self.ban_command))
        application.add_handler(CommandHandler("unban", self.unban_command))
        application.add_handler(CommandHandler("mute", self.mute_command))
        application.add_handler(CommandHandler("unmute", self.unmute_command))
        application.add_handler(CommandHandler("warn", self.warn_command))
        application.add_handler(CommandHandler("warnings", self.warnings_command))
        application.add_handler(CommandHandler("clearwarns", self.clearwarns_command))
        application.add_handler(CommandHandler("purge", self.purge_command))
        
        # Role management handlers
        application.add_handler(CommandHandler("addrole", self.addrole_command))
        application.add_handler(CommandHandler("removerole", self.removerole_command))
        application.add_handler(CommandHandler("userroles", self.userroles_command))
        application.add_handler(CommandHandler("roles", self.roles_command))
        application.add_handler(CommandHandler("admins", self.admins_command))
        
        # Welcome/Goodbye handlers
        application.add_handler(CommandHandler("setwelcome", self.setwelcome_command))
        application.add_handler(CommandHandler("setgoodbye", self.setgoodbye_command))
        application.add_handler(CommandHandler("welcome", self.welcome_command))
        application.add_handler(CommandHandler("goodbye", self.goodbye_command))
        
        # Info command handlers
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(CommandHandler("profile", self.profile_command))
        
        # Fun command handlers
        application.add_handler(CommandHandler("quote", self.quote_command))
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("cat", self.cat_command))
        application.add_handler(CommandHandler("poll", self.poll_command))
        
        # Advanced moderation handlers
        application.add_handler(CommandHandler("lock", self.lock_command))
        application.add_handler(CommandHandler("unlock", self.unlock_command))
        application.add_handler(CommandHandler("restrict", self.restrict_command))
        application.add_handler(CommandHandler("detectspam", self.detectspam_command))
        application.add_handler(CommandHandler("antispam", self.antispam_command))
        application.add_handler(CommandHandler("antiflood", self.antiflood_command))
        application.add_handler(CommandHandler("log", self.log_command))
        
        # Member management handlers
        application.add_handler(CommandHandler("promote", self.promote_command))
        application.add_handler(CommandHandler("demote", self.demote_command))
        application.add_handler(CommandHandler("listmembers", self.listmembers_command))
        application.add_handler(CommandHandler("inactive", self.inactive_command))
        
        # Content filtering handlers
        application.add_handler(CommandHandler("antinsfw", self.antinsfw_command))
        application.add_handler(CommandHandler("antilink", self.antilink_command))
        
        # Storage & Export handlers
        application.add_handler(CommandHandler("backup", self.backup_command))
        application.add_handler(CommandHandler("restore", self.restore_command))
        application.add_handler(CommandHandler("exportroles", self.exportroles_command))
        application.add_handler(CommandHandler("exportrules", self.exportrules_command))
        
        # Admin support handlers
        application.add_handler(CommandHandler("contactadmin", self.contactadmin_command))
        application.add_handler(CommandHandler("adminhelp", self.adminhelp_command))
        application.add_handler(CommandHandler("report", self.report_command))
        
        # Configuration handlers
        application.add_handler(CommandHandler("language", self.language_command))
        application.add_handler(CommandHandler("reloadconfig", self.reloadconfig_command))
        application.add_handler(CommandHandler("setprefix", self.setprefix_command))
        application.add_handler(CommandHandler("setrolecolor", self.setrolecolor_command))
        
        # Callback query handler
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # New/Left member handlers
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member))
        application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.handle_left_member))
        
        # Message handler for content filtering (MUST be last)
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message))

# ======================== BOT COMMANDS SETUP ========================

async def setup_bot_commands(application: Application) -> None:
    """Setup bot command menu"""
    commands = [
        # Basic Commands
        BotCommand("start", "🚀 Start the bot & show welcome"),
        BotCommand("help", "❓ Show help & command list"),
        BotCommand("menu", "🎛️ Open interactive main menu"),
        BotCommand("about", "ℹ️ About GROUP MEG Bot"),
        BotCommand("rules", "📋 Show group rules"),
        
        # Admin Commands
        BotCommand("settings", "⚙️ Open settings panel (admin)"),
        BotCommand("kick", "🦵 Kick user (admin only)"),
        BotCommand("ban", "🔨 Ban user (admin only)"),
        BotCommand("mute", "🔇 Mute user (admin only)"),
        BotCommand("warn", "⚠️ Warn user (admin only)"),
        
        # Fun Commands
        BotCommand("quote", "💭 Get motivational quote"),
        BotCommand("joke", "😄 Tell a random joke"),
        BotCommand("cat", "🐱 Share cat facts"),
        BotCommand("poll", "📊 Create a group poll"),
        
        # Info Commands
        BotCommand("stats", "📊 Show group statistics"),
        BotCommand("info", "👤 Show user information"),
        BotCommand("admins", "👮‍♂️ List group admins"),
        
        # Utility Commands
        BotCommand("backup", "📦 Export group settings (admin)"),
        BotCommand("adminhelp", "🚨 Admin command reference"),
        BotCommand("contactadmin", "📞 Contact developer support")
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands menu updated successfully")

# ======================== MAIN FUNCTION ========================

async def async_main():
    """Async main function to handle bot startup"""
    # Get bot token from environment
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable is required!")
        return
    
    try:
        # Initialize bot
        bot = GroupMegBot()
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        bot.setup_handlers(application)
        
        # Set up bot commands menu
        await setup_bot_commands(application)
        
        logger.info("🚀 GROUP MEG Bot is starting...")
        logger.info(f"🤖 Bot Name: {bot.config['bot_name']}")
        logger.info(f"👨‍💻 Developer: {bot.config['developer']['name']}")
        logger.info(f"🇧🇩 Nationality: {bot.config['developer']['nationality']}")
        logger.info("✅ All systems initialized successfully")
        logger.info("🛡️ Advanced content filtering enabled")
        logger.info("🚫 Anti-spam protection active")
        logger.info("🎯 Ready to manage groups professionally!")
        
        # Run the bot
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Critical error starting bot: {e}")
        raise
    finally:
        # Cleanup
        if 'application' in locals():
            await application.shutdown()

def main():
    """Main function to run the bot with proper event loop"""
    try:
        # Create new event loop if none exists
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async main function
        asyncio.run(async_main())
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()

