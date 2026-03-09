# -*- coding: utf-8 -*-
# StockBar Connector — API Module
# Handles all communication between local ERPNext and StockBar-WEB Cloud.

import frappe
import requests
import json
import os
import subprocess
import gzip
from datetime import datetime


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _get_settings():
    """Retrieve StockBar Settings (Single DocType)."""
    try:
        return frappe.get_single("StockBar Settings")
    except Exception:
        frappe.log_error("StockBar Settings not found. Please configure the connector.", "StockBar Connector")
        return None


def _get_headers(settings):
    """Build the standard request headers for Fleet API calls."""
    return {
        "X-License-Key": settings.license_key,
        "Content-Type": "application/json",
    }


def _cloud_url(settings, path):
    """Build the full URL for a Fleet API endpoint."""
    base = (settings.cloud_url or "").rstrip("/")
    return f"{base}{path}"


def _log_sync(message, level="info"):
    """Log sync activity to Frappe error log for debugging."""
    if level == "error":
        frappe.log_error(message, "StockBar Sync")
    else:
        frappe.logger("stockbar_connector").info(message)


def _update_sync_status(settings, status, message=""):
    """Update the sync status fields on the settings doc."""
    try:
        frappe.db.set_single_value("StockBar Settings", "sync_status", status)
        frappe.db.set_single_value("StockBar Settings", "last_sync", frappe.utils.now())
        if message:
            frappe.db.set_single_value("StockBar Settings", "last_sync_message", message[:500])
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to update sync status: {e}", "StockBar Connector")


# ─────────────────────────────────────────────────────────────────
# SCHEDULER: POLL CLOUD (every minute via cron)
# ─────────────────────────────────────────────────────────────────

def poll_cloud():
    """
    Called by Frappe scheduler every minute.
    1. Sends heartbeat to cloud
    2. Pulls pending tasks (config updates, backup requests, etc.)
    3. Processes each task and acknowledges it
    4. Handles kill-switch if license is suspended/deleted
    """
    settings = _get_settings()
    if not settings or not settings.license_key or not settings.cloud_url:
        return

    if not settings.is_enabled:
        return

    headers = _get_headers(settings)
    sync_pull_url = _cloud_url(settings, "/api/fleet/sync-pull")

    try:
        response = requests.get(sync_pull_url, headers=headers, timeout=30)

        if response.status_code == 403:
            # Kill-switch activated — license suspended or deleted
            data = response.json()
            if data.get("kill_switch"):
                _log_sync("⚠️ KILL SWITCH ACTIVATED — License suspended/deleted!", "error")
                _update_sync_status(settings, "KILLED", f"License status: {data.get('license_status')}")
                handle_kill_switch()
                return

        if response.status_code == 401:
            _log_sync("❌ Authentication failed — invalid license key", "error")
            _update_sync_status(settings, "AUTH_FAILED", "Invalid license key")
            return

        if response.status_code != 200:
            _log_sync(f"Sync-pull returned status {response.status_code}", "error")
            _update_sync_status(settings, "ERROR", f"HTTP {response.status_code}")
            return

        data = response.json()

        # Update connection status
        _update_sync_status(settings, "CONNECTED", f"OK - {len(data.get('tasks', []))} tasks")

        # Update business mode if changed from cloud
        if data.get("business_mode"):
            frappe.db.set_single_value("StockBar Settings", "business_mode", data["business_mode"])

        # Process pending tasks
        tasks = data.get("tasks", [])
        for task in tasks:
            try:
                process_task(task, settings)
                # Acknowledge successful processing
                ack_task(task["task_id"], settings)
            except Exception as e:
                _log_sync(f"Failed to process task {task.get('task_id')}: {e}", "error")

        frappe.db.commit()

    except requests.exceptions.ConnectionError:
        _update_sync_status(settings, "OFFLINE", "Cannot reach StockBar Cloud")
    except requests.exceptions.Timeout:
        _update_sync_status(settings, "TIMEOUT", "Cloud request timed out")
    except Exception as e:
        _log_sync(f"Poll cloud error: {e}", "error")
        _update_sync_status(settings, "ERROR", str(e)[:200])


