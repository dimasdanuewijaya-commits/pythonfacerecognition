import requests

BASE_URL = "http://localhost:8000"

def test_endpoint(name, method, url, data=None):
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
            
        if response.status_code == 200:
            print(f"✅ {name}: OK ({response.status_code})")
        else:
            print(f"❌ {name}: Failed ({response.status_code}) - {response.text[:100]}")
    except Exception as e:
        print(f"⚠️ {name}: Error connecting - {e}")

print("--- MENGETES API ENDPOINTS KESIAPAN SISTEM ---")
test_endpoint("1. Server Status (Root)", "GET", f"{BASE_URL}/")
test_endpoint("2. Ambil Semua Asisten", "GET", f"{BASE_URL}/users")
test_endpoint("3. Ambil Semua Absensi", "GET", f"{BASE_URL}/attendance/")
test_endpoint("4. Ambil Jadwal User 1", "GET", f"{BASE_URL}/schedules/1")

print("\n--- MENGETES STATISTIK (DASHBOARD) ---")
test_endpoint("5. Ambil Dashboard Admin", "GET", f"{BASE_URL}/admin/dashboard/stats")
test_endpoint("6. Cek Status Kiosk", "GET", f"{BASE_URL}/system/status")

print("\n--- SELESAI ---")
