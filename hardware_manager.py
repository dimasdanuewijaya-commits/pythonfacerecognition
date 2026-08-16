import time
import threading
import requests

# ─────────────────────────────────────────────────────────────────────────────
# MOCK CLASSES (For Mac/Windows Development)
# ─────────────────────────────────────────────────────────────────────────────
class MockLED:
    def __init__(self, color, pin):
        self.color = color
        self.pin = pin
        self.is_on = False

    def on(self):
        if not self.is_on:
            print(f"[MOCK HARDWARE] Lampu {self.color} (Pin {self.pin}) MENYALA")
            self.is_on = True

    def off(self):
        if self.is_on:
            # Only print OFF if we care about verbosity, skipping to keep logs clean
            self.is_on = False

class MockBuzzer:
    def __init__(self, pin):
        self.pin = pin

    def beep(self, on_time=0.1, off_time=0.1, n=1, background=True):
        print(f"[MOCK HARDWARE] BUZZER (Pin {self.pin}) berbunyi {n} kali")
        
    def on(self):
        print(f"[MOCK HARDWARE] BUZZER (Pin {self.pin}) MENYALA")
        
    def off(self):
        pass

class MockRFID:
    def read(self):
        # Mocks a blocking read. Waits 5 seconds then returns a dummy ID.
        print("[MOCK HARDWARE] Menunggu 5 detik untuk simulasi tap kartu...")
        time.sleep(5)
        return 123456789, "Dummy RFID Text"
        
# ─────────────────────────────────────────────────────────────────────────────
# HARDWARE IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
try:
    from gpiozero import LED, Buzzer
    IS_RPI = True
except ImportError:
    # If not on Raspberry Pi, use Mocks
    def LED(pin):
        # We deduce color based on our pin assignment
        if pin == 17: return MockLED("MERAH", pin)
        if pin == 27: return MockLED("KUNING", pin)
        if pin == 22: return MockLED("HIJAU", pin)
        return MockLED("UNKNOWN", pin)
        
    def Buzzer(pin):
        return MockBuzzer(pin)
        
    IS_RPI = False

try:
    from mfrc522 import SimpleMFRC522
except ImportError:
    SimpleMFRC522 = MockRFID


# ─────────────────────────────────────────────────────────────────────────────
# LED CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────
class LEDController:
    def __init__(self):
        self.red_led = LED(17)
        self.yellow_led = LED(27)
        self.green_led = LED(22)
        # Jika buzzer berbunyi terus, kemungkinan dia tipe Active LOW. 
        # Coba gunakan active_high=False atau True.
        try:
            self.buzzer = Buzzer(23, active_high=False)
        except Exception:
            self.buzzer = Buzzer(23)
        self.standby()

    def standby(self):
        """Set to Yellow (Waiting for user)."""
        self.red_led.off()
        self.green_led.off()
        self.yellow_led.on()

    def success(self, duration=3.0):
        """Flash Green for X seconds, beep once, then return to standby."""
        def routine():
            self.red_led.off()
            self.yellow_led.off()
            self.green_led.on()
            
            # Bunyi beep pendek 1 kali (0.3 detik)
            self.buzzer.beep(on_time=0.3, off_time=0.1, n=1, background=True)
            
            time.sleep(duration)
            self.standby()
            
        threading.Thread(target=routine, daemon=True).start()

    def error(self, duration=3.0):
        """Flash Red for X seconds, beep fast 3 times, then return to standby."""
        def routine():
            self.yellow_led.off()
            self.green_led.off()
            self.red_led.on()
            
            # Bunyi beep cepat 3 kali sebagai peringatan error
            self.buzzer.beep(on_time=0.1, off_time=0.1, n=3, background=True)
            
            time.sleep(duration)
            self.standby()
            
        threading.Thread(target=routine, daemon=True).start()

    def get_status(self):
        """Mengembalikan status hardware saat ini untuk Heartbeat report."""
        return {
            "led_ok": True,      # Kalau kita bisa instantiate LED, berarti OK
            "buzzer_ok": True,   # Kalau kita bisa instantiate Buzzer, berarti OK
            "is_rpi": IS_RPI,
        }

