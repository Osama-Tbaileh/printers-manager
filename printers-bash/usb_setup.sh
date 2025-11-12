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
LOGO_FILENAME="${LOGO_FILENAME:-BarakaOS_Logo.png}"

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
sudo apt install -y cups cups-client git python3 python3-pip python3-venv python3-dev build-essential lsof fonts-dejavu fonts-dejavu-core
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

# Check if port 3006 is in use and free it if needed
echo ""
echo -e "${YELLOW}Checking port $SERVER_PORT availability...${NC}"
PORT_PID=$(lsof -ti:$SERVER_PORT 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${YELLOW}⚠ Port $SERVER_PORT is in use by process $PORT_PID${NC}"
    PROCESS_NAME=$(ps -p $PORT_PID -o comm= 2>/dev/null)
    echo -e "${YELLOW}  Process: $PROCESS_NAME${NC}"
    echo -e "${YELLOW}  Stopping process to free the port...${NC}"
    kill -9 $PORT_PID 2>/dev/null
    sleep 2
    # Verify port is now free
    if lsof -ti:$SERVER_PORT >/dev/null 2>&1; then
        echo -e "${RED}✗ Failed to free port $SERVER_PORT${NC}"
        echo -e "${RED}  Please manually stop the process and try again${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Port $SERVER_PORT is now free${NC}"
    fi
else
    echo -e "${GREEN}✓ Port $SERVER_PORT is available${NC}"
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
# Get the correct local IP (prioritize 192.168.x.x and 10.x.x.x ranges)
LOCAL_IP=$(hostname -I | tr ' ' '\n' | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' | head -n1)
# Fallback to first IP if no private IP found
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NETWORK PRINTER DISCOVERY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo -e "${YELLOW}▸ Scanning for network printers...${NC}"
echo -e "${CYAN}  This may take up to 30 seconds...${NC}"

# Get local network subnet
LOCAL_IP=$(hostname -I | awk '{print $1}')
SUBNET=$(echo "$LOCAL_IP" | cut -d'.' -f1-3)

# Scan common printer ports (9100, 515, 631) on local network
echo -e "${CYAN}  Scanning subnet: ${SUBNET}.0/24${NC}"

DISCOVERED_PRINTERS=()
NEXT_PRINTER_NUM=1

# Quick scan using nmap if available, otherwise use nc
if command -v nmap &> /dev/null; then
    echo -e "${CYAN}  Using nmap for fast scanning...${NC}"
    # Scan for common printer ports
    SCAN_RESULTS=$(sudo nmap -p 9100,515,631 --open "$SUBNET.0/24" 2>/dev/null | grep -B 4 "open" | grep "Nmap scan report" | awk '{print $NF}' | tr -d '()')
else
    echo -e "${CYAN}  Using basic network scan (installing nmap recommended for faster scans)...${NC}"
    # Fallback: scan common IPs with netcat
    SCAN_RESULTS=""
    for i in {1..254}; do
        IP="$SUBNET.$i"
        # Quick check on port 9100 (most common for network printers)
        if timeout 0.2 bash -c "echo > /dev/tcp/$IP/9100" 2>/dev/null; then
            SCAN_RESULTS="$SCAN_RESULTS$IP\n"
        fi
    done
fi

# Get already configured printer URIs
EXISTING_URIS=$(lpstat -v 2>/dev/null | grep -oP 'device for \S+: \K.*' | sort -u)

# Process discovered printers
if [ ! -z "$SCAN_RESULTS" ]; then
    echo -e "${GREEN}✓ Found network printer(s)!${NC}"
    
    while IFS= read -r IP; do
        [ -z "$IP" ] && continue
        
        # Check if this IP is already configured
        IS_CONFIGURED=false
        while IFS= read -r uri; do
            if [[ "$uri" == *"$IP"* ]]; then
                IS_CONFIGURED=true
                break
            fi
        done <<< "$EXISTING_URIS"
        
        if [ "$IS_CONFIGURED" = false ]; then
            echo -e "${YELLOW}  ▸ New printer found at $IP${NC}"
            
            # Auto-configure with test name
            PRINTER_NAME="printer_$NEXT_PRINTER_NUM"
            PRINTER_URI="socket://$IP:9100"
            
            echo -e "${CYAN}    Adding as: $PRINTER_NAME${NC}"
            
            # Add printer to CUPS
            if sudo lpadmin -p "$PRINTER_NAME" -v "$PRINTER_URI" -E 2>/dev/null; then
                echo -e "${GREEN}    ✓ Printer configured successfully${NC}"
                DISCOVERED_PRINTERS+=("$PRINTER_NAME:$IP")
                NEXT_PRINTER_NUM=$((NEXT_PRINTER_NUM + 1))
            else
                echo -e "${RED}    ✗ Failed to configure printer${NC}"
            fi
        else
            echo -e "${CYAN}  ▸ Printer at $IP already configured${NC}"
        fi
    done <<< "$(echo -e "$SCAN_RESULTS")"
else
    echo -e "${YELLOW}⚠ No new network printers discovered${NC}"
fi

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST ALL CONFIGURED PRINTERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo -e "${YELLOW}▸ Testing all configured printers...${NC}"
CONFIGURED_PRINTERS=$(lpstat -p 2>/dev/null | awk '{print $2}')
if [ -z "$CONFIGURED_PRINTERS" ]; then
    echo -e "${YELLOW}⚠ No printers configured yet${NC}"
    echo "You can add printers with: sudo lpadmin -p PrinterName -v socket://IP:9100 -E"
else
    PRINTER_COUNT=$(echo "$CONFIGURED_PRINTERS" | wc -l)
    echo -e "${CYAN}Found $PRINTER_COUNT printer(s) configured${NC}"
    
    # Group printers by physical device (URI)
    declare -A PRINTER_GROUPS
    declare -A PRINTER_URIS
    
    while IFS= read -r printer; do
        PRINTER_URI=$(lpstat -v "$printer" 2>/dev/null | grep -oP 'device for \S+: \K.*' || echo "unknown")
        # Store printer names grouped by URI
        if [ -n "${PRINTER_GROUPS[$PRINTER_URI]}" ]; then
            PRINTER_GROUPS[$PRINTER_URI]="${PRINTER_GROUPS[$PRINTER_URI]}, $printer"
        else
            PRINTER_GROUPS[$PRINTER_URI]="$printer"
            PRINTER_URIS[$PRINTER_URI]="$PRINTER_URI"
        fi
    done <<< "$CONFIGURED_PRINTERS"
    
    PHYSICAL_PRINTER_COUNT=${#PRINTER_GROUPS[@]}
    echo -e "${CYAN}Grouped into $PHYSICAL_PRINTER_COUNT physical printer(s)${NC}"
    echo -e "${CYAN}Sending test print to each physical printer...${NC}"
    echo ""
    
    # Test each physical printer (unique URI)
    WORKING_PRINTERS=0
    FAILED_PRINTERS=0
    
    for uri in "${!PRINTER_GROUPS[@]}"; do
        PRINTER_NAMES="${PRINTER_GROUPS[$uri]}"
        FIRST_PRINTER=$(echo "$PRINTER_NAMES" | cut -d',' -f1 | xargs)
        
        echo -e "${YELLOW}  Testing physical printer: $uri${NC}"
        echo -e "${CYAN}    Assigned names: $PRINTER_NAMES${NC}"
        
        # Get printer IP and port from URI (simpler method without lookbehind)
        PRINTER_IP=$(echo "$uri" | sed -n 's/.*:\/\/\([0-9.]*\).*/\1/p')
        if [ -z "$PRINTER_IP" ]; then
            PRINTER_IP="unknown"
        fi
        PRINTER_PORT=$(echo "$uri" | sed -n 's/.*:\([0-9]*\)$/\1/p')
        if [ -z "$PRINTER_PORT" ]; then
            PRINTER_PORT="9100"
        fi
        
        # Count how many names are assigned
        NAME_COUNT=$(echo "$PRINTER_NAMES" | tr ',' '\n' | wc -l)
        
        # Create a Python script to generate the receipt image
        # Use timestamp to avoid conflicts with invalid characters
        TEMP_IMAGE="/tmp/printer_test_$(date +%s)_${RANDOM}.png"
        
        # Generate receipt image using Python
        $PYTHON_CMD << EOF
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

# Create image (576px width for 80mm thermal printer)
width = 576
height = 1600
img = Image.new('RGB', (width, height), 'white')
draw = ImageDraw.Draw(img)

# Use default font
try:
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except:
    title_font = header_font = normal_font = small_font = ImageFont.load_default()

y = 20
padding = 20

# Try to load company logo
logo_path = "$INSTALL_DIR/$LOGO_FILENAME"
if os.path.exists(logo_path):
    try:
        logo = Image.open(logo_path)
        # Resize logo to fit width (max 400px wide)
        logo_max_width = 400
        if logo.width > logo_max_width:
            ratio = logo_max_width / logo.width
            new_height = int(logo.height * ratio)
            logo = logo.resize((logo_max_width, new_height), Image.Resampling.LANCZOS)
        
        # Center the logo
        logo_x = (width - logo.width) // 2
        # Convert to RGB if needed (for PNG with transparency)
        if logo.mode == 'RGBA':
            # Create white background
            logo_bg = Image.new('RGB', logo.size, 'white')
            logo_bg.paste(logo, mask=logo.split()[3])
            logo = logo_bg
        img.paste(logo, (logo_x, y))
        y += logo.height + 20
    except:
        pass  # If logo fails to load, just skip it

# Title
title = "PRINTER SERVER TEST"
bbox = draw.textbbox((0, 0), title, font=title_font)
title_width = bbox[2] - bbox[0]
draw.text(((width - title_width) // 2, y), title, fill='black', font=title_font)
y += 50

# Draw line
draw.line([(padding, y), (width - padding, y)], fill='black', width=2)
y += 20

# Server Information Section
draw.text((padding, y), "SERVER INFORMATION", fill='black', font=header_font)
y += 30

info_lines = [
    ("Server IP:", "$LOCAL_IP"),
    ("Server Port:", "$SERVER_PORT"),
    ("Hostname:", "$HOSTNAME"),
    ("Access URL:", "http://$LOCAL_IP:$SERVER_PORT"),
    ("Installation:", "$INSTALL_DIR"),
]

for label, value in info_lines:
    draw.text((padding, y), label, fill='black', font=normal_font)
    draw.text((padding + 150, y), value, fill='blue', font=normal_font)
    y += 25

y += 10
draw.line([(padding, y), (width - padding, y)], fill='black', width=2)
y += 20

# Printer Information Section
draw.text((padding, y), "PRINTER INFORMATION", fill='black', font=header_font)
y += 30

printer_lines = [
    ("Printer IP:", "$PRINTER_IP"),
    ("Printer Port:", "$PRINTER_PORT"),
    ("Assigned Names:", "$NAME_COUNT"),
]

for label, value in printer_lines:
    draw.text((padding, y), label, fill='black', font=normal_font)
    draw.text((padding + 150, y), str(value), fill='green', font=normal_font)
    y += 25

# Print assigned names (wrap if needed)
y += 5
names_text = "$PRINTER_NAMES"
wrapped_names = textwrap.fill(names_text, width=40)
for line in wrapped_names.split('\n'):
    draw.text((padding + 20, y), line, fill='black', font=small_font)
    y += 20

y += 10
draw.line([(padding, y), (width - padding, y)], fill='black', width=2)
y += 20

# Success message
success_msg = "✓ Printer is working correctly!"
bbox = draw.textbbox((0, 0), success_msg, font=header_font)
msg_width = bbox[2] - bbox[0]
draw.text(((width - msg_width) // 2, y), success_msg, fill='green', font=header_font)
y += 40

# Instructions
instructions = [
    "Use the Server IP and Port above",
    "to send print jobs via the API.",
    "",
    "You can use any of the assigned",
    "printer names listed above.",
]

for line in instructions:
    bbox = draw.textbbox((0, 0), line, font=small_font)
    line_width = bbox[2] - bbox[0]
    draw.text(((width - line_width) // 2, y), line, fill='black', font=small_font)
    y += 20

y += 10
draw.line([(padding, y), (width - padding, y)], fill='black', width=2)
y += 20

# Timestamp
timestamp = "$(date '+%Y-%m-%d %H:%M:%S')"
bbox = draw.textbbox((0, 0), timestamp, font=small_font)
ts_width = bbox[2] - bbox[0]
draw.text(((width - ts_width) // 2, y), timestamp, fill='gray', font=small_font)
y += 30

# Lovely closing message
y += 10
draw.line([(padding, y), (width - padding, y)], fill='black', width=2)
y += 25

# Success message
success_message = "Your printer has been successfully set up and is ready to use!"
bbox = draw.textbbox((0, 0), success_message, font=header_font)
msg_width = bbox[2] - bbox[0]
draw.text(((width - msg_width) // 2, y), success_message, fill='green', font=header_font)
y += 40

closing_messages = []

for line in closing_messages:
    bbox = draw.textbbox((0, 0), line, font=small_font)
    line_width = bbox[2] - bbox[0]
    # Add some color to special lines
    color = 'black'
    if '❤️' in line or '☕' in line or '🌟' in line:
        color = 'purple'
    elif 'awesome' in line or 'boss' in line or 'amazing' in line:
        color = 'blue'
    draw.text(((width - line_width) // 2, y), line, fill=color, font=small_font)
    y += 22

# Crop to actual content height
img = img.crop((0, 0, width, y + 30))

# Save image
img.save("$TEMP_IMAGE")
print("Image created: $TEMP_IMAGE")
EOF

        # Check if image was created successfully
        if [ -f "$TEMP_IMAGE" ]; then
            # Use the print_image_any.py script to send the image
            if $PYTHON_CMD "$INSTALL_DIR/print_image_any.py" "$TEMP_IMAGE" --max-width 576 --mode gsv0 --align center 2>/dev/null | lp -d "$FIRST_PRINTER" -o raw 2>/dev/null; then
                echo -e "${GREEN}    ✓ Successfully sent test print (image)${NC}"
                
                # Send beep command (3 beeps, 200ms each)
                sleep 1
                echo -e "${YELLOW}    ▸ Sending beep command...${NC}"
                if echo -en "\x1b\x42\x03\x05" | lp -d "$FIRST_PRINTER" -o raw 2>/dev/null; then
                    echo -e "${GREEN}    ✓ Beep command sent${NC}"
                else
                    echo -e "${YELLOW}    ⚠ Beep command sent but printer may not support it${NC}"
                fi
                
                # Send cut command (feed 3 lines then partial cut)
                sleep 1
                echo -e "${YELLOW}    ▸ Sending cut command...${NC}"
                if echo -en "\x1b\x64\x03\x1d\x56\x01" | lp -d "$FIRST_PRINTER" -o raw 2>/dev/null; then
                    echo -e "${GREEN}    ✓ Paper cut command sent${NC}"
                else
                    echo -e "${YELLOW}    ⚠ Cut command sent but printer may not support it${NC}"
                fi
                
                WORKING_PRINTERS=$((WORKING_PRINTERS + 1))
            else
                echo -e "${RED}    ✗ Failed to send test print${NC}"
                FAILED_PRINTERS=$((FAILED_PRINTERS + 1))
            fi
            # Clean up temp image
            rm -f "$TEMP_IMAGE"
        else
            echo -e "${RED}    ✗ Failed to generate test image${NC}"
            FAILED_PRINTERS=$((FAILED_PRINTERS + 1))
        fi
        echo ""
    done

    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Printer Test Results:${NC}"
    echo -e "${CYAN}  Physical Printers: $PHYSICAL_PRINTER_COUNT${NC}"
    echo -e "${GREEN}  ✓ Working: $WORKING_PRINTERS${NC}"
    if [ $FAILED_PRINTERS -gt 0 ]; then
        echo -e "${RED}  ✗ Failed: $FAILED_PRINTERS${NC}"
    fi
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

