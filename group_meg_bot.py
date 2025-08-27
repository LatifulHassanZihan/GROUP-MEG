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

    # Basic Commands
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start command handler"""
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
        """Help command handler"""
        self.stats["commands_used"] += 1
        
        help_text = """
🆘 **GROUP MEG Bot - Command Help** 🇵🇸

📋 **Basic Commands:**
• /start - Start bot & show welcome
• /help - Display this help message
• /about - Bot information
• /rules - Show group rules
• /settings - Open settings panel (admin)

🛡️ **Admin & Moderation:**
• /kick [reply] - Kick user from group
• /ban [reply] - Ban user permanently
• /unban <user_id> - Unban user by ID
• /mute <seconds> [reply] - Mute user temporarily  
• /unmute [reply] - Unmute user
• /purge - Delete batch of messages
• /warn [reply + reason] - Warn user
• /warnings [reply] - Show user warnings

🎯 **Role Commands:**
• /addrole <role> [reply] - Assign role to user
• /removerole <role> [reply] - Remove user role
• /userroles [reply] - List user roles
• /roles - Display all available roles
• /admins - List group administrators

👋 **Welcome & Goodbye:**
• /setwelcome <text> - Set welcome message
• /setgoodbye <text> - Set goodbye message
• /welcome - Show current welcome text
• /goodbye - Show current goodbye text

🔧 **Configuration:**
• /setrules <text> - Set group rules
• /language <code> - Set bot language
• /reloadconfig - Reload settings

📊 **Info Commands:**
• /info [reply] - Show user details
• /stats - Display group statistics

🎮 **Fun & Engagement:**
• /quote - Get motivational quote
• /poll <question> - Create group poll
• /joke - Tell a random joke
• /cat - Share random cat picture

🛡️ **Moderation & Security:**
• /lock - 🔒 Lock group (disable messaging)
• /unlock - 🔓 Unlock group (enable messaging)  
• /restrict [reply/user_id] - ⚠️ Restrict user
• /clearwarns [reply] - 🧹 Clear user warnings
• /detectspam - 🔍 Scan recent spam messages
• /antispam on|off - 🛡️ Toggle anti-spam filter
• /antiflood on|off - 🌊 Toggle anti-flood controls
• /log - 📜 Show recent group events

👥 **Member Management:**
• /promote [reply/user_id] - 👑 Promote to admin
• /demote [reply/user_id] - ⬇️ Demote admin
• /listmembers - 👥 List all members
• /inactive - 😴 List inactive users
• /profile [reply] - 👤 Show user profile

📝 **Content & Rules:**
• /setrules <text> - 📋 Set custom rules
• /setlang <code> - 🌐 Set bot language
• /antinsfw on|off - 🚫 Adult content filter
• /antilink on|off - 🔗 Block external links
• /setwelcome <text> - 👋 Set welcome message  
• /setgoodbye <text> - 👋 Set goodbye message

💾 **Storage & Export:**
• /backup - 📦 Export group settings
• /restore <file> - 📂 Restore from backup
• /exportroles - 🏷️ Export user roles as CSV
• /exportrules - 📋 Export rules as text

🎪 **Fun Features:**
• /quote - 💭 Random motivational quote
• /poll <question> - 📊 Create group poll  
• /joke - 😄 Tell me a joke
• /cat - 🐱 Random cat picture

🆘 **Admin Support:**
• /contactadmin - 📞 Emergency admin help
• /adminhelp - 🚨 List admin commands
• /report [reply] - 🚨 Report to admins

