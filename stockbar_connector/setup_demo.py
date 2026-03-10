import frappe
from frappe.utils.password import update_password


def create_demo_data():
    """
    Creates comprehensive demo data for testing the StockBar Connector and URY POS.
    Includes: Item Groups, ~40 Products, Price Lists with tiered pricing,
    Tax Templates, Payment Methods, Users, POS Profiles, and URY restaurant data.
    """
    frappe.logger("stockbar").info("🚀 Starting comprehensive demo data generation...")

    company = _get_or_create_company()
    if not company:
        return

    currency = frappe.db.get_value("Company", company, "default_currency") or "EUR"
    warehouse = _get_or_create_warehouse(company, "Almacén Barra - SBD", "Almacén Barra")
    warehouse_kitchen = _get_or_create_warehouse(company, "Almacén Cocina - SBD", "Almacén Cocina")
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0})
    income_account = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0})
    expense_account = frappe.db.get_value("Account", {"account_type": "Expense Account", "company": company, "is_group": 0})

    # ─── 1. Item Groups ──────────────────────────────────────────────
    _create_item_groups()

    # ─── 2. Tax Templates ────────────────────────────────────────────
    _create_tax_templates(company)

    # ─── 3. Price Lists ──────────────────────────────────────────────
    _create_price_lists()

    # ─── 4. Products (~40 items) ─────────────────────────────────────
    items = _create_items()

    # ─── 5. Item Prices (3 tariffs) ──────────────────────────────────
    _create_item_prices(items)

    # ─── 6. Payment Methods ──────────────────────────────────────────
    _create_payment_methods(company)

    # ─── 7. Customer ─────────────────────────────────────────────────
    customer = _create_default_customer()

    # ─── 8. POS Profile ──────────────────────────────────────────────
    _create_pos_profile(company, warehouse, customer, income_account, expense_account, cost_center, currency)

    # ─── 9. Users ────────────────────────────────────────────────────
    _create_users()

    # ─── 10. URY Restaurant Data (if installed) ──────────────────────
    _create_ury_data()

    frappe.db.commit()
    frappe.logger("stockbar").info("✅ Demo data generation complete!")
    print("✅ Demo data generation complete!")


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _get_or_create_company():
    """Get default company or return None."""
    company = frappe.defaults.get_user_default("Company")
    if not company:
        company = frappe.db.get_value("Company", {"is_group": 0})
    if not company:
        frappe.logger("stockbar").error("No Company found. Aborting demo setup.")
        print("❌ No Company found. Please complete ERPNext setup wizard first.")
        return None
    return company


def _get_or_create_warehouse(company, wh_name, wh_label):
    """Get or create a warehouse."""
    existing = frappe.db.get_value("Warehouse", {"name": wh_name})
    if existing:
        return existing

    # Get parent warehouse
    parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1})
    if not parent:
        parent = frappe.db.get_value("Warehouse", {"company": company})

    try:
        wh = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": wh_label,
            "company": company,
            "parent_warehouse": parent,
            "is_group": 0,
        })
        wh.insert(ignore_permissions=True)
        frappe.logger("stockbar").info(f"Created warehouse: {wh_label}")
        return wh.name
    except Exception as e:
        frappe.logger("stockbar").warning(f"Could not create warehouse {wh_label}: {e}")
        return frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})


def _create_item_groups():
    """Create product category groups for a bar/restaurant."""
    groups = [
        "Bebidas Calientes", "Cervezas", "Refrescos", "Vinos",
        "Cócteles y Combinados", "Tapas", "Raciones",
        "Postres", "Menú del Día", "Extras"
    ]
    parent = frappe.db.get_value("Item Group", {"name": "All Item Groups"}) or "All Item Groups"

    for g in groups:
        if not frappe.db.exists("Item Group", g):
            try:
                doc = frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": g,
                    "parent_item_group": parent,
                    "is_group": 0,
                })
                doc.insert(ignore_permissions=True)
            except Exception:
                pass
    frappe.logger("stockbar").info(f"Item Groups created: {len(groups)}")


