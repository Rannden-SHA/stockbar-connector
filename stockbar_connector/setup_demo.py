import frappe

def create_demo_data():
    """
    Creates demo data for testing the StockBar Connector and URY POS.
    This includes test users, items, and settings.
    """
    frappe.logger("stockbar").info("Starting Demo Data generation...")

    # 1. Create a POS Profile if it doesn't exist
    if not frappe.db.exists("POS Profile", "StockBar Demo"):
        frappe.logger("stockbar").info("Creating POS Profile...")
        
        # Ensure default company, cost center, and warehouse exist (assuming standard ERPNext setup)
        company = frappe.defaults.get_user_default("Company")
        if not company:
            company = frappe.db.get_value("Company", {"is_group": 0})
            
        if not company:
            frappe.logger("stockbar").error("No Company found. Aborting demo structure.")
            return
            
        # Simplistic approach to grabbing standard records:
        currency = frappe.db.get_value("Company", company, "default_currency")
        
        # Try to get or create basic records for POS Profile
        warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
        customer = frappe.db.get_value("Customer", {"customer_group": "Commercial", "name": "POS Customer"})
        if not customer:
            customer_doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "POS Customer",
                "customer_group": "Commercial",
                "territory": "All Territories"
            })
            try:
                customer_doc.insert(ignore_permissions=True)
                customer = customer_doc.name
            except Exception as e:
                frappe.logger("stockbar").warning(f"Could not create demo POS Customer: {e}")
                
        income_account = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0})
        expense_account = frappe.db.get_value("Account", {"account_type": "Expense Account", "company": company, "is_group": 0})
        
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
            })
            profile.insert(ignore_permissions=True)
            frappe.logger("stockbar").info("POS Profile 'StockBar Demo' created.")
        except Exception as e:
            frappe.logger("stockbar").warning(f"Failed to create POS Profile 'StockBar Demo': {e}")


    # 2. Create Items
    demo_items = [
        {"item_code": "BEER-001", "item_name": "Craft Beer IPA", "item_group": "Products", "standard_rate": 5.50},
        {"item_code": "BEER-002", "item_name": "Stout Pint", "item_group": "Products", "standard_rate": 6.00},
        {"item_code": "FOOD-001", "item_name": "Nachos Supremo", "item_group": "Products", "standard_rate": 12.50},
        {"item_code": "FOOD-002", "item_name": "Classic Burger", "item_group": "Products", "standard_rate": 15.00},
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
                    "standard_rate": data["standard_rate"],
                    "taxes": []
                })
                item.insert(ignore_permissions=True)
                frappe.logger("stockbar").info(f"Item '{data['item_code']}' created.")
            except Exception as e:
                frappe.logger("stockbar").warning(f"Failed to create Item '{data['item_code']}': {e}")

    # 3. Create Users
    demo_users = [
        {"email": "cajero@stockbar.local", "first_name": "Caja", "last_name": "Principal", "role_profile_name": "StockBar POS User"},
        {"email": "encargado@stockbar.local", "first_name": "Encargado", "last_name": "Tienda", "role_profile_name": "StockBar Manager"}
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
                    "roles": [{"role": "System Manager"}] # Fallback basic roles. Better to map to real roles for URY
                })
                user.insert(ignore_permissions=True)
                # Ensure password is set to '1234'
                from frappe.utils.password import update_password
                update_password(user.name, "1234")
                frappe.logger("stockbar").info(f"User '{u['email']}' created with password '1234'.")
            except Exception as e:
                frappe.logger("stockbar").warning(f"Failed to create User '{u['email']}': {e}")
                
    frappe.db.commit()
    frappe.logger("stockbar").info("Demo data generation complete!")
    print("Demo data generation complete!")
