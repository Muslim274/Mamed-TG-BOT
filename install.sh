#!/bin/bash

echo "======================================"
echo "Installing Telegram Referral Bot"
echo "======================================"

# Update system
echo "Updating system..."
apt update
apt upgrade -y

# Install Python and dependencies
echo "Installing Python and dependencies..."
apt install -y python3 python3-pip python3-venv

# Create virtual environment
echo "Creating virtual environment..."
cd /root/bot_deploy
python3 -m venv venv

# Activate virtual environment and install requirements
echo "Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy service file
echo "Setting up systemd service..."
cp bot.service /etc/systemd/system/bot.service

# Reload systemd
systemctl daemon-reload

# Enable and start the bot
echo "Enabling bot service..."
systemctl enable bot.service

echo ""
echo "======================================"
echo "Installation completed!"
echo "======================================"
echo ""
echo "Commands:"
echo "  Start bot:   systemctl start bot"
echo "  Stop bot:    systemctl stop bot"
echo "  Restart bot: systemctl restart bot"
echo "  Status:      systemctl status bot"
echo "  Logs:        tail -f /root/bot_deploy/bot.log"
echo ""
