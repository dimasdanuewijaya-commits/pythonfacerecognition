import os
import sys
import time
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.database import SessionLocal
from backend.models import User

def register_rfid():
    db = SessionLocal()
    users = db.query(User).all()
    
    if not users:
        print("Belum ada user di database! Jalankan seed_assistants.py dulu.")
        db.close()
        return

    print("===========================================")
    print("        DAFTAR USER / ASISTEN LAB")
    print("===========================================")
    for u in users:
        rfid_status = "[SUDAH ADA RFID]" if u.rfid_uid else "[BELUM ADA RFID]"
        print(f"ID: {u.id} | Nama: {u.name} | Email: {u.email} | {rfid_status}")
    print("===========================================")

    try:
        user_id = int(input("\nMasukkan ID User yang ingin didaftarkan RFID-nya: "))
    except ValueError:
        print("ID harus berupa angka!")
        db.close()
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print(f"User dengan ID {user_id} tidak ditemukan!")
        db.close()
        return

    print(f"\nMendaftarkan RFID untuk: {user.name} ({user.email})")
    print("Sedang memanaskan sensor RFID...")
    time.sleep(1)

    reader = SimpleMFRC522()

    print("\nStatus: SIAP!")
    print(f"Silakan tempelkan kartu/gantungan kunci RFID milik {user.name} ke sensor.")
    print("Tekan Ctrl+C untuk membatalkan.")
    print("-------------------------------------------")

    try:
        id, text = reader.read()
        rfid_uid_str = str(id)
        
        # Cek apakah kartu sudah dipakai orang lain
        existing_user = db.query(User).filter(User.rfid_uid == rfid_uid_str).first()
        if existing_user:
            if existing_user.id == user.id:
                print(f"\n[INFO] Kartu ini memang sudah terdaftar atas nama {user.name}!")
            else:
                print(f"\n[GAGAL] Kartu ini sudah dipakai oleh {existing_user.name}! Gunakan kartu lain.")
        else:
            user.rfid_uid = rfid_uid_str
            db.commit()
            print("\n[BERHASIL!] Kartu RFID berhasil didaftarkan!")
            print(f"Nama User : {user.name}")
            print(f"UID Kartu : {rfid_uid_str}")
            
    except KeyboardInterrupt:
        print("\nProses dibatalkan.")
    finally:
        GPIO.cleanup()
        db.close()
        print("Sistem dibersihkan.")

if __name__ == "__main__":
    register_rfid()
