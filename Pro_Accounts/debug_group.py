from backend.models.ledger import Ledger
from backend.models.group import Group
from bson import ObjectId

def debug():
    l = Ledger.objects(name="Sunny").first()
    if l:
        g = Group.objects(id=l.group).first()
        print(f"Ledger: {l.name}, Group: {g.name}")

if __name__ == "__main__":
    debug()
