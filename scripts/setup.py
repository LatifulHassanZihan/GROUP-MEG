## 🔧 Setup Script (scripts/setup.py)

```python
#!/usr/bin/env python3
"""
Setup script for GROUP MEG Bot
"""

import os
import json
from pathlib import Path

def create_directories():
    """Create necessary directories"""
    directories = ['data', 'scripts', 'logs']
    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"✅ Created directory: {dir_name}")

def create_config_file():
    """Create default config file"""
    config = {
        "bot_name": "GROUP MEG 🇵🇸",
        "bot_username": "@group_meg_bot",
        "developer": {
            "name": "Latiful Hassan Zihan 🇵🇸",
            "nationality": "Bangladeshi 🇧🇩",
            "username": "@alwayszihan"
        },
        "default_rules": [
            "🚫 No spam or excessive posting",
            "🤝 Be respectful to all members",
            "📵 No adult content",
            "🔇 No promotion without permission",
            "💬 Use appropriate language"
        ],
        "warn_limit": 3
    }
    
    with open('data/config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("✅ Created config.json")

def create_env_file():
    """Create .env template"""
    env_content = """# Get your bot token from @BotFather
BOT_TOKEN=your_bot_token_here

# Optional settings
LOG_LEVEL=INFO
ENVIRONMENT=development
"""
    with open('.env.example', 'w') as f:
        f.write(env_content)
    print("✅ Created .env.example")

def main():
    print("🚀 Setting up GROUP MEG Bot...")
    create_directories()
    create_config_file()
    create_env_file()
    print("\n✨ Setup complete!")
    print("📝 Next steps:")
    print("1. Copy .env.example to .env")
    print("2. Add your bot token from @BotFather")
    print("3. Run: python group_meg_bot.py")

if __name__ == '__main__':
    main()