def _create_tax_templates(company):
    """Create Spanish IVA tax templates (10%, 21%, 4%)."""
    templates = [
        {"name": "IVA 10% Hostelería", "rate": 10, "title": "IVA Reducido 10%"},
        {"name": "IVA 21% General", "rate": 21, "title": "IVA General 21%"},
        {"name": "IVA 4% Superreducido", "rate": 4, "title": "IVA Superreducido 4%"},
    ]

    income_account = frappe.db.get_value("Account", {"account_type": "Tax", "company": company, "is_group": 0})
    if not income_account:
        income_account = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0})

    for t in templates:
        if not frappe.db.exists("Sales Taxes and Charges Template", {"title": t["title"], "company": company}):
            try:
                doc = frappe.get_doc({
                    "doctype": "Sales Taxes and Charges Template",
                    "title": t["title"],
                    "company": company,
                    "taxes": [{
                        "charge_type": "On Net Total",
                        "account_head": income_account,
                        "rate": t["rate"],
                        "description": f"IVA {t['rate']}%",
                    }]
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                frappe.logger("stockbar").warning(f"Tax template {t['title']}: {e}")
    frappe.logger("stockbar").info("Tax templates created")


def _create_price_lists():
    """Create tiered price lists: Barra, Terraza (+15%), Sala VIP (+25%)."""
    price_lists = [
        {"name": "Barra", "selling": 1},
        {"name": "Terraza (+15%)", "selling": 1},
        {"name": "Sala VIP (+25%)", "selling": 1},
    ]
    for pl in price_lists:
        if not frappe.db.exists("Price List", pl["name"]):
            try:
                doc = frappe.get_doc({
                    "doctype": "Price List",
                    "price_list_name": pl["name"],
                    "currency": "EUR",
                    "selling": pl["selling"],
                    "enabled": 1,
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                frappe.logger("stockbar").warning(f"Price list {pl['name']}: {e}")
    frappe.logger("stockbar").info("Price Lists created")


def _create_items():
    """Create ~40 real bar/restaurant products."""
    items = [
        # Bebidas Calientes
        {"code": "CAFE-001", "name": "Café Solo", "group": "Bebidas Calientes", "price": 1.20, "tax": 10},
        {"code": "CAFE-002", "name": "Café Cortado", "group": "Bebidas Calientes", "price": 1.30, "tax": 10},
        {"code": "CAFE-003", "name": "Café con Leche", "group": "Bebidas Calientes", "price": 1.50, "tax": 10},
        {"code": "CAFE-004", "name": "Café Americano", "group": "Bebidas Calientes", "price": 1.60, "tax": 10},
        {"code": "CAFE-005", "name": "Capuchino", "group": "Bebidas Calientes", "price": 1.80, "tax": 10},
        {"code": "CAFE-006", "name": "Infusión / Té", "group": "Bebidas Calientes", "price": 1.50, "tax": 10},
        {"code": "CAFE-007", "name": "Colacao / Cola Cao", "group": "Bebidas Calientes", "price": 1.80, "tax": 10},

        # Cervezas
        {"code": "CERV-001", "name": "Caña", "group": "Cervezas", "price": 1.50, "tax": 21},
        {"code": "CERV-002", "name": "Tercio", "group": "Cervezas", "price": 2.00, "tax": 21},
        {"code": "CERV-003", "name": "Pinta", "group": "Cervezas", "price": 3.50, "tax": 21},
        {"code": "CERV-004", "name": "Cerveza Sin Alcohol", "group": "Cervezas", "price": 1.80, "tax": 21},
        {"code": "CERV-005", "name": "Cerveza Especial", "group": "Cervezas", "price": 3.00, "tax": 21},

        # Refrescos
        {"code": "REF-001", "name": "Coca-Cola", "group": "Refrescos", "price": 2.00, "tax": 10},
        {"code": "REF-002", "name": "Fanta Naranja", "group": "Refrescos", "price": 2.00, "tax": 10},
        {"code": "REF-003", "name": "Fanta Limón", "group": "Refrescos", "price": 2.00, "tax": 10},
        {"code": "REF-004", "name": "Aquarius", "group": "Refrescos", "price": 2.20, "tax": 10},
        {"code": "REF-005", "name": "Agua Mineral 50cl", "group": "Refrescos", "price": 1.50, "tax": 10},
        {"code": "REF-006", "name": "Tónica", "group": "Refrescos", "price": 2.00, "tax": 10},
        {"code": "REF-007", "name": "Zumo Natural", "group": "Refrescos", "price": 3.00, "tax": 10},

        # Vinos
        {"code": "VINO-001", "name": "Tinto Copa", "group": "Vinos", "price": 2.50, "tax": 21},
        {"code": "VINO-002", "name": "Blanco Copa", "group": "Vinos", "price": 2.50, "tax": 21},
        {"code": "VINO-003", "name": "Fino / Manzanilla", "group": "Vinos", "price": 2.00, "tax": 21},
        {"code": "VINO-004", "name": "Tinto Reserva (Botella)", "group": "Vinos", "price": 18.00, "tax": 21},
        {"code": "VINO-005", "name": "Sangría Jarra", "group": "Vinos", "price": 12.00, "tax": 21},

        # Cócteles y Combinados
        {"code": "COCK-001", "name": "Gin-Tonic", "group": "Cócteles y Combinados", "price": 7.00, "tax": 21},
        {"code": "COCK-002", "name": "Mojito", "group": "Cócteles y Combinados", "price": 7.50, "tax": 21},
        {"code": "COCK-003", "name": "Cuba Libre", "group": "Cócteles y Combinados", "price": 6.50, "tax": 21},
        {"code": "COCK-004", "name": "Whisky Cola", "group": "Cócteles y Combinados", "price": 6.50, "tax": 21},

        # Tapas
        {"code": "TAPA-001", "name": "Patatas Bravas", "group": "Tapas", "price": 4.50, "tax": 10},
        {"code": "TAPA-002", "name": "Jamón Ibérico (media)", "group": "Tapas", "price": 12.00, "tax": 10},
        {"code": "TAPA-003", "name": "Croquetas (6 uds)", "group": "Tapas", "price": 6.50, "tax": 10},
        {"code": "TAPA-004", "name": "Tortilla Española", "group": "Tapas", "price": 5.00, "tax": 10},
        {"code": "TAPA-005", "name": "Aceitunas", "group": "Tapas", "price": 2.50, "tax": 10},
        {"code": "TAPA-006", "name": "Queso Manchego", "group": "Tapas", "price": 7.00, "tax": 10},
        {"code": "TAPA-007", "name": "Pan con Tomate", "group": "Tapas", "price": 3.00, "tax": 10},

        # Raciones
        {"code": "RAC-001", "name": "Pulpo a la Gallega", "group": "Raciones", "price": 14.00, "tax": 10},
        {"code": "RAC-002", "name": "Calamares a la Romana", "group": "Raciones", "price": 10.00, "tax": 10},
        {"code": "RAC-003", "name": "Gambas al Ajillo", "group": "Raciones", "price": 12.00, "tax": 10},
        {"code": "RAC-004", "name": "Ensaladilla Rusa", "group": "Raciones", "price": 6.00, "tax": 10},

        # Postres
        {"code": "POST-001", "name": "Flan Casero", "group": "Postres", "price": 4.00, "tax": 10},
        {"code": "POST-002", "name": "Tarta de Queso", "group": "Postres", "price": 5.00, "tax": 10},
        {"code": "POST-003", "name": "Helado (2 bolas)", "group": "Postres", "price": 3.50, "tax": 10},
        {"code": "POST-004", "name": "Brownie con Nata", "group": "Postres", "price": 5.50, "tax": 10},

        # Extras
        {"code": "EXTRA-001", "name": "Suplemento Pan", "group": "Extras", "price": 1.00, "tax": 4},
        {"code": "EXTRA-002", "name": "Suplemento Leche Vegetal", "group": "Extras", "price": 0.40, "tax": 10},
    ]

    for item in items:
        if not frappe.db.exists("Item", item["code"]):
            try:
                doc = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item["code"],
                    "item_name": item["name"],
                    "item_group": item.get("group", "Products"),
                    "stock_uom": "Nos",
                    "is_stock_item": 0,
                    "is_sales_item": 1,
                    "standard_rate": item["price"],
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                frappe.logger("stockbar").warning(f"Item {item['code']}: {e}")

    frappe.logger("stockbar").info(f"Items created: {len(items)}")
    return items


def _create_item_prices(items):
    """Create prices for 3 tariffs: Barra, Terraza (+15%), Sala VIP (+25%)."""
    tariffs = {
        "Barra": 1.0,
        "Terraza (+15%)": 1.15,
        "Sala VIP (+25%)": 1.25,
    }

    count = 0
    for item in items:
        for pl_name, multiplier in tariffs.items():
            if not frappe.db.exists("Price List", pl_name):
                continue
            price = round(item["price"] * multiplier, 2)
            existing = frappe.db.get_value(
                "Item Price",
                {"item_code": item["code"], "price_list": pl_name, "selling": 1},
                "name"
            )
            if not existing:
                try:
                    doc = frappe.get_doc({
                        "doctype": "Item Price",
                        "item_code": item["code"],
                        "price_list": pl_name,
                        "price_list_rate": price,
                        "selling": 1,
                        "currency": "EUR",
                    })
                    doc.insert(ignore_permissions=True)
                    count += 1
                except Exception:
                    pass

    frappe.logger("stockbar").info(f"Item Prices created: {count}")


def _create_payment_methods(company):
    """Create payment methods: Efectivo, Tarjeta, Bizum."""
    methods = [
        {"name": "Efectivo", "type": "Cash"},
        {"name": "Tarjeta", "type": "Bank"},
        {"name": "Bizum", "type": "Phone"},
        {"name": "Transferencia", "type": "Bank"},
    ]

    for m in methods:
        if not frappe.db.exists("Mode of Payment", m["name"]):
            try:
                doc = frappe.get_doc({
                    "doctype": "Mode of Payment",
                    "mode_of_payment": m["name"],
                    "type": m["type"],
                    "enabled": 1,
                    "accounts": [{
                        "company": company,
                        "default_account": frappe.db.get_value(
                            "Account",
                            {"account_type": "Cash" if m["type"] == "Cash" else "Bank", "company": company, "is_group": 0}
                        ),
                    }]
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                frappe.logger("stockbar").warning(f"Payment mode {m['name']}: {e}")

    frappe.logger("stockbar").info("Payment methods created")


def _create_default_customer():
    """Create default walk-in customer for POS."""
    name = "Cliente Mostrador"
    if not frappe.db.exists("Customer", name):
        try:
            customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}) or "Commercial"
            territory = frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories"
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": name,
                "customer_group": customer_group,
                "territory": territory,
                "customer_type": "Individual",
            })
            doc.insert(ignore_permissions=True)
            frappe.logger("stockbar").info(f"Customer '{name}' created")
        except Exception as e:
            frappe.logger("stockbar").warning(f"Customer: {e}")
    return name


def _create_pos_profile(company, warehouse, customer, income_account, expense_account, cost_center, currency):
    """Create a complete POS Profile with payment methods and item groups."""
    profile_name = "StockBar Barra"

    if frappe.db.exists("POS Profile", profile_name):
        frappe.logger("stockbar").info(f"POS Profile '{profile_name}' already exists, skipping.")
        return

    # Build payment methods list
    payments = []
    for mode in ["Efectivo", "Tarjeta", "Bizum"]:
        if frappe.db.exists("Mode of Payment", mode):
            account = frappe.db.get_value(
                "Mode of Payment Account",
                {"parent": mode, "company": company},
                "default_account"
            )
            if not account:
                account = frappe.db.get_value(
                    "Account",
                    {"account_type": "Cash" if mode == "Efectivo" else "Bank", "company": company, "is_group": 0}
                )
            payments.append({
                "mode_of_payment": mode,
                "default": 1 if mode == "Efectivo" else 0,
                "account": account,
            })

    try:
        profile = frappe.get_doc({
            "doctype": "POS Profile",
            "name": profile_name,
            "company": company,
            "currency": currency,
            "warehouse": warehouse,
            "customer": customer,
            "income_account": income_account,
            "expense_account": expense_account,
            "write_off_account": expense_account,
            "write_off_cost_center": cost_center,
            "update_stock": 1,
            "payments": payments,
            "applicable_for_users": [],
        })
        profile.insert(ignore_permissions=True)
        frappe.logger("stockbar").info(f"POS Profile '{profile_name}' created with {len(payments)} payment methods.")
    except Exception as e:
        frappe.logger("stockbar").warning(f"POS Profile: {e}")


def _create_users():
    """Create demo users for the POS system."""
    users = [
        {
            "email": "encargado@stockbar.local",
            "first_name": "Carlos",
            "last_name": "Encargado",
            "roles": [{"role": "System Manager"}, {"role": "Sales User"}, {"role": "Stock User"}],
        },
        {
            "email": "cajero@stockbar.local",
            "first_name": "María",
            "last_name": "Cajera",
            "roles": [{"role": "Sales User"}, {"role": "POS User"}],
        },
        {
            "email": "cocina@stockbar.local",
            "first_name": "Pedro",
            "last_name": "Cocina",
            "roles": [{"role": "Sales User"}],
        },
        {
            "email": "camarero@stockbar.local",
            "first_name": "Ana",
            "last_name": "Camarera",
            "roles": [{"role": "Sales User"}, {"role": "POS User"}],
        },
    ]

    for u in users:
        if not frappe.db.exists("User", u["email"]):
            try:
                doc = frappe.get_doc({
                    "doctype": "User",
                    "email": u["email"],
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                    "send_welcome_email": 0,
                    "roles": u["roles"],
                })
                doc.insert(ignore_permissions=True)
                update_password(doc.name, "1234")
                frappe.logger("stockbar").info(f"User '{u['email']}' created (pw: 1234)")
            except Exception as e:
                frappe.logger("stockbar").warning(f"User {u['email']}: {e}")

    frappe.logger("stockbar").info(f"Users created: {len(users)}")


def _create_ury_data():
    """Create Restaurant/URY data if the URY app is installed."""
    try:
        # Check if URY Restaurant module is available
        if not frappe.db.exists("DocType", "Restaurant"):
            frappe.logger("stockbar").info("URY not installed, skipping restaurant data.")
            return

        # Create Restaurant
        if not frappe.db.exists("Restaurant", "StockBar Demo"):
            try:
                restaurant = frappe.get_doc({
                    "doctype": "Restaurant",
                    "restaurant_name": "StockBar Demo",
                    "company": frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {"is_group": 0}),
                })
                restaurant.insert(ignore_permissions=True)
                frappe.logger("stockbar").info("Restaurant 'StockBar Demo' created")
            except Exception as e:
                frappe.logger("stockbar").warning(f"Restaurant: {e}")

        # Create Restaurant Menu if DocType exists
        if frappe.db.exists("DocType", "Restaurant Menu"):
            menus = [
                {"name": "Carta de Bebidas", "restaurant": "StockBar Demo"},
                {"name": "Carta de Tapas", "restaurant": "StockBar Demo"},
                {"name": "Carta de Postres", "restaurant": "StockBar Demo"},
            ]
            for m in menus:
                if not frappe.db.exists("Restaurant Menu", m["name"]):
                    try:
                        doc = frappe.get_doc({
                            "doctype": "Restaurant Menu",
                            "restaurant_menu": m["name"],
                            "restaurant": m["restaurant"],
                        })
                        doc.insert(ignore_permissions=True)
                    except Exception as e:
                        frappe.logger("stockbar").warning(f"Menu {m['name']}: {e}")

        # Create Tables if DocType exists
        if frappe.db.exists("DocType", "Restaurant Table"):
            tables = [
                # Barra
                {"name": "Barra 1", "capacity": 2},
                {"name": "Barra 2", "capacity": 2},
                {"name": "Barra 3", "capacity": 2},
                # Terraza
                {"name": "Terraza 1", "capacity": 4},
                {"name": "Terraza 2", "capacity": 4},
                {"name": "Terraza 3", "capacity": 6},
                {"name": "Terraza 4", "capacity": 4},
                # Sala Interior
                {"name": "Sala 1", "capacity": 4},
                {"name": "Sala 2", "capacity": 6},
                {"name": "Sala 3", "capacity": 8},
            ]
            for t in tables:
                if not frappe.db.exists("Restaurant Table", t["name"]):
                    try:
                        doc = frappe.get_doc({
                            "doctype": "Restaurant Table",
                            "table_name": t["name"],
                            "restaurant": "StockBar Demo",
                            "minimum_seating": 1,
                            "maximum_seating": t["capacity"],
                        })
                        doc.insert(ignore_permissions=True)
                    except Exception as e:
                        frappe.logger("stockbar").warning(f"Table {t['name']}: {e}")

        frappe.logger("stockbar").info("URY restaurant data created (menus + tables)")

    except Exception as e:
        frappe.logger("stockbar").info(f"URY data skipped: {e}")