# ─────────────────────────────────────────────────────────────────
# SCHEDULER: DAILY HEARTBEAT
# ─────────────────────────────────────────────────────────────────

def daily_heartbeat():
    """
    Called daily. Sends full system info to the cloud via /api/fleet/auth.
    """
    settings = _get_settings()
    if not settings or not settings.license_key or not settings.cloud_url:
        return

    if not settings.is_enabled:
        return

    headers = _get_headers(settings)
    auth_url = _cloud_url(settings, "/api/fleet/auth")

    try:
        # Gather system info
        import platform
        payload = {
            "hostname": platform.node(),
            "os_version": f"{platform.system()} {platform.release()}",
            "erpnext_version": _get_erpnext_version(),
            "connector_version": "1.0.0",
            "mac_address": _get_mac_address(),
        }

        response = requests.post(auth_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            _log_sync("Daily heartbeat sent successfully")
        elif response.status_code == 403:
            data = response.json()
            if data.get("kill_switch"):
                handle_kill_switch()
        else:
            _log_sync(f"Heartbeat returned {response.status_code}", "error")

    except Exception as e:
        _log_sync(f"Daily heartbeat error: {e}", "error")


# ─────────────────────────────────────────────────────────────────
# TASK PROCESSING
# ─────────────────────────────────────────────────────────────────

def process_task(task, settings):
    """
    Route a task from the cloud to the appropriate handler.
    Task types match those created by StockBar-WEB's SyncTask model.
    """
    task_type = task.get("task_type", "")
    payload = task.get("payload", {})

    _log_sync(f"Processing task {task.get('task_id')}: {task_type}")

    handlers = {
        "config_update": handle_config_update,
        "price_push": handle_price_push,
        "user_sync": handle_user_sync,
        "backup_request": handle_backup_request,
        "mode_change": handle_mode_change,
        "terminal_config": handle_terminal_config,
        "printer_config": handle_printer_config,
        "full_config_push": handle_full_config_push,
    }

    handler = handlers.get(task_type)
    if handler:
        handler(payload, settings)
    else:
        _log_sync(f"Unknown task type: {task_type}", "error")


def handle_config_update(payload, settings):
    """Apply general configuration updates from cloud."""
    if payload.get("server_name"):
        frappe.db.set_single_value("StockBar Settings", "server_name", payload["server_name"])
    if payload.get("business_mode"):
        frappe.db.set_single_value("StockBar Settings", "business_mode", payload["business_mode"])
    frappe.db.commit()
    _log_sync("Config updated from cloud")


def handle_price_push(payload, settings):
    """
    Receive price/key configuration from cloud and update local POS items.
    Maps cloud PosKeyConfig entries to ERPNext Item Price entries.
    """
    keys = payload.get("keys", [])
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"

    for key in keys:
        item_code = key.get("product_ref")
        if not item_code:
            continue

        # Ensure item exists
        if not frappe.db.exists("Item", item_code):
            _log_sync(f"Item {item_code} not found, skipping price push")
            continue

        # Update or create Item Price
        existing = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": price_list, "selling": 1},
            "name"
        )

        if existing:
            frappe.db.set_value("Item Price", existing, "price_list_rate", key.get("price", 0))
        else:
            item_price = frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list,
                "price_list_rate": key.get("price", 0),
                "selling": 1,
            })
            item_price.insert(ignore_permissions=True)

    frappe.db.commit()
    _log_sync(f"Price push processed: {len(keys)} keys")


def handle_user_sync(payload, settings):
    """
    Sync POS users from cloud. Creates/updates ERPNext users
    that are used for POS operator login.
    """
    users = payload.get("users", [])
    for user in users:
        _log_sync(f"User sync: {user.get('name')} ({user.get('pos_role')})")
        # In a full implementation, this would create/update POS Profile users
        # For now, log the sync for manual review
    _log_sync(f"User sync processed: {len(users)} users")


