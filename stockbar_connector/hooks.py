from . import __version__ as app_version

app_name = "stockbar_connector"
app_title = "StockBar Connector"
app_publisher = "Gisbert Distribuciones"
app_description = "Connects your local ERPNext server to StockBar-WEB cloud for license management, POS sync, and remote configuration."
app_email = "info@stockbar.pro"
app_license = "MIT"
app_icon_title = "StockBar"
app_logo_url = "/assets/stockbar_connector/images/stockbar-icon.png"

required_apps = ["erpnext"]

# ─── App Screen Icon ─────────────────────────────────────────────
add_to_apps_screen = [
    {
        "name": "stockbar_connector",
        "logo": "/assets/stockbar_connector/images/stockbar-icon.png",
        "title": "StockBar",
        "route": "/app/stockbar-settings",
        "has_permission": "stockbar_connector.permission.check_app_permission",
    }
]

# ─── Frontend Assets ─────────────────────────────────────────────
# app_include_css = "/assets/stockbar_connector/css/stockbar.css"
# app_include_js = "/assets/stockbar_connector/js/stockbar_connector.js"

# ─── Scheduled Tasks ─────────────────────────────────────────────
# Poll cloud every minute for pending config changes / kill-switch
scheduler_events = {
    "cron": {
        "*/1 * * * *": [
            "stockbar_connector.api.poll_cloud"
        ],
    },
    "daily": [
        "stockbar_connector.api.daily_heartbeat"
    ],
}

# ─── Document Event Hooks ────────────────────────────────────────
# Auto-push Z Report when a POS Closing Entry is submitted
doc_events = {
    "POS Closing Entry": {
        "on_submit": "stockbar_connector.api.on_pos_closing_submit",
    },
}

# ─── Website/Splash ──────────────────────────────────────────────
website_context = {
    "splash_image": "/assets/stockbar_connector/images/stockbar-icon.png"
}

# ─── Fixtures ────────────────────────────────────────────────────
# Export custom fields added by this app for portability
# fixtures = ["Custom Field"]

# ─── Override DocTypes ───────────────────────────────────────────
# override_doctype_class = {
#     "POS Closing Entry": "stockbar_connector.overrides.pos_closing_entry.StockBarPOSClosingEntry"
# }