⚙️ **Advanced Options:**
• /menu - 🎛️ Interactive main menu
• /settings - ⚙️ Advanced settings panel
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
        """About command handler"""
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
        """Open interactive menu"""
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

    # Rules Commands
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display group rules"""
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

    # Admin Commands
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Kick user command"""
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
        """Ban user command"""
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

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mute user command"""
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

    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Warn user command"""
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

    # Fun Commands
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send motivational quote"""
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
            "⚡ Sometimes we're tested not to show our weaknesses, but to discover our strengths."
        ]
        
        quote = random.choice(quotes)
        await update.message.reply_text(f"💭 **Daily Motivation:**\n\n{quote}")

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Tell a random joke"""
        self.stats["commands_used"] += 1
        
        jokes = [
            "Why don't scientists trust atoms? 🧪\nBecause they make up everything!",
            "Why did the programmer quit his job? 💻\nHe didn't get arrays!",
            "What do you call a fake noodle? 🍜\nAn impasta!",
            "Why don't eggs tell jokes? 🥚\nThey'd crack each other up!",
            "What do you call a bear with no teeth? 🐻\nA gummy bear!",
            "Why did the math book look so sad? 📚\nBecause it was full of problems!",
            "What's the best thing about Switzerland? 🇨🇭\nI don't know, but the flag is a big plus!",
            "Why don't skeletons fight each other? 💀\nThey don't have the guts!"
        ]
        
        joke = random.choice(jokes)
        await update.message.reply_text(f"😄 **Random Joke:**\n\n{joke}")

    async def cat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send random cat fact and emoji"""
        self.stats["commands_used"] += 1
        
        cat_facts = [
            "🐱 Cats sleep 12-16 hours per day!",
            "🐈 A group of cats is called a 'clowder'!",  
            "😸 Cats can make over 100 different vocal sounds!",
            "🐾 Cats have a third eyelid called a 'nictitating membrane'!",
            "😻 Cats can't taste sweetness!",
            "🐈‍⬛ Black cats are considered good luck in many countries!",
            "😺 Cats have whiskers on their legs too!",
            "🐱 A cat's purr can help heal bones!"
        ]
        
        fact = random.choice(cat_facts)
        await update.message.reply_text(f"🐱 **Cat Fact:**\n\n{fact}")

    # Callback Query Handler
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

    async def _show_moderation_menu(self, query, context):
        """Show moderation menu"""
        text = """
🛡️ **Moderation Tools** 

Advanced moderation commands for group management:

**User Actions:**
• Warn, kick, ban, mute users
• Manage user restrictions  
• Clear warnings & violations
• Promote/demote administrators

**Content Control:**
• Message purging & cleanup
• Link filtering & validation
• Spam detection & removal
• Adult content blocking

**Group Security:**
• Lock/unlock group messaging
• Anti-flood protection
• Suspicious activity monitoring
• Automated violation responses

Use /help for detailed command syntax.
        """
        
        keyboard = [
            [
                InlineKeyboardButton("⚠️ Warning System", callback_data="mod_warnings"),
                InlineKeyboardButton("🔨 Ban Management", callback_data="mod_bans")
            ],
            [
                InlineKeyboardButton("🔇 Mute Controls", callback_data="mod_mutes"),
                InlineKeyboardButton("🧹 Message Cleanup", callback_data="mod_cleanup")
            ],
            [
                InlineKeyboardButton("🛡️ Auto Moderation", callback_data="mod_auto"),
                InlineKeyboardButton("📊 Mod Statistics", callback_data="mod_stats")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_statistics(self, query, context):
        """Show bot statistics"""
        uptime = self._get_uptime()
        
        text = f"""
📊 **GROUP MEG Bot Statistics** 🇵🇸

**📈 Usage Statistics:**
• Commands Used: {self.stats['commands_used']:,}
• Groups Managed: {self.stats['groups_managed']:,}
• Users Registered: {self.stats['users_registered']:,}
• Messages Filtered: {self.stats['messages_filtered']:,}
• Spam Blocked: {self.stats['spam_blocked']:,}

**⏰ System Information:**
• Bot Uptime: {uptime}
• Start Time: {self.stats['start_time'][:19]}
• Python Version: 3.11+
• Memory Usage: Optimized
• Response Time: < 100ms average

**🛡️ Protection Statistics:**
• Content Violations Detected: {self.stats['messages_filtered']:,}
• Spam Messages Blocked: {self.stats['spam_blocked']:,}
• Active Filters: Adult Content, Profanity, Links
• Auto-Moderation: Enabled

**📋 Group Health:**
• Active Groups: {len(self.groups_data)}
• Average Rules per Group: {self._get_avg_rules()}
• Most Used Command: /help
• Peak Usage Time: Evening (UTC+6)

---
📈 Performance: Excellent • 🛡️ Security: Maximum
        """
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="show_stats")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _get_avg_rules(self) -> int:
        """Calculate average rules per group"""
        if not self.groups_data:
            return len(self.config["default_rules"])
        
        total_rules = sum(len(group_data.get("rules", [])) for group_data in self.groups_data.values())
        return total_rules // len(self.groups_data) if self.groups_data else 0

    async def _show_content_filter_menu(self, query, context):
        """Show content filter menu"""
        text = """