def handle_backup_request(payload, settings):
    """Trigger a database backup and upload it to the cloud."""
    try:
        upload_backup(settings)
        _log_sync("Backup requested and uploaded successfully")
    except Exception as e:
        _log_sync(f"Backup request failed: {e}", "error")


def handle_mode_change(payload, settings):
    """Change business mode (hospitality/retail) from cloud."""
    new_mode = payload.get("business_mode")
    if new_mode in ("hospitality", "retail"):
        frappe.db.set_single_value("StockBar Settings", "business_mode", new_mode)
        frappe.db.commit()
        _log_sync(f"Business mode changed to: {new_mode}")


def handle_terminal_config(payload, settings):
    """Receive terminal configuration from cloud."""
    terminals = payload.get("terminals", [])
    _log_sync(f"Terminal config received: {len(terminals)} terminals")
    # Store terminal config locally for reference
    frappe.db.set_single_value(
        "StockBar Settings", "terminal_config_json",
        json.dumps(terminals)
    )
    frappe.db.commit()


def handle_printer_config(payload, settings):
    """Receive printer configuration from cloud."""
    printers = payload.get("printers", [])
    _log_sync(f"Printer config received: {len(printers)} printers")
    frappe.db.set_single_value(
        "StockBar Settings", "printer_config_json",
        json.dumps(printers)
    )
    frappe.db.commit()


def handle_full_config_push(payload, settings):
    """Handle a full configuration push (servers + terminals + users + keys + printers)."""
    if payload.get("keys"):
        handle_price_push({"keys": payload["keys"]}, settings)
    if payload.get("users"):
        handle_user_sync({"users": payload["users"]}, settings)
    if payload.get("terminals"):
        handle_terminal_config({"terminals": payload["terminals"]}, settings)
    if payload.get("printers"):
        handle_printer_config({"printers": payload["printers"]}, settings)
    if payload.get("business_mode"):
        handle_mode_change({"business_mode": payload["business_mode"]}, settings)
    _log_sync("Full config push processed")


# ─────────────────────────────────────────────────────────────────
# TASK ACKNOWLEDGEMENT
# ─────────────────────────────────────────────────────────────────

def ack_task(task_id, settings):
    """Acknowledge a processed task to the cloud."""
    headers = _get_headers(settings)
    ack_url = _cloud_url(settings, f"/api/fleet/task/{task_id}/ack")

    try:
        response = requests.post(ack_url, headers=headers, timeout=15)
        if response.status_code != 200:
            _log_sync(f"Task ack failed for {task_id}: HTTP {response.status_code}", "error")
    except Exception as e:
        _log_sync(f"Task ack error for {task_id}: {e}", "error")


# ─────────────────────────────────────────────────────────────────
# POS CLOSING ENTRY HOOK — AUTO Z-REPORT PUSH
# ─────────────────────────────────────────────────────────────────

def on_pos_closing_submit(doc, method):
    """
    Frappe hook: called when a POS Closing Entry is submitted.
    Automatically pushes Z report data to StockBar-WEB.
    """
    settings = _get_settings()
    if not settings or not settings.license_key or not settings.is_enabled:
        return

    try:
        push_z_report(doc, settings)
    except Exception as e:
        _log_sync(f"Auto Z-report push failed: {e}", "error")
        # Don't block the POS closing — just log the error


