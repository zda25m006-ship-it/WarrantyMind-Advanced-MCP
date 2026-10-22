import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warrantymind.database import seed_demo_data

if __name__ == "__main__":
    seed_demo_data()
    print("WarrantyMind AI v3.1 database initialized and seeded successfully.")
    print("Demo Accounts:")
    print("  Customer   -> customer1   / Customer123!")
    print("  Technician -> technician1 / Tech123!")
    print("  Support    -> support1    / Support123!")
