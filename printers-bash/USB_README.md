# 🔌 USB Auto-Setup for Printer Server v2.0

This USB drive contains everything needed to automatically set up the printer server on any Raspberry Pi!

---

## 📋 What This USB Does (FULLY AUTOMATED):

When you run the setup script, it will:
1. ✅ **Update entire system** (apt update && upgrade)
2. ✅ **Install CUPS printing system** (auto-configured)
3. ✅ **Clone repository** from GitHub
4. ✅ **Create Python virtual environment**
5. ✅ **Install all required packages**
6. ✅ **Detect network printers** automatically
7. ✅ **Install systemd service** for auto-start on boot
8. ✅ **Start server immediately** via systemd
9. ✅ **Display IP address and port** for client devices

**100% Automatic - No user input required!**
**Server auto-starts on every reboot!** 🔄

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

### **For Windows:**

1. **Plug in the USB drive**

2. **Open the USB folder in File Explorer**

3. **Double-click: `usb_setup.bat`**

4. **Follow the prompts!** ☕

---

## ⚙️ Configuration Required

### **Before First Use:**

You need to update the GitHub repository URL in the setup scripts:

#### **In `usb_setup.sh` (line 29):**
```bash
GITHUB_REPO="YOUR_GITHUB_USERNAME/printers-manager"
```
Change to your actual GitHub username/organization.

---

### **For PRIVATE Repositories:**

If your repository is private, you need to add authentication:

#### **Method 1: Personal Access Token (Recommended for USB)** 🔑

1. **Create a GitHub Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Give it a name like "Printer Server USB Setup"
   - Select scope: ✅ **repo** (Full control of private repositories)
   - Click "Generate token"
   - **Copy the token** (starts with `ghp_...`)

2. **Add token to script (line 44):**
   ```bash
   GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
   Replace with your actual token.

3. **Done!** The script will now clone your private repo.

#### **Method 2: SSH Keys** 🔐

If you prefer SSH (requires SSH key already on Raspberry Pi):

1. **Set in script (line 48):**
   ```bash
   USE_SSH=true
   ```

2. **Make sure SSH key is configured:**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   cat ~/.ssh/id_ed25519.pub  # Copy this
   # Add to GitHub: Settings → SSH Keys → New SSH Key
   ```

---

### **For PUBLIC Repositories:**

No changes needed! Leave `GITHUB_TOKEN=""` empty.

---

## 📝 What Gets Installed:

```
~/printer-server/                 (or custom location)
├── server.py                     ← Main FastAPI server
├── print_image_any.py           ← Image converter
├── requirements.txt             ← Python packages
├── venv/                        ← Virtual environment
├── uploads/                     ← Image uploads folder
├── start_server.sh              ← Easy start script
├── printer_config.txt           ← Your printer IPs
└── printer-server.service       ← Systemd service file
```

---

## 🎯 After Installation:

### **Server is Already Running!**
The setup script automatically:
- ✅ Installs the systemd service
- ✅ Enables auto-start on boot
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
```bash
curl http://localhost:3006/health
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

### **Health Check:**
```bash
curl http://localhost:3006/health
```

### **Print Text:**
```bash
curl -X POST "http://localhost:3006/print-text?printer=Kitchen_Printer&cut=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from USB setup!"}'
```

### **Beep:**
```bash
curl "http://localhost:3006/beep?printer=Kitchen_Printer&count=2"
```

---

## 📦 What's on This USB:

| File | Purpose |
|------|---------|
| `usb_setup.sh` | Linux/Raspberry Pi setup script |
| `usb_setup.bat` | Windows setup script |
| `USB_README.md` | This file - instructions |
| `QUICK_SETUP.txt` | Ultra-quick reference |

---

## 🔧 Requirements:

### **Raspberry Pi / Linux:**
- **Internet connection** (to clone from GitHub and update system)
- **Sudo access** (script will install everything else automatically)

**The script automatically installs:**
- ✅ Git
- ✅ Python 3 + pip + venv
- ✅ CUPS (printing system)
- ✅ All Python packages
- ✅ System updates

### **Windows:**
- Git: https://git-scm.com/download/win
- Python: https://www.python.org/downloads/
- Internet connection

---

## ❓ Troubleshooting:

### **Script requires sudo password**
The script needs sudo access to:
- Update system packages
- Install CUPS and dependencies
- Add user to lpadmin group

### **"Failed to clone repository"**
- Check internet connection
- Verify GitHub repo URL is correct in script (line 29)
- Make sure repository is public or you have access

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
tail -f ~/printer-server/server.log
```

---

## 🎉 Success!

Once setup is complete:
- ✅ **Server is running** as systemd service
- ✅ **Auto-starts on boot** (systemd enabled)
- ✅ **IP address displayed** on screen
- ✅ **CUPS configured** and ready
- ✅ **All dependencies installed**

Your server will be running at:
- **Local:** http://localhost:3006
- **Network:** http://YOUR_IP:3006 (shown by script)

**Reboot the Raspberry Pi - server will start automatically!** 🔄

Send print commands from any device on the same network!

---

## 🆘 Need Help?

Check the full documentation in the repository or contact support.

**Happy Printing!** 🖨️✨

