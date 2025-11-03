# 🔐 Private Repository Setup Guide

## If Your GitHub Repo is Private

The script supports **two methods** for accessing private repositories:

---

## 🔑 Method 1: Personal Access Token (Recommended)

**Best for USB setup** - Token is stored in the script.

### Step 1: Generate GitHub Token

1. Go to: **https://github.com/settings/tokens**
2. Click **"Generate new token (classic)"**
3. Settings:
   - **Name:** `Printer Server USB Setup`
   - **Expiration:** Choose duration (or "No expiration" for USB)
   - **Scopes:** ✅ Check **`repo`** (Full control of private repositories)
4. Click **"Generate token"**
5. **Copy the token!** (starts with `ghp_...`)
   - ⚠️ Save it somewhere safe - you won't see it again!

### Step 2: Add Token to Script

Edit `usb_setup.sh` **line 44:**

```bash
GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Replace with your actual token.

### Step 3: Done!

The script will now clone your private repo automatically!

**Example:**
```bash
GITHUB_REPO="omarherbawi1/printers-manager"
GITHUB_TOKEN="ghp_1234567890abcdefghijklmnopqrstuvwxyz"
```

---

## 🔐 Method 2: SSH Keys

**Best if SSH key already exists** on the Raspberry Pi.

### Step 1: Generate SSH Key (if not exists)

On the Raspberry Pi:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter for default location
# Press Enter for no passphrase (or set one)
```

### Step 2: Add SSH Key to GitHub

```bash
# Display your public key
cat ~/.ssh/id_ed25519.pub
```

1. Copy the output
2. Go to: **https://github.com/settings/keys**
3. Click **"New SSH key"**
4. Paste the key
5. Click **"Add SSH key"**

### Step 3: Configure Script

Edit `usb_setup.sh` **line 48:**

```bash
USE_SSH=true
```

### Step 4: Test Connection

```bash
ssh -T git@github.com
# Should say: "Hi username! You've successfully authenticated..."
```

---

## 📊 Comparison

| Feature | Personal Access Token | SSH Keys |
|---------|----------------------|----------|
| **Ease of setup** | ⭐⭐⭐ Easy | ⭐⭐ Medium |
| **USB portability** | ✅ Excellent | ❌ Requires key on device |
| **Security** | ⚠️ Token in script | ✅ Key not in script |
| **Best for** | USB deployment | Pre-configured devices |

---

## 🔒 Security Notes

### For Personal Access Tokens:
- ⚠️ **Token is visible in the script file!**
- Don't share the USB with untrusted people
- Use token with minimal permissions (just `repo` scope)
- Set expiration date if possible
- You can revoke token anytime at: https://github.com/settings/tokens

### For SSH Keys:
- ✅ More secure - key never leaves the device
- ❌ Requires SSH key on every Raspberry Pi
- Can be passphrase-protected

---

## 🧪 Testing

After configuration, test the clone manually:

**With Token:**
```bash
git clone https://YOUR_TOKEN@github.com/username/repo.git test-clone
```

**With SSH:**
```bash
git clone git@github.com:username/repo.git test-clone
```

If it works, the script will work!

---

## ❓ Troubleshooting

### "Authentication failed"
- **Token method:** Check token has `repo` scope and is not expired
- **SSH method:** Run `ssh -T git@github.com` to test connection

### "Repository not found"
- Check `GITHUB_REPO` format: `username/repo-name`
- Verify you have access to the repository
- Make sure repository exists

### "Permission denied (publickey)"
- SSH key not added to GitHub
- SSH key not on the device
- Use `ssh-add ~/.ssh/id_ed25519` to add key

---

## 🚀 Recommendation

**For USB Setup:** Use **Personal Access Token** method
- Easier to deploy to multiple devices
- No SSH key management needed
- Works immediately after copying USB files

**For Production:** Consider **SSH Keys**
- More secure
- No token exposure
- Better for long-term deployments

---

**Need help?** Check the main `USB_README.md` file!

