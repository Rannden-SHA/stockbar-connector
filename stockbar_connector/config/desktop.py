from frappe import _


def get_data():
    return [
        {
            "module_name": "StockBar Connector",
            "color": "#6366f1",
            "icon": "octicon octicon-cloud",
            "type": "module",
            "label": _("StockBar Connector"),
            "description": _("Cloud sync, license management, and POS data uplink."),
        }
    ]
