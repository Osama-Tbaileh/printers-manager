#!/bin/bash
################################################################################
# USB Auto-Setup Script for Printer Server (OFFLINE MODE)
# 
# This script installs from the USB drive directly (no internet needed!)
#
# Usage: Run this script if you have the full repo on the USB
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
USB_REPO_DIR="$(dirname "$0")/printers-manager"
INSTALL_DIR="$HOME/printer-server"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║   Printer Server - USB Auto Setup         ║"
echo "║           (OFFLINE MODE)                  ║"
echo "╔════════════════════════════════════════════╗"
echo -e "${NC}"

# Step 1: Check if source folder exists on USB
echo -e "${YELLOW}[1/5] Checking USB contents...${NC}"
if [ ! -d "$USB_REPO_DIR" ]; then
    echo -e "${RED}ERROR: Cannot find 'printers-manager' folder on USB!${NC}"
    echo "Expected location: $USB_REPO_DIR"
    echo ""
    echo "Please make sure the USB has this structure:"
    echo "  USB/"
    echo "  ├── usb_setup_offline.sh  (this script)"
    echo "  └── printers-manager/     (the server code)"
    exit 1
fi
echo -e "${GREEN}✓ Source folder found on USB${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 is not installed!${NC}"
    echo "Install it with: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
echo -e "${GREEN}✓ Python3 found${NC}"

# Step 2: Ask for installation directory
echo ""
echo -e "${YELLOW}[2/5] Setting up installation directory...${NC}"
read -p "Install to $INSTALL_DIR? (y/n, default: y): " choice
if [[ "$choice" != "" && "$choice" != "y" && "$choice" != "Y" ]]; then
    read -p "Enter installation path: " INSTALL_DIR
    INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"
fi

# Remove old installation if exists
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory $INSTALL_DIR already exists.${NC}"
    read -p "Remove and reinstall? (y/n): " remove_choice
    if [[ "$remove_choice" == "y" || "$remove_choice" == "Y" ]]; then
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}✓ Old installation removed${NC}"
    else
        echo -e "${RED}Installation cancelled.${NC}"
        exit 1
    fi
fi

# Step 3: Copy files from USB
echo ""
echo -e "${YELLOW}[3/5] Copying files from USB...${NC}"
cp -r "$USB_REPO_DIR" "$INSTALL_DIR"
echo -e "${GREEN}✓ Files copied successfully${NC}"

# Step 4: Create virtual environment
echo ""
echo -e "${YELLOW}[4/5] Creating Python virtual environment...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv
echo -e "${GREEN}✓ Virtual environment created${NC}"

# Step 5: Install requirements
echo ""
echo -e "${YELLOW}[5/5] Installing Python packages...${NC}"
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ All packages installed${NC}"
else
    echo -e "${RED}WARNING: requirements.txt not found!${NC}"
fi

# Setup printer configuration
echo ""
echo -e "${BLUE}Do you want to configure printers now?${NC}"
read -p "Enter printer IP addresses (comma-separated) or press Enter to skip: " PRINTER_IPS

if [ ! -z "$PRINTER_IPS" ]; then
    echo "# Printer Configuration" > printer_config.txt
    IFS=',' read -ra IPS <<< "$PRINTER_IPS"
    for i in "${!IPS[@]}"; do
        ip=$(echo "${IPS[$i]}" | xargs)
        echo "Printer_$((i+1))=$ip" >> printer_config.txt
        echo -e "${GREEN}✓ Saved Printer_$((i+1)): $ip${NC}"
    done
fi

# Create start script
cat > start_server.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 server.py
EOF
chmod +x start_server.sh

# Create systemd service
cat > printer-server.service << EOF
[Unit]
Description=Printer Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════╗"
echo "║         Installation Complete! ✓          ║"
echo "╔════════════════════════════════════════════╗"
echo -e "${NC}"
echo ""
echo -e "${BLUE}Installation Directory:${NC} $INSTALL_DIR"
echo -e "${BLUE}Installation Mode:${NC} Offline (from USB)"
echo ""
echo -e "${YELLOW}▸ To start the server:${NC}"
echo "  cd $INSTALL_DIR"
echo "  ./start_server.sh"
echo ""
echo -e "${YELLOW}▸ To run server in background:${NC}"
echo "  cd $INSTALL_DIR"
echo "  nohup ./start_server.sh > server.log 2>&1 &"
echo ""
echo -e "${YELLOW}▸ To install as system service (auto-start on boot):${NC}"
echo "  sudo cp $INSTALL_DIR/printer-server.service /etc/systemd/system/"
echo "  sudo systemctl enable printer-server"
echo "  sudo systemctl start printer-server"
echo ""
echo -e "${YELLOW}▸ To check server status:${NC}"
echo "  curl http://localhost:3006/health"
echo ""

# Ask to start server now
read -p "Start server now? (y/n): " start_choice
if [[ "$start_choice" == "y" || "$start_choice" == "Y" ]]; then
    echo ""
    echo -e "${GREEN}Starting server...${NC}"
    cd "$INSTALL_DIR"
    ./start_server.sh
else
    echo -e "${BLUE}Setup complete! Run './start_server.sh' when ready.${NC}"
fi

