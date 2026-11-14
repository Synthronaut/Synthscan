from refinery_db import load_inventory, add_haul_record, clear_inventory
from crafting_db import load_recipes, craft_item

# Reset and seed inventory
clear_inventory()
add_haul_record({"Quantainium": 2.0, "Titanium": 5.0}, source="test_seed")

recipes = load_recipes()
surge = next(r for r in recipes if r["id"] == "mod_surge")
print("Recipe:", surge["name"], surge["cost"])

# Craft 2x Surge Modules
ok, msg, deducted = craft_item(surge, count=2)
print("Craft 1 success:", ok)
print(msg)

inv = load_inventory()
print("Inventory after crafting 2x Surge (should be 1.5 Quantainium, 4.0 Titanium):")
print(inv["totals"])

# Attempt craft that exceeds remaining Quantainium (e.g. 10x Surge = 2.5 Quantainium required)
ok2, msg2, _ = craft_item(surge, count=10)
print("\nCraft 2 success (should fail):", ok2)
print(msg2)

clear_inventory()
print("Inventory cleared after test.")