# ─────────────────────────────────────────────────────────────────────────────
# RFID READER
# ─────────────────────────────────────────────────────────────────────────────
class RFIDScanner:
    def __init__(self):
        self.reader = SimpleMFRC522()
        self.is_scanning = False
        self._scan_thread = None

    def start_scanning(self, success_callback):
        """
        Starts a background thread to scan for a card.
        When a card is found, it calls success_callback(uid).
        """
        if self.is_scanning:
            return
            
        self.is_scanning = True
        self._scan_thread = threading.Thread(target=self._scan_loop, args=(success_callback,), daemon=True)
        self._scan_thread.start()

    def stop_scanning(self):
        """Signals the scanning thread to stop."""
        self.is_scanning = False

    def _scan_loop(self, callback):
        try:
            print("[RFID] Memulai pemindaian kartu...")
            while self.is_scanning:
                # read() blocks until a card is detected.
                uid, text = self.reader.read()
                
                if uid and self.is_scanning:
                    print(f"[RFID] Kartu terdeteksi! UID: {uid}")
                    self.is_scanning = False # Auto stop after reading
                    
                    # Mengirimkan UID sebagai identitas ke API Backend. 
                    # Backend sudah pintar dan akan mencari nama User berdasarkan rfid_uid ini!
                    callback(str(uid), str(uid)) 
                    break
        except Exception as e:
            print(f"[RFID Error] {e}")
        finally:
            self.is_scanning = False
            print("[RFID] Pemindaian dihentikan.")


# ─────────────────────────────────────────────────────────────────────────────
# HEARTBEAT REPORTER (Melapor status ke Backend setiap 30 detik)
# ─────────────────────────────────────────────────────────────────────────────
class HeartbeatReporter:
    """
    Mengirim 'detak jantung' (heartbeat) ke Backend secara berkala.
    Ini memberi tahu Admin Dashboard bahwa Kiosk (Raspberry Pi) masih hidup
    dan semua komponen hardware berfungsi normal.
    """
    def __init__(self, backend_url="http://127.0.0.1:8000", interval=30):
        self.backend_url = backend_url
        self.interval = interval
        self._start_time = time.time()
        self._running = False
        self._thread = None
        
        # Status komponen (di-update dari luar)
        self.rfid_ok = False
        self.buzzer_ok = False
        self.led_ok = False
        self.camera_ok = False

    def start(self):
        """Mulai mengirim heartbeat di background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        print(f"[HEARTBEAT] Reporter dimulai. Interval: {self.interval} detik")

    def stop(self):
        """Hentikan heartbeat."""
        self._running = False

    def update_status(self, rfid_ok=None, buzzer_ok=None, led_ok=None, camera_ok=None):
        """Update status komponen dari script utama."""
        if rfid_ok is not None:
            self.rfid_ok = rfid_ok
        if buzzer_ok is not None:
            self.buzzer_ok = buzzer_ok
        if led_ok is not None:
            self.led_ok = led_ok
        if camera_ok is not None:
            self.camera_ok = camera_ok

    def _heartbeat_loop(self):
        while self._running:
            try:
                uptime = int(time.time() - self._start_time)
                payload = {
                    "rpi_online": True,
                    "rfid_ok": self.rfid_ok,
                    "buzzer_ok": self.buzzer_ok,
                    "led_ok": self.led_ok,
                    "camera_ok": self.camera_ok,
                    "uptime_seconds": uptime,
                }
                resp = requests.post(
                    f"{self.backend_url}/system/status",
                    json=payload,
                    timeout=5
                )
                if resp.status_code == 200:
                    print(f"[HEARTBEAT] ✓ Laporan terkirim (uptime: {uptime}s)")
                else:
                    print(f"[HEARTBEAT] ✗ Server merespon {resp.status_code}")
            except requests.exceptions.ConnectionError:
                print("[HEARTBEAT] ✗ Tidak bisa terhubung ke Backend")
            except Exception as e:
                print(f"[HEARTBEAT] ✗ Error: {e}")
            
            time.sleep(self.interval)
