# 🔌 USB Auto-Setup for Printer Server v2.0

This USB drive contains everything needed to automatically set up the printer server on any Raspberry Pi!

---

## ⚡ Quick Start (TL;DR)

```bash
# 1. Plug in USB
# 2. Navigate to USB
cd /media/pi/USB_NAME

# 3. Run setup
chmod +x usb_setup.sh
sudo ./usb_setup.sh

# 4. Wait 5-10 minutes ☕
# 5. Done! Server auto-starts and displays IP & API key
```

**Before first use:** Edit `GITHUB_REPO` in `usb_setup.sh` (line 35) or create `.env.setup` file.

---

## 📋 What This USB Does (FULLY AUTOMATED):

When you run the setup script, it will:
1. ✅ **Update entire system** (apt update && upgrade)
2. ✅ **Install CUPS printing system** (auto-configured)
3. ✅ **Check Python version** and upgrade to 3.11+ if needed
4. ✅ **Clone repository** from GitHub
5. ✅ **Create Python virtual environment** (with correct Python version)
6. ✅ **Install all required packages**
7. ✅ **Generate secure API key** automatically
8. ✅ **Detect network printers** automatically
9. ✅ **Install systemd service** for auto-start on boot
10. ✅ **Configure auto-updates** from GitHub on every restart
11. ✅ **Start server immediately** via systemd
12. ✅ **Display API key and access URLs**

**100% Automatic - No user input required!**
**Server auto-starts on every reboot!** 🔄
**Server auto-updates from GitHub on every restart!** 🔄
**Python auto-upgrades to 3.11+ if your system is older!** 🔄

---

## 🚀 Quick Start Guide

### **For Raspberry Pi / Linux:**

1. **Plug in the USB drive**

2. **Open terminal and navigate to USB:**
   ```bash
   cd /media/pi/USB_NAME/printers-bash
   # or wherever your USB is mounted
   ```

3. **Run the setup script (requires sudo for system updates):**
   ```bash
   chmod +x usb_setup.sh
   sudo ./usb_setup.sh
   ```

4. **Wait 5-10 minutes** ☕ - The script will:
   - Update your entire system
   - Install CUPS and all dependencies
   - Download and configure the server
   - Start the server automatically
   - Show you the IP address and port!

5. **Done!** The script displays:
   ```
   🌐 Access URLs:
     From other devices (same network):
       http://192.168.1.100:3006
   ```
   Use this URL on your client devices!

---

## ⚙️ Configuration (Optional)

### **Option 1: Use .env.setup file (Recommended)**

Create a `.env.setup` file in the `printers-bash/` directory:

```bash
# Copy the example file
cp .env.setup.example .env.setup

# Edit with your settings
nano .env.setup
```

**.env.setup contents:**
```bash
# GitHub repository (format: username/repository)
GITHUB_REPO=YOUR_GITHUB_USERNAME/printers-manager

# GitHub token for private repos (leave empty for public repos)
GITHUB_TOKEN=

# Installation directory
INSTALL_DIR=$HOME/printer-server
```

### **Option 2: Edit usb_setup.sh directly**

If you don't create `.env.setup`, you can edit the script defaults (line 35):

```bash
GITHUB_REPO="YOUR_GITHUB_USERNAME/printers-manager"
```

---

### **For PRIVATE Repositories:**

Add your GitHub Personal Access Token to `.env.setup`:

1. **Create a GitHub Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Give it a name like "Printer Server USB Setup"
   - Select scope: ✅ **repo** (Full control of private repositories)
   - Click "Generate token"
   - **Copy the token** (starts with `ghp_...`)

