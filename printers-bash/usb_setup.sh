#!/bin/bash
################################################################################
# USB Auto-Setup Script for Printer Server
# 
# This script will:
# 1. Update system packages
# 2. Install CUPS and dependencies
# 3. Clone the printer-manager repo from GitHub
# 4. Create a Python virtual environment
# 5. Install all requirements
# 6. Start the server automatically in background
# 7. Display server IP and port
#
# Usage: Just run this script after plugging in the USB!
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Load configuration from .env.setup if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env.setup" ]; then
    source "$SCRIPT_DIR/.env.setup"
fi

# Default Configuration
GITHUB_REPO="${GITHUB_REPO:-iztech-team/printers-manager}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/printer-server}"
SERVER_PORT="${SERVER_PORT:-3006}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUTHENTICATION SETUP (for private repos)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 
# For PUBLIC repos: No configuration needed
# For PRIVATE repos: Use .env.setup file (recommended)
#
# Create .env.setup file with:
#   GITHUB_TOKEN="ghp_your_token_here"
#
# Or set defaults below (not recommended - use .env.setup instead):
GITHUB_TOKEN="${GITHUB_TOKEN:-}"  # Leave empty, set in .env.setup
USE_SSH="${USE_SSH:-false}"       # Set to true for SSH authentication
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Build repository URL based on authentication method

if [ "$USE_SSH" = "true" ]; then
    REPO_URL="git@github.com:$GITHUB_REPO.git"
elif [ ! -z "$GITHUB_TOKEN" ]; then
    REPO_URL="https://$GITHUB_TOKEN@github.com/$GITHUB_REPO.git"
else
    REPO_URL="https://github.com/$GITHUB_REPO.git"
fi

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════╗"
echo "║   Printer Server - Auto Setup v2.0         ║"
echo "╔════════════════════════════════════════════╗"
echo -e "${NC}"

# Step 1: Update system
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
echo "This may take a few minutes..."
sudo apt update -qq
sudo apt upgrade -y -qq
echo -e "${GREEN}✓ System updated${NC}"

# Step 2: Install CUPS and dependencies
echo ""
echo -e "${YELLOW}[2/8] Installing CUPS and dependencies...${NC}"
sudo apt install -y cups cups-client git python3 python3-pip python3-venv python3-dev build-essential
echo -e "${GREEN}✓ CUPS installed${NC}"

# Start and enable CUPS service
sudo systemctl enable cups
sudo systemctl start cups
echo -e "${GREEN}✓ CUPS service started${NC}"

# Add current user to lpadmin group (for printer management)
sudo usermod -a -G lpadmin $USER
echo -e "${GREEN}✓ User added to lpadmin group${NC}"

# Step 3: Check for available dependencies
echo ""
echo -e "${YELLOW}[3/8] Verifying installation...${NC}"
if ! command -v git &> /dev/null; then
    echo -e "${RED}ERROR: git installation failed!${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 installation failed!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ All dependencies verified${NC}"

# Check Python version and upgrade if needed
echo ""
echo -e "${CYAN}Checking Python version...${NC}"
CURRENT_PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Current Python version: $CURRENT_PYTHON_VERSION"

# Extract major and minor version
PYTHON_MAJOR=$(echo $CURRENT_PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $CURRENT_PYTHON_VERSION | cut -d. -f2)

# Check if Python is less than 3.8 (minimum requirement)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${YELLOW}⚠ Python 3.8+ required for modern packages${NC}"
    echo -e "${YELLOW}Current version: $CURRENT_PYTHON_VERSION${NC}"
    echo ""
    echo -e "${YELLOW}Adding deadsnakes PPA for newer Python versions...${NC}"
    
    # Add deadsnakes PPA
    sudo apt install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update -qq
    
    echo -e "${GREEN}✓ PPA added${NC}"
    
    # Try to install the newest available Python (try 3.11, 3.10, 3.9, 3.8 in order)
    PYTHON_CMD=""
    for version in 3.11 3.10 3.9 3.8; do
        echo -e "${YELLOW}Trying to install Python $version...${NC}"
        if sudo apt install -y python$version python$version-venv python$version-dev 2>/dev/null; then
            if command -v python$version &> /dev/null; then
                PYTHON_CMD="python$version"
                echo -e "${GREEN}✓ Python $version installed successfully${NC}"
                echo "Python version: $(python$version --version)"
                break
            fi
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}ERROR: Failed to install any newer Python version${NC}"
        echo -e "${YELLOW}Attempting to continue with Python $CURRENT_PYTHON_VERSION...${NC}"
        echo -e "${RED}WARNING: Package installation will likely fail!${NC}"
        PYTHON_CMD="python3"
    fi
