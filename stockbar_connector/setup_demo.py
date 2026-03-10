import frappe

def create_demo_data():
    """
    Creates comprehensive demo data for testing the StockBar Connector and URY POS.
    This includes test users, taxes, item groups, price lists, items, and settings.
    """
    frappe.logger("stockbar").info("Starting Advanced Demo Data generation...")
    print("Starting Advanced Demo Data generation...")

    company = frappe.defaults.get_user_default("Company")
    if not company:
        company = frappe.db.get_value("Company", {"is_group": 0})
        
    if not company:
        frappe.logger("stockbar").error("No Company found. Aborting demo structure.")
        print("ERROR: No Company found!")
        return
        
    currency = frappe.db.get_value("Company", company, "default_currency")

    # 1. Base Setup (Price Lists, Item Groups)
    print("Setting up base groups and lists...")
    if not frappe.db.exists("Price List", "Standard Selling"):
        doc = frappe.get_doc({"doctype": "Price List", "price_list_name": "Standard Selling", "selling": 1, "currency": currency})
        doc.insert(ignore_permissions=True)

    item_groups = ["Comida", "Bebidas", "Postres"]
    for ig in item_groups:
        if not frappe.db.exists("Item Group", ig):
            doc = frappe.get_doc({"doctype": "Item Group", "item_group_name": ig, "parent_item_group": "All Item Groups"})
            doc.insert(ignore_permissions=True)

    # 2. Taxes
    print("Setting up Taxes...")
    income_account = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0})
    expense_account = frappe.db.get_value("Account", {"account_type": "Expense Account", "company": company, "is_group": 0})
    tax_account = frappe.db.get_value("Account", {"account_type": "Tax", "company": company, "is_group": 0})
    
    if tax_account:
        if not frappe.db.exists("Item Tax Template", "IVA 21%"):
            doc = frappe.get_doc({
                "doctype": "Item Tax Template", 
                "title": "IVA 21%", 
                "company": company,
                "taxes": [{"tax_type": tax_account, "tax_rate": 21}]
            })
            doc.insert(ignore_permissions=True)

    # 3. Create Items & Prices
    print("Creating Items and Pricing...")
    demo_items = [
        {"item_code": "BEER-001", "item_name": "Cerveza IPA Artesanal", "item_group": "Bebidas", "rate": 5.50},
        {"item_code": "BEER-002", "item_name": "Cerveza Rubia Pinta", "item_group": "Bebidas", "rate": 4.00},
        {"item_code": "FOOD-001", "item_name": "Nachos Supremo", "item_group": "Comida", "rate": 12.50},
        {"item_code": "FOOD-002", "item_name": "Hamburguesa Clásica", "item_group": "Comida", "rate": 15.00},
        {"item_code": "DESS-001", "item_name": "Tarta de Queso", "item_group": "Postres", "rate": 6.50},
    ]

    for data in demo_items:
        if not frappe.db.exists("Item", data["item_code"]):
            try:
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": data["item_code"],
                    "item_name": data["item_name"],
                    "item_group": data["item_group"],
                    "stock_uom": "Nos",
                    "is_stock_item": 0,
                    "is_sales_item": 1,
                    "taxes": [{"item_tax_template": "IVA 21%", "tax_category": ""}] if tax_account else []
                })
                item.insert(ignore_permissions=True)
                
                # Create Price
                frappe.get_doc({
                    "doctype": "Item Price",
                    "price_list": "Standard Selling",
                    "item_code": item.item_code,
                    "price_list_rate": data["rate"]
                }).insert(ignore_permissions=True)
                
            except Exception as e:
                print(f"Failed to create Item '{data['item_code']}': {e}")

    # 4. Create POS Profile
    print("Creating POS Profile...")
    if not frappe.db.exists("POS Profile", "StockBar Demo"):
        warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
        customer = frappe.db.get_value("Customer", {"customer_group": "Commercial", "name": "Cliente Contado"})
        if not customer:
            doc = frappe.get_doc({
                "doctype": "Customer", "customer_name": "Cliente Contado", "customer_group": "Commercial", "territory": "All Territories"
            })
            doc.insert(ignore_permissions=True)
            customer = doc.name
                
        try:
            profile = frappe.get_doc({
                "doctype": "POS Profile",
                "name": "StockBar Demo",
                "company": company,
                "currency": currency,
                "warehouse": warehouse,
                "customer": customer,
                "income_account": income_account,
                "expense_account": expense_account,
                "write_off_account": expense_account,
                "write_off_cost_center": frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}),
                "company_address": frappe.db.get_value("Address", {"is_your_company_address": 1}),
                "update_stock": 1,
                "item_groups": [{"item_group": ig} for ig in item_groups]
            })
            profile.insert(ignore_permissions=True)
        except Exception as e:
            print(f"Failed to create POS Profile 'StockBar Demo': {e}")

    # 5. Create Users
    print("Creating System Users...")
    demo_users = [
        {"email": "cajero@stockbar.local", "first_name": "Caja", "last_name": "Principal"},
        {"email": "encargado@stockbar.local", "first_name": "Encargado", "last_name": "Tienda"}
    ]

    for u in demo_users:
        if not frappe.db.exists("User", u["email"]):
            try:
                user = frappe.get_doc({
                    "doctype": "User",
                    "email": u["email"],
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                    "send_welcome_email": 0,
                    "roles": [{"role": "System Manager"}] # Fallback para que puedan hacer login y ver todo
                })
                user.insert(ignore_permissions=True)
                from frappe.utils.password import update_password
                update_password(user.name, "1234")
            except Exception as e:
                print(f"Failed to create User '{u['email']}': {e}")
                
    frappe.db.commit()
    frappe.logger("stockbar").info("Advanced Demo data generation complete!")
    print("✅ Demo data generation complete and committed successfully!")