2. **Add token to .env.setup:**
   ```bash
   GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

3. **Done!** The script will now clone your private repo.

---

### **For PUBLIC Repositories:**

No authentication needed! Just set your `GITHUB_REPO` and you're good to go.

---

## 📝 What Gets Installed:

### **Files from GitHub (cloned automatically):**
```
~/printer-server/
├── server.py                     ← Main FastAPI server
├── print_image_any.py           ← Image converter/printer script
├── requirements.txt             ← Python dependencies list
├── .env.example                 ← Configuration template
├── README.md                    ← Project documentation
└── .gitignore                   ← Git ignore rules
```

### **Files created by setup script:**
```
~/printer-server/
├── .env                         ← Server config (auto-generated with API key)
├── venv/                        ← Python virtual environment
├── start_server.sh              ← Manual start script
├── stop_server.sh               ← Manual stop script
└── printer-server.service       ← Systemd service file (copied to /etc/systemd/system/)
```

### **Folders created at runtime:**
```
~/printer-server/
└── uploads/                     ← Temporary image storage (auto-created, auto-cleaned)
```

---

## 🎯 After Installation:

### **Server is Already Running!**
The setup script automatically:
- ✅ Generates a secure API key
- ✅ Installs the systemd service
- ✅ Enables auto-start on boot
- ✅ Configures auto-updates from GitHub
- ✅ Starts the server immediately

### **Manage the Server (Using systemd):**

**Check service status:**
```bash
sudo systemctl status printer-server
```

**View live logs:**
```bash
sudo journalctl -u printer-server -f
```

**Stop server:**
```bash
sudo systemctl stop printer-server
```

**Restart server:**
```bash
sudo systemctl restart printer-server
```

**Disable auto-start on boot:**
```bash
sudo systemctl disable printer-server
```

**Re-enable auto-start:**
```bash
sudo systemctl enable printer-server
```

**Test Server API:**

You'll need the API key that was displayed during setup. Check the `.env` file:
```bash
cat ~/printer-server/.env
```

Then test with the API key:
```bash
curl -H "X-API-Key: YOUR_API_KEY_HERE" http://localhost:3006/health
```

Should return: `{"ok":true}`

---

## 🖨️ Configure Printers:

### **Automatic Detection:**
The setup script automatically scans for network printers using CUPS. If printers are found, they'll be displayed during setup.

### **Manual Printer Addition:**
Add printers to the system:
```bash
sudo lpadmin -p Kitchen_Printer -v socket://192.168.1.87:9100 -E
sudo lpadmin -p Counter_Printer -v socket://192.168.1.88:9100 -E
sudo lpadmin -p Office_Printer -v socket://192.168.1.105:9100 -E
```

### **List Available Printers:**
```bash
lpstat -p
```

### **Check Detected Network Printers:**
```bash
lpinfo -v
```

---

## 🧪 Test the Server:

**First, get your API key:**
```bash
grep API_KEY ~/printer-server/.env
```

### **Health Check:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:3006/health
```

### **Print Text:**
```bash
curl -X POST "http://localhost:3006/print-text?printer=Kitchen_Printer&cut=true" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from USB setup!"}'
```

### **Beep:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:3006/beep?printer=Kitchen_Printer&count=2"
```

---

## 📦 What's on This USB:

| File | Purpose |
|------|---------|
| `usb_setup.sh` | Linux/Raspberry Pi setup script |
| `.env.setup.example` | Configuration template (optional) |
| `USB_README.md` | This file - complete documentation |

---

## 🔧 Requirements:

### **Raspberry Pi / Linux:**
- **Internet connection** (to clone from GitHub and update system)
- **Sudo access** (script will install everything else automatically)

**The script automatically installs/upgrades:**
- ✅ Git
- ✅ **Python 3.11+** (automatically upgrades from older versions)
- ✅ Python pip + venv
- ✅ CUPS (printing system)
- ✅ All Python packages (FastAPI, Pillow, etc.)
- ✅ System updates

**Note:** If your Raspberry Pi has Python 3.6, 3.7, 3.8, 3.9, or 3.10, the script will automatically install Python 3.11 alongside it and use it for the server.

---

## ❓ Troubleshooting:

### **Script requires sudo password**
The script needs sudo access to:
- Update system packages
- Install CUPS and dependencies
- Add user to lpadmin group

### **"Failed to clone repository"**
- Check internet connection
- Verify GitHub repo URL is correct in `.env.setup` or script (line 35)
- For private repos, make sure `GITHUB_TOKEN` is set in `.env.setup`
- Make sure repository exists and you have access

### **Server not accessible from other devices**
- Check firewall settings: `sudo ufw allow 3006`
- Verify devices are on same network
- Use the IP address displayed by the script

### **"Cannot find printer"**
- Make sure printer is powered on
- Check printer IP address is correct
- Verify printer is on the same network
- Add printer manually: `sudo lpadmin -p PrinterName -v socket://IP:9100 -E`

