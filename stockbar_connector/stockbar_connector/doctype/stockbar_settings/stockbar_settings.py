# -*- coding: utf-8 -*-
# StockBar Settings DocType Controller

import frappe
from frappe.model.document import Document


class StockBarSettings(Document):
    """Controller for StockBar Settings Single DocType."""

    def validate(self):
        """Validate settings before saving."""
        if self.cloud_url:
            # Ensure URL doesn't end with /
            self.cloud_url = self.cloud_url.rstrip("/")

        if self.license_key and len(self.license_key) < 10:
            frappe.throw("License Key appears too short. Please check.")

    @frappe.whitelist()
    def test_connection(self):
        """Button handler: Test connection to StockBar Cloud."""
        from stockbar_connector.api import test_connection
        result = test_connection()
        if result.get("status") == "ok":
            frappe.msgprint(f"✅ {result['message']}", title="Connection Test", indicator="green")
        else:
            frappe.msgprint(f"❌ {result['message']}", title="Connection Test", indicator="red")

    @frappe.whitelist()
    def manual_sync(self):
        """Button handler: Trigger manual sync."""
        from stockbar_connector.api import manual_sync
        result = manual_sync()
        frappe.msgprint("🔄 Sync completed. Check the status fields above.", title="Manual Sync", indicator="blue")

    @frappe.whitelist()
    def manual_backup(self):
        """Button handler: Upload backup to cloud."""
        from stockbar_connector.api import manual_backup
        result = manual_backup()
        frappe.msgprint("📦 Backup upload initiated. Check Frappe logs for status.", title="Backup", indicator="blue")
