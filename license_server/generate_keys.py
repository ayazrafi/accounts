import requests

SERVER_URL = "https://webrtc.bestie11.com"

def generate_keys(count=1, days=365, lic_type='single', max_acts=1):
    try:
        response = requests.post(f"{SERVER_URL}/generate", json={
            "count": count,
            "days": days,
            "type": lic_type,
            "max_activations": max_acts
        })
        if response.status_code == 200:
            keys = response.json().get("keys", [])
            print(f"\nGenerated {len(keys)} {lic_type.upper()} License Keys (Limit: {max_acts}):")
            for k in keys:
                print(f"  - {k}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Could not connect to server: {e}")

if __name__ == "__main__":
    print("--- License Key Generator ---")
    c = input("How many keys to generate? (default 1): ") or 1
    d = input("Duration in days? (default 365): ") or 365
    
    print("\nSelect License Type:")
    print("1. Server License (Runs local database and backend server + client app)")
    print("2. Client License (Runs only client app, connects to server)")
    choice = input("Choice (1/2): ") or "1"
    
    lic_type = "server" if choice == "1" else "client"
    default_max = 1 if lic_type == "server" else 10
    
    m = input(f"Max activations for each key? (default {default_max}): ") or default_max
    
    generate_keys(int(c), int(d), lic_type, int(m))