### **View server logs**
```bash
sudo journalctl -u printer-server -f
```

### **Check API key**
```bash
cat ~/printer-server/.env | grep API_KEY
```

### **Python version errors (package installation fails)**
If you see errors like "No matching distribution found for fastapi==0.115.0":

1. **Check Python version:**
   ```bash
   python3 --version
   ```

2. **The script should have installed Python 3.11 automatically**
   ```bash
   python3.11 --version
   ```

3. **If Python 3.11 is installed but packages still fail:**
   - Remove the installation directory: `rm -rf ~/printer-server`
   - Run the setup script again: `sudo ./usb_setup.sh`

4. **Old Python versions and compatibility:**
   - Python 3.6 or older: ❌ Not supported
   - Python 3.7 - 3.10: ⚠️ Script auto-installs Python 3.11
   - Python 3.11+: ✅ Fully supported

---

## 🎉 Success!

Once setup is complete:
- ✅ **Server is running** as systemd service
- ✅ **Auto-starts on boot** (systemd enabled)
- ✅ **Auto-updates from GitHub** on every restart
- ✅ **Python 3.11+** installed and configured
- ✅ **API key generated** and displayed
- ✅ **IP address displayed** on screen
- ✅ **CUPS configured** and ready
- ✅ **All dependencies installed**

Your server will be running at:
- **Local:** http://localhost:3006
- **Network:** http://YOUR_IP:3006 (shown by script)

**Important:** Save the API key displayed during setup! You'll need it for all API requests.

**Reboot the Raspberry Pi - server will start automatically and pull latest updates!** 🔄

Send print commands from any device on the same network using the API key!

---

## 📀 How to Create This USB Drive

### **Step 1: Prepare Your GitHub Repository**

1. **Push your code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Printer server"
   git remote add origin https://github.com/YOUR_USERNAME/printers-manager.git
   git branch -M main
   git push -u origin main
   ```

2. **Make sure these files are in the repo:**
   - ✅ `server.py` - Main FastAPI server
   - ✅ `print_image_any.py` - Image converter script
   - ✅ `requirements.txt` - Python dependencies
   - ✅ `.env.example` - Configuration template
   - ✅ `README.md` - Project documentation
   - ✅ `.gitignore` - Prevents committing secrets

3. **Files that should NOT be pushed** (already in `.gitignore`):
   - ❌ `venv/` - Virtual environment
   - ❌ `uploads/` - Temporary files
   - ❌ `.env` - Contains secrets (API key)
   - ❌ `printers-bash/.env.setup` - Contains GitHub token

### **Step 2: Prepare the USB Drive**

1. **Format USB** (optional but recommended):
   - Format as **FAT32** or **exFAT**
   - Label it: "PRINTER-SETUP"

2. **Copy these files from `printers-bash/` directory to USB:**
   ```
   USB Drive/
   ├── usb_setup.sh          ← Main setup script
   ├── USB_README.md         ← This documentation
   └── .env.setup.example    ← Configuration template (optional)
   ```

### **Step 3: Configure for Your Repo**

**Option 1: Create .env.setup file (Recommended)**
```bash
cp .env.setup.example .env.setup
nano .env.setup
```

**Option 2: Edit usb_setup.sh directly**
Edit line 35 in `usb_setup.sh`:
```bash
GITHUB_REPO="YOUR_USERNAME/printers-manager"
```

### **Step 4: Test**
Plug USB into Raspberry Pi and run `sudo ./usb_setup.sh`

### **Updating the USB**

When you update your server:
1. Push changes to GitHub: `git push`
2. That's it! The USB will pull the latest code automatically
3. Only update USB files if you changed the setup script itself

---

## 🆘 Need Help?

Check the full documentation in the repository or contact support.

**Happy Printing!** 🖨️✨

