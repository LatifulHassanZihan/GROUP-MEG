#!/bin/bash

# Navigate to script directory
cd "$(dirname "$0")"

# Install dependencies (optional if already done in Render build)
pip install -r requirements.txt

# Start the bot
python3 group_meg.py
