import os
import sys
import shutil
import time
from pymongo import MongoClient

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment variables for testing
test_dbpath = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db"))
os.environ["MONGO_DBPATH"] = test_dbpath
os.environ["DB_NAME"] = "test_pro_accounts"

# Remove existing test directory
shutil.rmtree(test_dbpath, ignore_errors=True)
os.makedirs(test_dbpath, exist_ok=True)

import backend.mongo_manager as mm
from backend.models.company import create_company, Company
from backend.database import company_db_name

# 1. Shutdown existing mongo on port 27021 if running
if mm.is_port_open():
    print("MongoDB port is open. Attempting to shut down existing instance...")
    try:
        client = MongoClient(f"mongodb://localhost:27021/", serverSelectionTimeoutMS=2000)
        client.admin.command("shutdown")
        client.close()
    except Exception as e:
        print(f"Could not shutdown running Mongo: {e}")
    time.sleep(2)

# Verify port is closed
if mm.is_port_open():
    print("Error: Port is still open.")
    sys.exit(1)

# Update DATA_DIR in mongo_manager
mm.DATA_DIR = test_dbpath

# 2. Start MongoDB
print("Starting MongoDB using mongo_manager...")
success = mm.ensure_mongodb_running(status_callback=print)
if not success:
    print("Failed to start MongoDB.")
    sys.exit(1)

try:
    # 3. Create a test company
    company_data = {
        "name": "Alpha Company",
        "fiscal_year_from": "2026-04-01",
        "fiscal_year_to": "2027-03-31",
        "address": "123 Main St",
        "phone": "555-0199",
        "email": "alpha@example.com"
    }
    
    print("\nCreating test company...")
    company_id = create_company(company_data)
    print(f"Company created with ID: {company_id}")
    
    # 4. Fetch the company and check db_name field
    company = Company.objects(id=company_id).first()
    print(f"Company Document db_name field: {company.db_name}")
    
    # 5. Resolve database name
    resolved_db_name = company_db_name(company_id)
    print(f"Resolved database name: {resolved_db_name}")
    
    # 6. Check directory contents of test_dbpath
    print("\nListing files inside main database folder:")
    items = os.listdir(test_dbpath)
    for item in items:
        is_dir = os.path.isdir(os.path.join(test_dbpath, item))
        print(f" - {item} [{'Directory' if is_dir else 'File'}]")
        
    expected_folder = "Alpha_Company_2026_2027"
    if expected_folder in items and os.path.isdir(os.path.join(test_dbpath, expected_folder)):
        print(f"\nSUCCESS: Created folder '{expected_folder}' for company and financial year!")
    else:
        print(f"\nFAILURE: Expected folder '{expected_folder}' was not found or is not a directory.")
        sys.exit(1)
        
finally:
    # 7. Shutdown mongo
    print("\nShutting down test MongoDB instance...")
    try:
        client = MongoClient(f"mongodb://localhost:27021/", serverSelectionTimeoutMS=2000)
        client.admin.command("shutdown")
        client.close()
    except Exception as e:
        print(f"Shutdown error: {e}")
    time.sleep(2)
    
    # Clean up test files
    shutil.rmtree(test_dbpath, ignore_errors=True)
    print("Test cleanup complete.")