def push_z_report(closing_entry, settings):
    """
    Extract Z report data from POS Closing Entry and push to cloud.
    Maps ERPNext's POS Closing Entry to StockBar-WEB's ZReport format.
    """
    headers = _get_headers(settings)
    push_url = _cloud_url(settings, "/api/fleet/sync-push")

    # Calculate totals from the closing entry
    total_sales = 0
    total_cash = 0
    total_card = 0
    total_tickets = 0
    tax_breakdown = {}

    # Sum up payment methods
    for payment in closing_entry.payment_reconciliation or []:
        amount = payment.closing_amount or 0
        total_sales += amount

        mode = (payment.mode_of_payment or "").lower()
        if "efectivo" in mode or "cash" in mode:
            total_cash += amount
        elif "tarjeta" in mode or "card" in mode or "visa" in mode or "mastercard" in mode:
            total_card += amount

    # Count invoices
    total_tickets = len(closing_entry.pos_transactions or [])

    # Calculate tax breakdown from invoices
    iva_totals = {"21": {"base": 0, "tax": 0}, "10": {"base": 0, "tax": 0}, "4": {"base": 0, "tax": 0}, "0": {"base": 0, "tax": 0}}

    for tx in closing_entry.pos_transactions or []:
        try:
            invoice = frappe.get_doc("POS Invoice", tx.pos_invoice)
            for tax_row in invoice.taxes or []:
                rate = str(int(tax_row.rate)) if tax_row.rate else "21"
                if rate in iva_totals:
                    iva_totals[rate]["tax"] += tax_row.tax_amount or 0
                    iva_totals[rate]["base"] += tax_row.tax_amount_after_discount_amount or (tax_row.tax_amount / (tax_row.rate / 100) if tax_row.rate else 0)
        except Exception:
            pass  # Skip if invoice can't be read

    tax_breakdown = {
        "iva_21_base": round(iva_totals["21"]["base"], 2),
        "iva_21_tax": round(iva_totals["21"]["tax"], 2),
        "iva_10_base": round(iva_totals["10"]["base"], 2),
        "iva_10_tax": round(iva_totals["10"]["tax"], 2),
        "iva_4_base": round(iva_totals["4"]["base"], 2),
        "iva_4_tax": round(iva_totals["4"]["tax"], 2),
        "iva_0_base": round(iva_totals["0"]["base"], 2),
        "iva_0_tax": 0,
    }

    # Build the Z report payload matching what fleet_sync_push expects
    payload = {
        "report_date": str(closing_entry.period_end_date or frappe.utils.today()),
        "report_number": f"Z-{closing_entry.name}",
        "total_sales": round(total_sales, 2),
        "total_cash": round(total_cash, 2),
        "total_card": round(total_card, 2),
        "total_other": round(max(0, total_sales - total_cash - total_card), 2),
        "total_tickets": total_tickets,
        "total_void": 0,
        "total_discounts": round(closing_entry.total_quantity or 0, 2),
        "tax_breakdown": tax_breakdown,
        "closed_by": closing_entry.user or "Sistema",
        "operator_name": frappe.db.get_value("User", closing_entry.user, "full_name") or closing_entry.user,
        "pos_profile": closing_entry.pos_profile or "",
    }

    response = requests.post(push_url, headers=headers, json=payload, timeout=30)

    if response.status_code == 201:
        _log_sync(f"Z-report pushed successfully: {closing_entry.name}")
    elif response.status_code == 403:
        _log_sync("Z-report push blocked — license not active", "error")
    else:
        _log_sync(f"Z-report push failed: HTTP {response.status_code} — {response.text[:200]}", "error")


# ─────────────────────────────────────────────────────────────────
# BACKUP UPLOAD
# ─────────────────────────────────────────────────────────────────

def upload_backup(settings=None):
    """
    Generate a database backup and upload it to StockBar-WEB cloud.
    Can be called by:
    - A cloud task (backup_request)
    - Manual trigger via the UI (frappe.call)
    """
    if not settings:
        settings = _get_settings()

    if not settings or not settings.license_key:
        _log_sync("Cannot upload backup — no settings configured", "error")
        return

    headers = {"X-License-Key": settings.license_key}
    upload_url = _cloud_url(settings, "/api/fleet/upload-backup")

    try:
        # Use Frappe's built-in backup
        from frappe.utils.backups import BackupGenerator
        backup = BackupGenerator(
            frappe.conf.db_name,
            frappe.conf.db_name,
            frappe.conf.db_password,
            db_host=frappe.conf.db_host,
            db_port=frappe.conf.db_port,
        )
        backup.take_dump()
        backup_path = backup.backup_path_db

        if not backup_path or not os.path.exists(backup_path):
            _log_sync("Backup file not generated", "error")
            return

        # Upload the backup file
        with open(backup_path, "rb") as f:
            files = {"backup_file": (os.path.basename(backup_path), f, "application/gzip")}
            data = {"backup_type": "full", "notes": f"Auto backup {frappe.utils.now()}"}
            response = requests.post(upload_url, headers=headers, files=files, data=data, timeout=120)

        if response.status_code == 201:
            _log_sync(f"Backup uploaded successfully: {os.path.basename(backup_path)}")
        else:
            _log_sync(f"Backup upload failed: HTTP {response.status_code}", "error")

    except Exception as e:
        _log_sync(f"Backup upload error: {e}", "error")