else
    PYTHON_CMD="python3"
    echo -e "${GREEN}✓ Python version is sufficient ($CURRENT_PYTHON_VERSION)${NC}"
fi

# Step 4: Setup installation directory
echo ""
echo -e "${YELLOW}[4/8] Setting up installation directory...${NC}"
echo "Installation path: $INSTALL_DIR"

# Remove old installation if exists
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Removing old installation...${NC}"
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Old installation removed${NC}"
fi

# Step 5: Clone repository
echo ""
echo -e "${YELLOW}[5/8] Cloning repository from GitHub...${NC}"
# Don't print the URL if it contains a token (security)
if [ ! -z "$GITHUB_TOKEN" ]; then
    echo "Repository: https://***TOKEN***@github.com/$GITHUB_REPO.git"
else
    echo "Repository: $REPO_URL"
fi

# Clone the repository
if git clone "$REPO_URL" "$INSTALL_DIR" 2>&1; then
    # Verify the clone actually succeeded
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${GREEN}✓ Repository cloned successfully${NC}"
    else
        echo -e "${RED}ERROR: Repository clone failed!${NC}"
        echo "The directory was not created. Please check:"
        echo "  1. Your internet connection"
        echo "  2. Repository name: $GITHUB_REPO"
        echo "  3. If private, check your GITHUB_TOKEN in .env.setup"
        echo "  4. Token must start with 'ghp_' (lowercase)"
        exit 1
    fi
else
    echo -e "${RED}ERROR: Failed to clone repository!${NC}"
    echo "Please check:"
    echo "  1. Your internet connection"
    echo "  2. Repository name: $GITHUB_REPO"
    echo "  3. If private, check your GITHUB_TOKEN in .env.setup"
    echo "  4. Token format must be: ghp_xxxxxxxxxxxx (lowercase 'ghp_')"
    echo "  5. Generate token at: https://github.com/settings/tokens"
    exit 1
fi

# Step 6: Create virtual environment
echo ""
echo -e "${YELLOW}[6/8] Creating Python virtual environment...${NC}"
cd "$INSTALL_DIR"
$PYTHON_CMD -m venv venv
echo -e "${GREEN}✓ Virtual environment created${NC}"

# Step 7: Install requirements
echo ""
echo -e "${YELLOW}[7/8] Installing Python packages...${NC}"
source venv/bin/activate
pip install --upgrade pip -qq
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -qq
    echo -e "${GREEN}✓ All packages installed${NC}"
else
    echo -e "${RED}WARNING: requirements.txt not found!${NC}"
fi

# Create .env file if it doesn't exist (optional - uses defaults if not present)
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo ""
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
fi

# Step 8: Detect available printers
echo ""
echo -e "${YELLOW}[8/8] Detecting network printers...${NC}"
echo "Scanning network for printers..."

# Scan for network printers (this will find printers via mDNS/Bonjour)
PRINTERS_FOUND=$(lpinfo -v 2>/dev/null | grep -i "socket\|network" | wc -l || echo "0")

