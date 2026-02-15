# Client Setup Guide - Print Queue Manager

Simple guide for end users to add the print queue to their computers.

---

## 🪟 Windows (10/11)

### Method 1: Add Printer (Recommended)

1. Click **Start** → **Settings** ⚙️
2. Go to **Bluetooth & devices** → **Printers & scanners**
3. Click **Add device** or **Add a printer or scanner**
4. Click **"The printer that I want isn't listed"**
5. Select **"Select a shared printer by name"**
6. Enter: `http://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515`
   - Replace `PRINT-SERVER-IP` with your actual server IP (e.g., `192.168.1.100`)
7. Click **Next**
8. Windows will install drivers automatically
9. Set as default printer if desired

### Method 2: PowerShell (Admin Users)

```powershell
# Open PowerShell as Administrator
# Replace 192.168.1.100 with your server IP

Add-Printer -Name "Print Queue" -ConnectionName "http://192.168.1.100:631/printers/HP_Smart_Tank_515"
```

### How to Print

1. Print from any application (Ctrl+P)
2. Select "Print Queue" or "HP_Smart_Tank_515"
3. Click Print
4. Open browser: `http://PRINT-SERVER-IP:5000`
5. Login with your credentials
6. Find your job and click **Release**
7. Your document will print!

---

## 🍎 macOS

### Add Printer

1. Open **System Settings** (or **System Preferences** on older macOS)
2. Click **Printers & Scanners**
3. Click the **+** button to add a printer
4. Click the **IP** tab
5. Fill in:
   - **Address:** `PRINT-SERVER-IP` (e.g., `192.168.1.100`)
   - **Protocol:** Internet Printing Protocol - IPP
   - **Queue:** `printers/HP_Smart_Tank_515`
   - **Name:** Print Queue (or whatever you prefer)
   - **Location:** (optional)
6. **Use:** Select "HP Smart Tank 515" from the dropdown (or Generic PostScript)
7. Click **Add**

### How to Print

1. Print from any application (⌘+P)
2. Select "Print Queue"
3. Click Print
4. Open Safari/Chrome: `http://PRINT-SERVER-IP:5000`
5. Login with your credentials
6. Find your job and click **Release**
7. Your document will print!

---

## 🐧 Linux (Ubuntu/Debian)

### Method 1: GUI

1. Open **Settings** → **Printers**
2. Click **Add Printer**
3. Click **Network Printer** → **Internet Printing Protocol (ipp)**
4. Enter: `http://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515`
5. Click **Forward**
6. Select driver (HP Smart Tank 515 or Generic)
7. Click **Apply**

### Method 2: Command Line

```bash
# Replace 192.168.1.100 with your server IP
lpadmin -p PrintQueue -v ipp://192.168.1.100:631/printers/HP_Smart_Tank_515 -E

# Set as default (optional)
lpadmin -d PrintQueue
```

### How to Print

```bash
# Print a file
lpr -P PrintQueue document.pdf

# Or use GUI print dialog from any app
```

Then visit `http://PRINT-SERVER-IP:5000` to release the job.

---

## 📱 Mobile Devices

### iOS/iPadOS

1. Open document/photo you want to print
2. Tap **Share** → **Print**
3. Tap **Select Printer**
4. Look for **HP_Smart_Tank_515** or **Print Queue**
   - If not found, tap **"Add Printer"**
   - Enter: `http://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515`
5. Tap **Print**
6. On your computer or tablet, visit `http://PRINT-SERVER-IP:5000`
7. Login and release the job

### Android

1. Install **Mopria Print Service** from Play Store
2. Open document/photo
3. Tap **Share** → **Print**
4. Select printer (should auto-discover)
5. If not found:
   - Tap **All Printers** → **Add Printer**
   - Enter: `ipp://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515`
6. Visit `http://PRINT-SERVER-IP:5000` on any device
7. Login and release the job

---

## 🌐 Web Interface Guide

### Accessing the Print Queue Manager

1. Open your web browser
2. Go to: `http://PRINT-SERVER-IP:5000`
3. You'll be redirected to login page
4. Enter your username and password
5. You'll see your print jobs

### Dashboard Features

**My Jobs Tab:**
- Shows only your print jobs
- See job status (Pending, Held, Processing)
- Release jobs to start printing
- Cancel jobs you don't want

**Admin Tab (if you're an admin):**
- See all users' jobs
- Manage any job in the system
- Monitor print queue activity

### Job Status Meanings

| Status | What it means |
|--------|---------------|
| 🟡 Pending | Job is waiting in queue |
| 🔵 Held | Job is held, waiting for your approval |
| 🟢 Processing | Job is currently printing |
| ⚪ Completed | Job finished printing |
| 🔴 Canceled | Job was canceled |

---

## 🔧 Troubleshooting

### "Printer not found" when adding

**Solution:**
- Verify the server IP address is correct
- Make sure you can ping the server: `ping PRINT-SERVER-IP`
- Check server firewall allows port 631
- Try using the full URL: `http://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515`

### Print job doesn't appear in queue

**Solution:**
- Wait 10-20 seconds and refresh the web page
- Check you printed to the correct printer
- Verify your username matches your login credentials
- Contact your admin if issue persists

### "Authentication failed" when logging in

**Solution:**
- Make sure you're using the correct credentials
- Check with your admin that your account is set up
- Try clearing browser cache/cookies
- Make sure you have access to the print system

### Job stuck in "Processing"

**Solution:**
- Check if printer has paper/ink
- Check printer is not showing errors
- Admin can cancel the job and you can reprint
- Physical check: is printer turned on?

### Can't access web interface

**Solution:**
- Verify the server IP is correct
- Check server is running: contact your admin
- Try accessing from another device
- Check your network connection

---

## 📊 Quick Reference

**Important URLs** (replace PRINT-SERVER-IP with actual IP):

| What | URL |
|------|-----|
| Print Queue Manager | `http://PRINT-SERVER-IP:5000` |
| Printer URL (for adding) | `http://PRINT-SERVER-IP:631/printers/HP_Smart_Tank_515` |
| CUPS Web Interface | `http://PRINT-SERVER-IP:631` |

**Common Tasks:**

| Task | Steps |
|------|-------|
| Print a document | Print normally → Visit web interface → Release job |
| Cancel a job | Visit web interface → Find your job → Click Cancel |
| Check job status | Visit web interface → See status badge |
| Set default printer | Add printer → Set as default in system settings |

---

## 💡 Tips

1. **Bookmark the web interface** for quick access
2. **Set the printer as default** if you use it frequently
3. **Check the queue before large print jobs** to avoid wasting paper
4. **Cancel test prints quickly** to save paper and ink
5. **Mobile printing works too!** Just remember to release the job from a computer

---

## ℹ️ Support

For issues or questions:
1. Check this guide first
2. Try the troubleshooting section
3. Contact your system administrator
4. Check printer has paper and ink (basics!)

---

**Remember:** All print jobs are held until you release them via the web interface. This gives you control over what actually prints!