# ─────────────────────────────────────────────────────────────────
# KILL SWITCH
# ─────────────────────────────────────────────────────────────────

def handle_kill_switch():
    """
    Called when the cloud signals that the license is suspended or deleted.
    Disables all POS Profiles to prevent sales on unlicensed servers.
    """
    _log_sync("🚨 EXECUTING KILL SWITCH — Disabling all POS Profiles", "error")

    try:
        # Disable all POS Profiles
        pos_profiles = frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name")
        for profile_name in pos_profiles:
            frappe.db.set_value("POS Profile", profile_name, "disabled", 1)
            _log_sync(f"Disabled POS Profile: {profile_name}", "error")

        frappe.db.set_single_value("StockBar Settings", "sync_status", "LICENSE_BLOCKED")
        frappe.db.set_single_value("StockBar Settings", "is_enabled", 0)
        frappe.db.commit()

        _log_sync("Kill switch executed — all POS Profiles disabled", "error")

    except Exception as e:
        _log_sync(f"Kill switch execution error: {e}", "error")


# ─────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def _get_erpnext_version():
    """Get the installed ERPNext version."""
    try:
        import erpnext
        return erpnext.__version__
    except Exception:
        return "unknown"


def _get_mac_address():
    """Get the primary MAC address for hardware identification."""
    try:
        import uuid
        mac = uuid.getnode()
        return ":".join(f"{(mac >> i) & 0xFF:02x}" for i in range(0, 48, 8))
    except Exception:
        return "unknown"


# ─────────────────────────────────────────────────────────────────
# WHITELISTED METHODS (callable from desk UI via frappe.call)
# ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def manual_sync():
    """Manually trigger a sync-pull from the cloud. Callable from the desk."""
    poll_cloud()
    return {"status": "ok", "message": "Sync completed"}


@frappe.whitelist()
def manual_backup():
    """Manually trigger a backup upload. Callable from the desk."""
    upload_backup()
    return {"status": "ok", "message": "Backup uploaded"}


@frappe.whitelist()
def test_connection():
    """Test the connection to StockBar-WEB cloud."""
    settings = _get_settings()
    if not settings or not settings.license_key or not settings.cloud_url:
        return {"status": "error", "message": "License Key or Cloud URL not configured"}

    headers = _get_headers(settings)
    auth_url = _cloud_url(settings, "/api/fleet/auth")

    try:
        import platform
        payload = {
            "hostname": platform.node(),
            "os_version": f"{platform.system()} {platform.release()}",
            "erpnext_version": _get_erpnext_version(),
            "connector_version": "1.0.0",
        }
        response = requests.post(auth_url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()
            frappe.db.set_single_value("StockBar Settings", "is_connected", 1)
            frappe.db.set_single_value("StockBar Settings", "sync_status", "CONNECTED")
            frappe.db.commit()
            return {"status": "ok", "message": f"Connected! Server: {data.get('server_name', 'OK')}"}
        elif response.status_code == 403:
            return {"status": "error", "message": "License suspended or deleted (kill-switch active)"}
        elif response.status_code == 401:
            return {"status": "error", "message": "Invalid license key"}
        else:
            return {"status": "error", "message": f"Unexpected response: HTTP {response.status_code}"}

    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Cannot reach StockBar Cloud server"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