if [ "$PRINTERS_FOUND" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $PRINTERS_FOUND network printer(s)${NC}"
    lpinfo -v 2>/dev/null | grep -i "socket\|network" | while read line; do
        echo -e "${CYAN}  → $line${NC}"
    done
else
    echo -e "${YELLOW}⚠ No network printers detected${NC}"
    echo "You can add printers manually later with:"
    echo "  sudo lpadmin -p PrinterName -v socket://IP_ADDRESS:9100 -E"
fi

# Create start script
cat > start_server.sh << EOF
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
python server.py
EOF
chmod +x start_server.sh

# Create stop script
cat > stop_server.sh << EOF
#!/bin/bash
PID=\$(pgrep -f "python.*server.py")
if [ ! -z "\$PID" ]; then
    kill \$PID
    echo "Server stopped (PID: \$PID)"
else
    echo "Server is not running"
fi
EOF
chmod +x stop_server.sh

# Create systemd service with git pull before start
cat > printer-server.service << EOF
[Unit]
Description=Printer Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStartPre=/usr/bin/git pull origin main
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Install systemd service
echo ""
echo -e "${YELLOW}▸ Installing systemd service for auto-start on boot...${NC}"
sudo cp printer-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printer-server
echo -e "${GREEN}✓ Service installed and enabled${NC}"

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔════════════════════════════════════════════╗"
echo "║      Installation Complete! ✓             ║"
echo "╔════════════════════════════════════════════╗"
echo -e "${NC}"

# Get network information
echo ""
echo -e "${CYAN}${BOLD}📡 Getting network information...${NC}"
HOSTNAME=$(hostname)
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${YELLOW}▸ Starting server via systemd service...${NC}"
cd "$INSTALL_DIR"
sudo systemctl start printer-server

# Wait for service to start
sleep 3

# Check service status
if systemctl is-active --quiet printer-server; then
    SERVER_PID=$(systemctl show -p MainPID --value printer-server)
    echo -e "${GREEN}✓ Server started successfully via systemd (PID: $SERVER_PID)${NC}"
    echo -e "${GREEN}✓ Service will auto-start on boot${NC}"
else
    echo -e "${RED}✗ Service failed to start. Checking logs...${NC}"
    sudo journalctl -u printer-server -n 20 --no-pager
    exit 1
fi

# Display server information
echo ""
echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║         🖨️  SERVER IS RUNNING! 🖨️          ║${NC}"
echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════╗${NC}"
echo ""
echo -e "${CYAN}${BOLD}📍 Server Access Information:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}  Hostname:${NC}        $HOSTNAME"
echo -e "${YELLOW}  Local IP:${NC}        ${GREEN}${BOLD}$LOCAL_IP${NC}"
echo -e "${YELLOW}  Port:${NC}            ${GREEN}${BOLD}$SERVER_PORT${NC}"
echo -e "${YELLOW}  Python:${NC}          ${GREEN}${BOLD}$($PYTHON_CMD --version | awk '{print $2}')${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}${BOLD}🌐 Access URLs:${NC}"
echo ""
echo -e "${YELLOW}  Local access:${NC}"
echo -e "    ${CYAN}http://localhost:$SERVER_PORT${NC}"
echo ""
echo -e "${YELLOW}  From other devices (same network):${NC}"
echo -e "    ${CYAN}${BOLD}http://$LOCAL_IP:$SERVER_PORT${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}${BOLD}🧪 Quick Tests:${NC}"
echo ""
echo -e "  ${YELLOW}Health check:${NC}"
echo -e "    curl http://localhost:$SERVER_PORT/health"
echo ""
echo -e "  ${YELLOW}From phone/tablet:${NC}"
echo -e "    Open browser: ${CYAN}http://$LOCAL_IP:$SERVER_PORT/health${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}${BOLD}🔧 Service Management Commands:${NC}"
echo ""
echo -e "  ${YELLOW}Check service status:${NC}"
echo -e "    sudo systemctl status printer-server"
echo ""
echo -e "  ${YELLOW}View live logs:${NC}"
echo -e "    sudo journalctl -u printer-server -f"
echo ""
echo -e "  ${YELLOW}Stop server:${NC}"
echo -e "    sudo systemctl stop printer-server"
echo ""
echo -e "  ${YELLOW}Restart server:${NC}"
echo -e "    sudo systemctl restart printer-server"
echo ""
echo -e "  ${YELLOW}Disable auto-start on boot:${NC}"
echo -e "    sudo systemctl disable printer-server"
echo ""
echo -e "  ${YELLOW}Re-enable auto-start on boot:${NC}"
echo -e "    sudo systemctl enable printer-server"
echo ""
echo -e "  ${GREEN}✓ Server is configured to auto-start on boot!${NC}"
echo -e "  ${GREEN}✓ Server auto-updates from GitHub on every restart!${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}${BOLD}📋 Available Printers:${NC}"
echo ""
lpstat -p 2>/dev/null || echo -e "${YELLOW}  No printers configured yet.${NC}"
echo ""
echo -e "  ${YELLOW}To add a printer:${NC}"
echo -e "    sudo lpadmin -p PrinterName -v socket://192.168.1.X:9100 -E"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}${BOLD}✨ Installation Directory: ${CYAN}$INSTALL_DIR${NC}"
echo ""
echo -e "${GREEN}${BOLD}🎉 Setup complete! Server is running in the background!${NC}"
echo ""

