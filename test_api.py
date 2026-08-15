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
test_endpoint("1. Ambil Semua Asisten", "GET", f"{BASE_URL}/users/")
test_endpoint("2. Ambil Absensi Hari Ini", "GET", f"{BASE_URL}/attendance/today")
test_endpoint("3. Ambil Semua Jadwal Shift", "GET", f"{BASE_URL}/schedule/")
test_endpoint("4. Cek Data Asisten ID 1", "GET", f"{BASE_URL}/users/1")

print("\n--- MENGETES STATISTIK (DASHBOARD) ---")
test_endpoint("5. Ambil Rekap Bulanan", "GET", f"{BASE_URL}/attendance/stats/2026/8")

print("\n--- SELESAI ---")
