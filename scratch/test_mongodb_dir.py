import os
import subprocess
import time
from pymongo import MongoClient

mongod = r"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe"
dbpath = r"C:\data\db_test_spaces"
os.makedirs(dbpath, exist_ok=True)

# 1. Start mongod with --directoryperdb
cmd = [
    mongod,
    "--port", "27025",
    "--dbpath", dbpath,
    "--directoryperdb",
    "--logpath", os.path.join(dbpath, "mongod.log"),
    "--logappend"
]
proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)

# Wait for mongo to start
time.sleep(3)

try:
    client = MongoClient("mongodb://localhost:27025/", serverSelectionTimeoutMS=2000)
    # 2. Try creating a database with underscores and hyphens
    db_name = "Test_Company_2026-2027"
    db = client[db_name]
    db.test_coll.insert_one({"hello": "world"})
    print("Database list:", client.list_database_names())
    
    # 3. List directory contents
    print("Directory contents:")
    for item in os.listdir(dbpath):
        print(f" - {item}")
finally:
    # 4. Cleanup
    try:
        client.admin.command("shutdown")
    except Exception:
        pass
    proc.wait()
    # Remove files if needed
    import shutil
    shutil.rmtree(dbpath, ignore_errors=True)
