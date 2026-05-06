import os
import sys
from mongoengine import connect
from bson import ObjectId

# Add current directory to path
sys.path.append(os.getcwd())

from backend.models.inventory import StockTransaction

connect('accounts_db', host='mongodb://localhost:27017/accounts_db')

print(f"Total Stock Transactions: {StockTransaction.objects.count()}")
for t in StockTransaction.objects[:10]:
    print(f"Voucher: {t.voucher_id}, Item: {t.item_name}, Qty: {t.qty}")
