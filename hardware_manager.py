import time
import threading

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
                    
                    # Kita asumsikan saat ini semua kartu RFID yang berhasil dibaca = Dimas
                    # Nanti akan ditautkan ke Database asli.
                    callback(str(uid), "Dimas (Asisten)") 
                    break
        except Exception as e:
            print(f"[RFID Error] {e}")
        finally:
            self.is_scanning = False
            print("[RFID] Pemindaian dihentikan.")
