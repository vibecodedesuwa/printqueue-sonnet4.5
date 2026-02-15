# Client Setup Guide — PrintQ

Connect your devices to PrintQ for printing from any device on your network.

## 📱 iPhone / iPad (AirPrint)

AirPrint is built into iOS — **no app needed**.

1. Make sure your device is on the **same Wi-Fi network** as the print server
2. Open any app (Photos, Safari, Files, etc.)
3. Tap the **Share** button (⬆️) → **Print**
4. Your printer (`HP Smart Tank 515`) should appear automatically
5. Select it, choose options, and tap **Print**
6. The job goes into the queue as **held** — approve it via the dashboard or kiosk

> **Not seeing the printer?** Make sure mDNS (UDP 5353) traffic is not blocked by your router/firewall.

---

## 🤖 Android (Mopria / Default Print Service)

Android 8+ has built-in print support via **Default Print Service**.

### Android 8+ (Oreo and newer)

1. Connect to the **same Wi-Fi network**
2. Open any app → **Share** → **Print** (or via the menu: ⋮ → Print)
3. The printer should appear automatically
4. If not found, go to **Settings → Connected devices → Printing** and ensure **Default Print Service** is ON

### Older Android (< 8.0)

1. Install **[Mopria Print Service](https://play.google.com/store/apps/details?id=org.mopria.printplugin)** from Play Store
2. Enable it in **Settings → Connected devices → Printing**
3. Print from any app as above

> **Job identity:** Since Android sends a generic username, your job will appear as "unclaimed" in the queue. Log into the web dashboard to **claim** your job.

---

## 💻 macOS

### Automatic (AirPrint)

- The printer should auto-appear in the Print dialog (Cmd+P) — same as iOS

### Manual

1. **System Settings → Printers & Scanners → Add Printer (+)**
2. Click the **IP** tab
3. Protocol: **IPP**
4. Address: `your-server-ip`
5. Queue: `/printers/HP_Smart_Tank_515`
6. Click **Add**

---

## 🪟 Windows 10 / 11

### Add Printer via IPP

1. Open **Settings → Bluetooth & Devices → Printers & Scanners**
2. Click **Add device**
3. Click **"The printer that I want isn't listed"**
4. Select **"Add a printer using a TCP/IP address or hostname"**
5. Device type: **IPP Device**
6. Hostname or IP: `http://YOUR-SERVER-IP:631/printers/HP_Smart_Tank_515`
7. Follow the prompts to finish setup

### Alternatively, enable Internet Printing Client

1. **Settings → Apps → Optional Features → Add a feature**
2. Search for **"Internet Printing Client"** and install it
3. Open **Run** (Win+R), type: `http://YOUR-SERVER-IP:631/printers/HP_Smart_Tank_515`
4. Click **Connect** to add the printer

---

## 🐧 Linux

### Via CUPS (Command Line)

```bash
# Add the shared printer
lpadmin -p PrintQ -E -v ipp://YOUR-SERVER-IP:631/printers/HP_Smart_Tank_515

# Set as default (optional)
lpoptions -d PrintQ

# Print a file
lp -d PrintQ document.pdf
```

### Via GUI (GNOME/KDE)

1. **Settings → Printers → Add Printer**
2. The printer should appear automatically via mDNS
3. If not, enter the URL: `ipp://YOUR-SERVER-IP:631/printers/HP_Smart_Tank_515`

---

## 🌐 Web Upload (Any Device)

No driver installation needed — works from any browser!

1. Go to `http://YOUR-SERVER-IP:5000/upload`
2. Log in with your SSO credentials
3. Drag & drop or select your file (PDF, PNG, JPG, DOCX, TXT)
4. Choose print options (copies, color, duplex)
5. Click **Submit Print Job**
6. Your job enters the queue for approval

---

## 📧 Print via Email

Send your documents by email — no login required!

1. Send an email to `print@your-domain.com` (ask your admin for the address)
2. Attach the file(s) you want to print (PDF, PNG, JPG, DOCX)
3. You'll receive a confirmation reply
4. Your job enters the queue for approval

> **Tip:** Ask your admin to add your email to the **email mapping** so jobs are automatically assigned to your username.

---

## 🙋 Claiming Your Print Job

When you print from a phone via AirPrint/Mopria, the system may not know who you are. Here's how to claim your job:

1. Log into the **PrintQ dashboard** at `http://YOUR-SERVER-IP:5000/dashboard`
2. Look for the **"Unclaimed Jobs"** section at the top
3. Find your document by name and timestamp
4. Tap the **🙋 Claim** button
5. The job is now yours — approve it to start printing!

> **Pro tip:** Ask your admin to add your device to the **Device Mapping** so future jobs are automatically assigned to you.

---

## ⚠️ Troubleshooting

| Issue                           | Solution                                                       |
| ------------------------------- | -------------------------------------------------------------- |
| Printer not found (iOS/Android) | Ensure mDNS (UDP 5353) is open; device must be on same network |
| Jobs stuck in queue             | Check if the CUPS server is running (`docker ps`)              |
| "Unclaimed" job                 | Log into web dashboard and claim it                            |
| File type not supported         | Convert to PDF first — supported: PDF, PNG, JPG, DOCX, TXT     |
| Windows can't connect           | Ensure Internet Printing Client is enabled                     |
