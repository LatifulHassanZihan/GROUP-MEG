#!/usr/bin/env python3
"""
🔧 Group MEG Bot - Data Setup Script
Creates all necessary JSON files and directories
Developer: Latiful Hassan Zihan 🇧🇩
"""

import json
import os
from pathlib import Path
from datetime import datetime

def create_project_structure():
    """Create all necessary directories and JSON files"""
    
    print("🚀 Setting up Group MEG Bot project structure...")
    print("=" * 60)
    
    # Create directories
    directories = [
        "data",
        "backups", 
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}/")
    
    # JSON file templates
    json_files = {
        "data/config.json": {
            "bot_settings": {
                "bot_token": "YOUR_BOT_TOKEN_HERE",
                "webhook_url": None,
                "developer_username": "alwayszihan",
                "support_chat": "@alwayszihan",
                "version": "2.1.0",
                "debug_mode": False
            },
            "default_settings": {
                "anti_spam": True,
                "welcome_enabled": True,
                "anti_flood": True,
                "goodbye_enabled": True,
                "alphabet_filter": False,
                "captcha_enabled": False,
                "checks_enabled": True,
                "admin_call": True,
                "blocks_enabled": True,
                "media_settings": True,
                "porn_filter": True,
                "warns_enabled": True,
                "night_mode": False,
                "tag_enabled": True,
                "link_filter": False,
                "approval_mode": False,
                "delete_messages": False,
                "language": "en",
                "flood_limit": 5,
                "flood_time": 10,
                "welcome_message": "👋 Welcome {mention}! Please read our rules and enjoy your stay! 🎉",
                "goodbye_message": "👋 Goodbye {mention}! We'll miss you! 😢",
                "rules": "📜 **Default Group Rules:**\n1️⃣ Be respectful to all members\n2️⃣ No spam or self-promotion\n3️⃣ Keep discussions on-topic\n4️⃣ No NSFW content\n5️⃣ Follow Telegram ToS"
            },
            "role_permissions": {
                "moderator": {
                    "can_delete_messages": True,
                    "can_restrict_members": True,
                    "can_warn_users": True,
                    "can_mute_users": True,
                    "can_kick_users": False,
                    "can_ban_users": False,
                    "can_manage_settings": False
                },
                "helper": {
                    "can_delete_messages": True,
                    "can_restrict_members": False,
                    "can_warn_users": True,
                    "can_mute_users": False,
                    "can_kick_users": False,
                    "can_ban_users": False,
                    "can_manage_settings": False
                },
                "vip": {
                    "can_delete_messages": False,
                    "can_restrict_members": False,
                    "can_warn_users": False,
                    "can_mute_users": False,
                    "can_kick_users": False,
                    "can_ban_users": False,
                    "can_manage_settings": False
                }
            }
        },
        
        "data/group_settings.json": {
            "groups": {}
        },
        
        "data/user_roles.json": {
            "roles": {}
        },
        
        "data/warnings.json": {
            "warnings": {}
        },
        
        "data/logs.json": {
            "logs": [],
            "log_settings": {
                "max_logs": 10000,
                "auto_cleanup_days": 30,
                "log_levels": ["info", "warning", "error"]
            }
        }
    }
    
    # Create JSON files
    for file_path, content in json_files.items():
        if not Path(file_path).exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            print(f"✅ Created: {file_path}")
        else:
            print(f"📄 Already exists: {file_path}")
    
    print("\n" + "=" * 60)
    print("🎉 **Setup Complete!**")
    print("\n📝 **Next Steps:**")
    print("1. Edit data/config.json - Add your bot token")
    print("2. Run: python group_meg_bot.py")
    print("3. Add bot to your group using /start command")
    print("\n👨‍💻 **Developer:** Latiful Hassan Zihan 🇧🇩")
    print("📞 **Support:** @alwayszihan")
    print("🇵🇸 **Free Palestine!** 🇧🇩")

def verify_setup():
    """Verify that all files are created properly"""
    required_files = [
        "data/config.json",
        "data/group_settings.json", 
        "data/user_roles.json",
        "data/warnings.json",
        "data/logs.json"
    ]
    
    print("\n🔍 **Verifying Setup...**")
    all_good = True
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - Missing!")
            all_good = False
    
    if all_good:
        print("\n🎯 **All files created successfully!**")
        return True
    else:
        print("\n⚠️ **Some files are missing. Please run setup again.**")
        return False

if __name__ == "__main__":
    print("🤖 **Group MEG Bot - Setup Script** 🛡️")
    print("🔧 **Developer:** Latiful Hassan Zihan 🇧🇩")
    print("📅 **Version:** 2.1.0 (Advanced with Persistent Storage)")
    print("")
    
    create_project_structure()
    verify_setup()
    
    print("\n🚀 **Ready to launch your advanced group management bot!**")
