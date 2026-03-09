/* StockBar Connector Desk JS */
frappe.provide("stockbar_connector");

// Add quick action buttons to the desk via system notification
$(document).ready(function () {
    // Show connection status indicator in toolbar if on StockBar Settings
    if (frappe.get_route_str() === "Form/StockBar Settings") {
        frappe.call({
            method: "stockbar_connector.api.test_connection",
            callback: function (r) {
                if (r.message && r.message.status === "ok") {
                    frappe.show_alert({
                        message: __("StockBar Cloud: Connected ✅"),
                        indicator: "green",
                    });
                }
            },
        });
    }
});
