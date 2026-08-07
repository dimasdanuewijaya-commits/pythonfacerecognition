#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

print("===========================================")
print("      ALAT UJI COBA SENSOR RFID RC522")
print("===========================================")
print("Sedang memanaskan sensor...")
time.sleep(1)

reader = SimpleMFRC522()

print("Status: SIAP!")
print("Silakan tempelkan kartu putih / gantungan kunci biru Anda ke sensor.")
print("Tekan Ctrl+C untuk membatalkan.")
print("-------------------------------------------")

try:
    while True:
        # read() akan mengunci program sampai ada kartu yang menempel
        id, text = reader.read()
        print("\n[BERHASIL!] Kartu terdeteksi!")
        print(f"ID Kartu (UID): {id}")
        print(f"Teks di Kartu : {text}")
        print("-------------------------------------------")
        print("Silakan tempelkan kartu lain, atau tekan Ctrl+C untuk keluar.")
        
        # Jeda sebentar agar tidak membaca kartu yang sama berulang kali
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\nUji coba dihentikan.")
finally:
    GPIO.cleanup()
    print("Sistem dibersihkan.")
