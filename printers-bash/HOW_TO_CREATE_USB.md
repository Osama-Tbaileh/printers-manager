# 📀 How to Create the Auto-Setup USB Drive

Follow these steps to create your USB auto-setup drive.

---

## 📋 Step 1: Prepare Your GitHub Repository

### **1.1 Push Your Code to GitHub:**

```bash
# If not already a git repo, initialize it
cd C:\Users\IzTech-OTbaileh\Desktop\printers-manager
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Printer server with auto-setup"

# Create repository on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/printers-manager.git
git branch -M main
git push -u origin main
```

### **1.2 Make Sure These Files Are in the Repo:**
- ✅ `server.py`
- ✅ `print_image_any.py`
- ✅ `requirements.txt`
- ✅ All other server files

**Note:** Don't push the `venv/` folder or `uploads/` folder (add them to `.gitignore`)

---

## 📀 Step 2: Prepare the USB Drive

### **2.1 Format USB (Optional but Recommended):**
- Format as **FAT32** (works on all systems)
- Or **exFAT** (for larger files, works on modern systems)
- Label it something like: "PRINTER-SETUP"

### **2.2 Copy Files to USB:**

Copy these files from your project to the USB root:
```
USB Drive/
├── usb_setup.sh          ← Linux/RasPi setup script
├── usb_setup.bat         ← Windows setup script
├── USB_README.md         ← Full instructions
└── QUICK_SETUP.txt       ← Quick reference
```

**Files to copy:**
1. `usb_setup.sh`
2. `usb_setup.bat`
3. `USB_README.md`
4. `QUICK_SETUP.txt`

---

## ⚙️ Step 3: Configure the Scripts

### **3.1 Edit `usb_setup.sh`:**

Open `usb_setup.sh` on the USB and change line 23:
```bash
GITHUB_REPO="YOUR_GITHUB_USERNAME/printers-manager"
```

To your actual GitHub username, for example:
```bash
GITHUB_REPO="johndoe/printers-manager"
```

### **3.2 Edit `usb_setup.bat`:**

Open `usb_setup.bat` on the USB and change line 16:
```batch
set GITHUB_REPO=YOUR_GITHUB_USERNAME/printers-manager
```

To your actual GitHub username, for example:
```batch
set GITHUB_REPO=johndoe/printers-manager
```

---

## ✅ Step 4: Test the USB

### **4.1 Test on Raspberry Pi:**

1. Plug USB into Raspberry Pi
2. Open terminal
3. Navigate to USB (usually `/media/pi/PRINTER-SETUP` or similar)
4. Run:
   ```bash
   chmod +x usb_setup.sh
   ./usb_setup.sh
   ```
5. Follow the prompts
6. Verify server starts successfully

### **4.2 Test on Windows (Optional):**

1. Plug USB into Windows PC
2. Open USB folder in Explorer
3. Double-click `usb_setup.bat`
4. Follow the prompts

---

## 📁 Optional: Add Offline Backup

If you want to work **without internet** (no GitHub clone), you can:

### **Option A: Include the entire repo on USB:**
```
USB Drive/
├── usb_setup.sh
├── usb_setup.bat
├── USB_README.md
├── QUICK_SETUP.txt
└── printers-manager/         ← Full repo folder
    ├── server.py
    ├── print_image_any.py
    ├── requirements.txt
    └── ...
```

Then modify the setup scripts to copy from USB instead of cloning from GitHub.

### **Option B: Create offline setup script:**

Create `usb_setup_offline.sh`:
```bash
#!/bin/bash
echo "Installing from USB (offline mode)..."
INSTALL_DIR="$HOME/printer-server"
USB_DIR="$(dirname "$0")/printers-manager"

cp -r "$USB_DIR" "$INSTALL_DIR"
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Installation complete!"
```

---

## 🎯 Final USB Structure

### **Minimal (requires internet):**
```
USB Drive/
├── usb_setup.sh          (configured with your GitHub repo)
├── usb_setup.bat         (configured with your GitHub repo)
├── USB_README.md
└── QUICK_SETUP.txt
```

### **Full (works offline):**
```
USB Drive/
├── usb_setup.sh
├── usb_setup.bat
├── usb_setup_offline.sh  (optional)
├── USB_README.md
├── QUICK_SETUP.txt
└── printers-manager/     (entire repo)
    ├── server.py
    ├── print_image_any.py
    ├── requirements.txt
    ├── test_browser.html
    └── ...
```

---

## 🚀 You're Done!

Now you can:
1. ✅ Plug USB into any Raspberry Pi
2. ✅ Run one command
3. ✅ Server automatically sets up and runs!

**Perfect for deploying to multiple locations!** 🎉

---

## 💡 Pro Tips:

1. **Make multiple USBs** - Keep backups
2. **Test before deploying** - Always test the setup on a clean system
3. **Update regularly** - When you update the server, update GitHub and recreate USB
4. **Label clearly** - Label USB as "Printer Server Setup v1.0" etc.
5. **Include contact info** - Add a text file with support contact info

---

## 🔄 Updating the USB:

When you update your server:

1. Push changes to GitHub:
   ```bash
   git add .
   git commit -m "Updated server"
   git push
   ```

2. That's it! USB will pull latest version from GitHub

3. (Optional) Update files on USB if you changed the setup scripts

---

**Happy deploying!** 🚀

