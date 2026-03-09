<p align="center">
  <h1 align="center">⚡ StockBar Connector</h1>
  <p align="center">
    Frappe/ERPNext app that connects your local server to <strong>StockBar-WEB Cloud</strong>.<br>
    License management · POS sync · Remote configuration · Kill-switch
  </p>
</p>

---

## 🏗️ Architecture

```
┌──────────────────────┐           HTTPS          ┌───────────────────────┐
│   LOCAL SERVER       │   ◄──────────────────►   │   STOCKBAR-WEB CLOUD  │
│                      │                          │                       │
│  ERPNext             │   poll (every X min)     │  Fleet API            │
│  StockBar Connector  │ ──── sync-pull ────────► │  /api/fleet/sync-pull │
│                      │  ◄─── tasks ──────────── │                       │
│  POS Closing Entry   │                          │                       │
│  ──► auto Z-report   │ ──── sync-push ────────► │  /api/fleet/sync-push │
│                      │                          │                       │
│  DB Backup           │ ──── upload-backup ────► │  /api/fleet/upload    │
└──────────────────────┘                          └───────────────────────┘
```

## ✨ Features

| Feature | Description |
|---|---|
| 🔄 **Auto Polling** | Every minute via Frappe scheduler — pulls pending config tasks from cloud |
| 📊 **Z-Report Push** | Automatically sends POS closing data (sales, taxes, payments) to cloud on submit |
| 💾 **Backup Upload** | Generate and upload database backups to cloud storage |
| 🔐 **Kill-Switch** | Cloud can remotely disable all POS Profiles if license is suspended |
| 💰 **Price Sync** | Receive item prices from cloud and update local ERPNext price lists |
| ⚙️ **Remote Config** | Terminal, printer, and user configuration pushed from cloud |
| 🖥️ **Desk UI** | "StockBar Settings" page with test connection, manual sync, and backup buttons |

## 📋 Requirements

- **ERPNext** v15+
- **Frappe** v15+
- **Python** 3.10+
- Active **StockBar-WEB** license key

## 🚀 Installation

### Option A: Automated (recommended)

Use the install_server.sh provisioning script, which installs ERPNext + this connector automatically.

### Option B: Manual

```bash
# 1. Download the app
bench get-app stockbar_connector https://github.com/Rannden-SHA/stockbar-connector.git

# 2. Install on your site
bench --site your-site.local install-app stockbar_connector

# 3. Build assets (CRITICAL — app will be invisible without this!)
bench build --force

# 4. Run migrations (CRITICAL — creates DocTypes)
bench --site your-site.local migrate

# 5. Restart workers
bench restart
```

### Docker (frappe_docker)

```bash
# Inside the backend container:
docker compose -f pwd.yml exec backend bench get-app stockbar_connector https://github.com/Rannden-SHA/stockbar-connector.git
docker compose -f pwd.yml exec backend bench --site stockbar.local install-app stockbar_connector
docker compose -f pwd.yml exec backend bench build --force
docker compose -f pwd.yml exec backend bench --site stockbar.local migrate
docker compose -f pwd.yml restart backend queue-long queue-short scheduler websocket
```

## ⚙️ Configuration

1. Login to ERPNext as **Administrator**
2. Search for **"StockBar Settings"** in the search bar
3. Enter your **License Key** and **Cloud URL** (`https://stockbarweb.pro`)
4. Check **Enabled**
5. Click **Test Connection** to verify

## 📁 App Structure

```
stockbar_connector/
├── setup.py                 # Python package config
├── requirements.txt         # Dependencies (requests)
├── MANIFEST.in              # Package manifest
└── stockbar_connector/
    ├── __init__.py           # Version: 1.0.0
    ├── hooks.py              # Scheduler + doc_events
    ├── api.py                # Core logic (~480 lines)
    ├── permission.py         # App permission check
    ├── modules.txt           # Frappe module definition
    ├── config/
    │   └── desktop.py        # Desk icon
    ├── public/js/
    │   └── stockbar_connector.js
    ├── templates/pages/
    └── stockbar_connector/   # Frappe module
        ├── stockbar_connector.json
        └── doctype/
            └── stockbar_settings/
                ├── stockbar_settings.json   # DocType definition
                └── stockbar_settings.py     # Controller
```

## 🔗 Fleet API Endpoints

The connector communicates with these StockBar-WEB endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/fleet/auth` | POST | License validation + heartbeat |
| `/api/fleet/sync-pull` | GET | Pull pending tasks + kill-switch check |
| `/api/fleet/sync-push` | POST | Push Z Reports (POS closings) |
| `/api/fleet/upload-backup` | POST | Upload database backups |
| `/api/fleet/task/<id>/ack` | POST | Acknowledge processed tasks |

## 🛡️ Kill-Switch

If the license is suspended or deleted from StockBar-WEB:

1. `sync-pull` returns `403` with `kill_switch: True`
2. Connector **disables all POS Profiles** on the local ERPNext
3. Sets status to `LICENSE_BLOCKED`
4. POS operators cannot open new sessions until license is reactivated

## 📄 License

MIT — [Gisbert Distribuciones](https://stockbar.pro)