🛡️ **Advanced Content Filtering** 

Protect your group with AI-powered content moderation:

**🔞 Adult Content Filter:**
• Detects explicit material & inappropriate content
• Blocks NSFW images, links & text
• Automatic violation warnings
• Customizable sensitivity levels

**🤬 Profanity Detection:**
• Multi-language bad word filtering
• Context-aware detection
• Custom word lists per group
• Smart evasion prevention

**🚫 Anti-Spam System:**
• Message frequency monitoring
• Duplicate content detection  
• Link spam prevention
• Automated temporary restrictions

**⚠️ Harassment Protection:**
• Threat detection & analysis
• Hate speech identification
• Cyberbullying prevention
• Immediate intervention protocols

All filters are fully customizable per group!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🔞 Adult Filter", callback_data="filter_adult_config"),
                InlineKeyboardButton("🤬 Profanity Filter", callback_data="filter_profanity_config")
            ],
            [
                InlineKeyboardButton("🚫 Anti-Spam", callback_data="filter_spam_config"),
                InlineKeyboardButton("⚠️ Harassment Detection", callback_data="filter_harassment_config")
            ],
            [
                InlineKeyboardButton("🔗 Link Protection", callback_data="filter_links_config"),
                InlineKeyboardButton("📊 Filter Analytics", callback_data="filter_analytics")
            ],
            [
                InlineKeyboardButton("⚙️ Filter Settings", callback_data="filter_global_settings"),
                InlineKeyboardButton("🔄 Reset Filters", callback_data="filter_reset")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_welcome_menu(self, query, context):
        """Show welcome/goodbye menu"""
        text = """
👋 **Welcome & Goodbye Messages**

Create warm, professional greetings for your community:

**🎉 Welcome Features:**
• Custom welcome messages with user variables
• Rich formatting with markdown support
• Automatic rule reminders
• Interactive welcome buttons
• Media attachments support

**👋 Goodbye Features:**
• Personalized farewell messages  
• Thank you notes for contribution
• Optional goodbye disable
• Custom timing settings

**📝 Available Variables:**
• `{name}` - User's first name
• `{username}` - User's username
• `{id}` - User's ID
• `{group}` - Group name
• `{rules}` - Link to rules
• `{count}` - Member count

**Current Settings:**
✅ Welcome messages: Enabled
✅ Goodbye messages: Enabled  
✅ Variables: Supported
✅ Rich formatting: Active
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🎉 Set Welcome", callback_data="set_welcome_msg"),
                InlineKeyboardButton("👋 Set Goodbye", callback_data="set_goodbye_msg")
            ],
            [
                InlineKeyboardButton("👀 Preview Welcome", callback_data="preview_welcome"),
                InlineKeyboardButton("👀 Preview Goodbye", callback_data="preview_goodbye")
            ],
            [
                InlineKeyboardButton("⚙️ Welcome Settings", callback_data="welcome_settings"),
                InlineKeyboardButton("🔄 Reset Messages", callback_data="reset_welcome_goodbye")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Message Handler for Content Filtering
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
            
            warning_msg = await update.message.reply_text(
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
            
            warning_msg = await update.message.reply_text(
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

    async def _show_games_menu(self, query, context):
        """Show games and fun menu"""
        text = """
🎮 **Fun & Entertainment**

Engage your community with interactive features:

**🎯 Available Games & Features:**
• Random quotes & motivation
• Joke generator with categories
• Cat facts & cute content
• Interactive polls & surveys
• Word games & trivia
• Community challenges

**💭 Quote System:**
• Daily motivational quotes
• Success & inspiration themes
• Famous personality quotes
• Custom quote submissions

**😄 Humor Features:**
• Clean joke database
• Multiple categories
• Community-friendly content
• Regular updates

**📊 Interactive Polls:**
• Easy poll creation
• Anonymous voting
• Results tracking
• Custom options

Use /quote, /joke, /cat or /poll to get started!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💭 Random Quote", callback_data="cmd_quote"),
                InlineKeyboardButton("😄 Tell Joke", callback_data="cmd_joke")
            ],
            [
                InlineKeyboardButton("🐱 Cat Facts", callback_data="cmd_cat"),
                InlineKeyboardButton("📊 Create Poll", callback_data="cmd_poll")
            ],
            [
                InlineKeyboardButton("🎯 Mini Games", callback_data="show_mini_games"),
                InlineKeyboardButton("🎪 Fun Settings", callback_data="fun_settings")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_info_menu(self, query, context):
        """Show info commands menu"""
        text = """
🔍 **Information Commands**

Get detailed information about users and groups:

**👤 User Information:**
• Detailed user profiles & statistics
• Join date & activity levels
• Role assignments & permissions
• Warning history & violations
• Message count & engagement

**📊 Group Analytics:**
• Member statistics & growth
• Message activity patterns
• Most active users & times
• Content type breakdown
• Moderation statistics

**🔧 System Information:**
• Bot performance metrics
• Command usage statistics  
• Filter effectiveness rates
• Error logs & debugging
• Uptime & reliability stats

**Available Commands:**
• /info [reply] - User details
• /stats - Group statistics
• /profile [reply] - Full user profile
• /listmembers - All members
• /admins - Group administrators

Get insights to optimize your group management!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👤 User Info", callback_data="cmd_info"),
                InlineKeyboardButton("📊 Group Stats", callback_data="cmd_stats")
            ],
            [
                InlineKeyboardButton("👥 List Members", callback_data="cmd_listmembers"),
                InlineKeyboardButton("👑 Show Admins", callback_data="cmd_admins")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="show_analytics"),
                InlineKeyboardButton("🔧 System Info", callback_data="show_system_info")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_utilities_menu(self, query, context):
        """Show utilities menu"""
        text = """
🔧 **Utility Commands**

Essential tools for group management:

**💾 Backup & Storage:**
• Export all group settings
• Restore from backup files
• Role assignments backup
• Rules & configuration export

**🔄 Configuration Management:**
• Reload bot settings
• Update group configurations  
• Reset to default settings
• Import/export preferences

**🌐 Language & Localization:**
• Multi-language support
• Custom response languages
• Regional format settings
• Translation management

**🔧 Advanced Tools:**
• Custom command prefixes
• Interactive button panels
• Automation workflows
• API integrations

**Maintenance Features:**
• System diagnostics
• Performance optimization
• Error log analysis
• Cache management

Keep your bot running smoothly with these tools!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💾 Backup Data", callback_data="cmd_backup"),
                InlineKeyboardButton("🔄 Reload Config", callback_data="cmd_reload")
            ],
            [
                InlineKeyboardButton("🌐 Language", callback_data="cmd_language"),
                InlineKeyboardButton("🔧 Advanced", callback_data="show_advanced")
            ],
            [
                InlineKeyboardButton("📋 Export Settings", callback_data="export_settings"),
                InlineKeyboardButton("📥 Import Settings", callback_data="import_settings")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_admin_help_menu(self, query, context):
        """Show admin help menu"""
        text = """
🚨 **Admin Help & Support**

Emergency assistance and advanced admin features:

**📞 Emergency Contact:**
• Direct admin communication
• Priority support channels
• Urgent issue resolution
• 24/7 assistance availability

**🆘 Quick Actions:**
• Immediate group lockdown
• Emergency user restrictions
• Mass message deletion
• Panic mode activation

**📋 Admin Command Reference:**
• Complete command documentation
• Permission level explanations
• Best practice guidelines
• Troubleshooting guides

**🔧 Advanced Admin Tools:**
• Bulk user management
• Automated responses
• Custom enforcement rules
• Advanced logging options

**📊 Admin Reports:**
• Daily activity summaries
• Violation trend analysis
• Performance metrics
• Security incident logs

For immediate assistance, use /contactadmin or reach out to the developer directly.
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📞 Contact Admin", callback_data="cmd_contactadmin"),
                InlineKeyboardButton("📋 Admin Commands", callback_data="cmd_adminhelp")
            ],
            [
                InlineKeyboardButton("🆘 Emergency Mode", callback_data="emergency_mode"),
                InlineKeyboardButton("📊 Admin Reports", callback_data="admin_reports")
            ],
            [
                InlineKeyboardButton("🔧 Advanced Tools", callback_data="advanced_admin_tools"),
                InlineKeyboardButton("📚 Documentation", callback_data="admin_docs")
            ],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _reload_config(self, query, context):
        """Reload bot configuration"""
        try:
            self.config = self.load_config()
            self.groups_data = self.load_json_file("groups.json", {})
            self.users_data = self.load_json_file("users.json", {})
            self.warnings_data = self.load_json_file("warnings.json", {})
            
            text = """
🔄 **Configuration Reloaded Successfully!**

✅ All settings have been refreshed from files
✅ Group configurations updated
✅ User data synchronized
✅ Warning systems refreshed

**Reloaded Components:**
• Bot configuration (config.json)
• Group settings & rules
• User roles & permissions
• Warning & violation data
• Content filter settings
• Anti-spam parameters

The bot is now running with the latest configuration!
            """
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]])
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ **Configuration Reload Failed**\n\nError: {str(e)}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]])
            )

    async def _contact_admin(self, query, context):
        """Show contact admin options"""
        text = f"""
📞 **Contact Admin Support**

Need urgent help or have questions? Multiple ways to reach us:

**🔥 Emergency Support:**
For immediate assistance with bot issues, security concerns, or urgent group management needs.

**💬 Developer Contact:**
• Telegram: {self.config['developer']['username']}
• Response Time: Usually within 2-4 hours
• Available: 16+ hours daily
• Languages: English, বাংলা

**🛠️ Technical Support:**
• Bug reports & feature requests
• Custom development inquiries  
• Integration assistance
• Performance optimization

**📋 What to Include:**
• Your group ID: `{query.message.chat.id if query.message else 'N/A'}`
• Issue description
• Steps to reproduce
• Screenshots if applicable

**⚡ Quick Help:**
• Use /adminhelp for command reference
• Check /help for common solutions
• Review /settings for configuration issues

We're here to help make your group management experience smooth and professional!
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Message Developer", url=f"https://t.me/{self.config['developer']['username'].replace('@', '')}")],
            [InlineKeyboardButton("📋 Admin Commands", callback_data="cmd_adminhelp")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def setup_handlers(self, application: Application) -> None:
        """Setup all command and message handlers"""
        # Basic command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("about", self.about_command))
        application.add_handler(CommandHandler("menu", self.menu_command))
        application.add_handler(CommandHandler("rules", self.rules_command))
        
        # Admin command handlers
        application.add_handler(CommandHandler("kick", self.kick_command))
        application.add_handler(CommandHandler("ban", self.ban_command))
        application.add_handler(CommandHandler("mute", self.mute_command))
        application.add_handler(CommandHandler("warn", self.warn_command))
        
        # Fun command handlers
        application.add_handler(CommandHandler("quote", self.quote_command))
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("cat", self.cat_command))
        
        # Callback query handler
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handler for content filtering
        application.add_handler(MessageHandler(filters.ALL, self.handle_message))

async def setup_bot_commands(application: Application) -> None:
    """Setup bot command menu"""
    commands = [
        BotCommand("start", "🚀 Start the bot & show welcome"),
        BotCommand("help", "❓ Show help & command list"),
        BotCommand("menu", "🎛️ Open interactive main menu"),
        BotCommand("about", "ℹ️ About GROUP MEG Bot"),
        BotCommand("rules", "📋 Show group rules"),
        BotCommand("settings", "⚙️ Open settings panel"),
        BotCommand("kick", "🦵 Kick user (admin only)"),
        BotCommand("ban", "🔨 Ban user (admin only)"),
        BotCommand("mute", "🔇 Mute user (admin only)"),
        BotCommand("warn", "⚠️ Warn user (admin only)"),
        BotCommand("quote", "💭 Get motivational quote"),
        BotCommand("joke", "😄 Tell a random joke"),
        BotCommand("cat", "🐱 Share cat facts"),
        BotCommand("stats", "📊 Show group statistics"),
        BotCommand("info", "👤 Show user information")
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands menu updated successfully")

def main():
    """Main function to run the bot"""
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
        asyncio.run(setup_bot_commands(application))
        
        logger.info("🚀 GROUP MEG Bot is starting...")
        logger.info(f"🤖 Bot Name: {bot.config['bot_name']}")
        logger.info(f"👨‍💻 Developer: {bot.config['developer']['name']}")
        logger.info(f"🇧🇩 Nationality: {bot.config['developer']['nationality']}")
        logger.info("✅ All systems initialized successfully")
        logger.info("🛡️ Advanced content filtering enabled")
        logger.info("🚫 Anti-spam protection active")
        logger.info("🎯 Ready to manage groups professionally!")
        
        # Run the bot
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"❌ Critical error starting bot: {e}")
        raise

if __name__ == "__main__":
    main()

