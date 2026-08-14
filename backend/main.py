from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File, Form
import os
import uuid
import shutil

import models
import schemas
import auth
from database import engine, get_db, Base

# ─── INISIALISASI ─────────────────────────────────────────────────────────
# Buat semua tabel di database secara otomatis
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LabTrack Pro API",
    description="Backend API untuk Sistem Absensi Lab berbasis Face Recognition & RFID",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Izinkan Flutter dan Kiosk untuk mengakses API ini dari mana saja
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── SEED DATA (Data Awal) ────────────────────────────────────────────────
@app.on_event("startup")
def seed_initial_data():
    """Membuat akun Admin dan Asisten default saat server pertama kali menyala"""
    db = next(get_db())
    
    # Cek apakah sudah ada user
    existing = db.query(models.User).first()
    if existing:
        return
    
    # Buat Admin default
    admin = models.User(
        name="Admin Lab",
        email="admin@lab.com",
        password_hash=auth.get_password_hash("admin123"),
        role="admin"
    )
    
    # Buat Asisten default (Dataset person 5)
    dimass = models.User(
        name="dimass",
        email="dimass@lab.com",
        password_hash=auth.get_password_hash("dimas123"),
        role="asisten",
        rfid_uid="111111111"
    )
    
    db.add_all([admin, dimass])
    db.commit()
    print("[SEED] Akun Admin dan Asisten berhasil dibuat!")
    db.close()


# ─── AUTH ENDPOINTS ────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login untuk Flutter App (Admin & Asisten)"""
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    
    if not user or not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah"
        )
    
    token = auth.create_access_token(data={"sub": str(user.id), "role": user.role})
    
    return schemas.TokenResponse(
        access_token=token,
        user=schemas.UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            rfid_uid=user.rfid_uid
        )
    )


@app.post("/auth/register", response_model=schemas.UserResponse)
def register_user(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Mendaftarkan user baru (hanya Admin yang boleh)"""
    existing = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    
    new_user = models.User(
        name=user_data.name,
        email=user_data.email,
        password_hash=auth.get_password_hash(user_data.password),
        role=user_data.role,
        rfid_uid=user_data.rfid_uid
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    """Mendapatkan daftar semua user (untuk Admin Dashboard)"""
    return db.query(models.User).all()

@app.put("/users/{user_id}/rfid", response_model=schemas.UserResponse)
def update_user_rfid(user_id: int, rfid_data: schemas.UserRfidUpdate, db: Session = Depends(get_db)):
    """Mendaftarkan atau mengupdate RFID untuk user tertentu"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    # Cek apakah RFID sudah dipakai oleh orang lain
    existing = db.query(models.User).filter(models.User.rfid_uid == rfid_data.rfid_uid).first()
    if existing and existing.id != user_id:
        raise HTTPException(status_code=400, detail=f"RFID ini sudah digunakan oleh {existing.name}")
        
    user.rfid_uid = rfid_data.rfid_uid
    db.commit()
    db.refresh(user)
    return user


# ─── ATTENDANCE ENDPOINTS (Kiosk -> Server) ────────────────────────────────
@app.post("/attendance/", response_model=dict)
def create_attendance(data: schemas.AttendanceCreate, db: Session = Depends(get_db)):
    """
    Endpoint utama yang dipanggil Kiosk saat seseorang absen.
    - Absen Datang: Buat record baru dengan check_in
    - Absen Pulang: Update record hari ini dengan check_out + data shift
    """
    # Cari user berdasarkan nama (dari Face Recognition) atau RFID UID
    user = db.query(models.User).filter(models.User.name == data.user_name).first()
    
    if not user:
        # Jika nama tidak ditemukan, coba cari lewat RFID
        user = db.query(models.User).filter(models.User.rfid_uid == data.user_name).first()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{data.user_name}' tidak ditemukan di database")
    
    today = date.today()
    current_dt = datetime.now()
    now = current_dt.strftime("%I:%M %p")  # Format "07:55 AM"
    
    if data.attendance_type == "datang":
        # Blokir absen datang jika sudah lewat jam 18:00
        if current_dt.hour >= 18:
            raise HTTPException(status_code=400, detail="Lab sudah tutup. Batas absen datang adalah jam 18:00.")

        # Cek apakah sudah absen hari ini
        existing = db.query(models.Attendance).filter(
            models.Attendance.user_id == user.id,
            models.Attendance.date == today
        ).first()
        
        if existing:
            return {"status": "warning", "message": f"{user.name} sudah absen datang hari ini"}
        
        new_attendance = models.Attendance(
            user_id=user.id,
            date=today,
            check_in=now,
            method=data.method,
            verified=True
        )
        db.add(new_attendance)
        db.commit()
        return {"status": "success", "message": f"Absen DATANG berhasil untuk {user.name}", "user_name": user.name, "check_in": now}
    
    elif data.attendance_type == "pulang":
        # Cari record hari ini
        attendance = db.query(models.Attendance).filter(
            models.Attendance.user_id == user.id,
            models.Attendance.date == today
        ).first()
        
        if not attendance:
            raise HTTPException(status_code=400, detail=f"{user.name} belum absen datang hari ini!")
        
        attendance.check_out = now
        
        # Hapus data shift lama jika ada (mencegah dobel kalau absen pulang berkali-kali)
        db.query(models.AttendanceShift).filter(models.AttendanceShift.attendance_id == attendance.id).delete()
        
        # Parsing jam check-in dan check-out untuk validasi shift (Anti-Cheat)
        check_in_time = datetime.strptime(attendance.check_in, "%I:%M %p").time()
        check_out_time = datetime.strptime(now, "%I:%M %p").time()

        # Hitung aktual total poin dan gaji berdasarkan shift yang benar-benar tersimpan dan sah
        total_points = 0
        # Ambil hari ini dan konversi ke Bahasa Indonesia
        eng_dow = date.today().strftime('%A')
        dow_map = {
            'Monday': 'Senin',
            'Tuesday': 'Selasa',
            'Wednesday': 'Rabu',
            'Thursday': 'Kamis',
            'Friday': 'Jumat',
            'Saturday': 'Sabtu',
            'Sunday': 'Minggu'
        }
        today_dow = dow_map.get(eng_dow, eng_dow)

        # Simpan data shift baru
        if data.shifts:
            for s in data.shifts:
                # Validasi jam shift
                try:
                    start_str, end_str = s.time_range.split(" - ")
                    shift_start = datetime.strptime(start_str.strip(), "%H:%M").time()
                    shift_end = datetime.strptime(end_str.strip(), "%H:%M").time()
                    
                    if not (check_in_time < shift_end and check_out_time > shift_start):
                        s.activity = f"{s.activity} (Di Luar Jam)"
                        s.points = 0
                    elif s.activity.lower() == "kosong":
                        s.activity = "Stand By (Otomatis)"
                        s.points = 1
                except Exception as e:
                    print(f"Error parsing time_range '{s.time_range}': {e}")
                
                # Validasi Jadwal & Swap jika lolos jam dan bukan Kosong
                if s.points > 0 and s.activity.lower() not in ["kosong", "stand by"]:
                    my_sched = db.query(models.Schedule).filter(
                        models.Schedule.user_id == user.id,
                        models.Schedule.day_of_week == today_dow,
                        models.Schedule.shift_number == s.shift_number
                    ).first()
                    
                    if my_sched:
                        db_activity = my_sched.activity.lower()
                        kiosk_activity = s.activity.lower()
                        
                        # Fix for Teaching: Kiosk sends "Teaching", DB has "Teaching - JKL - 3KB02-A"
                        is_match = False
                        if db_activity == kiosk_activity:
                            is_match = True
                        elif kiosk_activity == "teaching" and db_activity.startswith("teaching"):
                            is_match = True
                            
                        if is_match:
                            if kiosk_activity == "teaching":
                                # Cek keterlambatan (> 5 menit)
                                shift_start_mins = shift_start.hour * 60 + shift_start.minute
                                check_in_mins = check_in_time.hour * 60 + check_in_time.minute
                                if check_in_mins - shift_start_mins > 5:
                                    s.activity = f"{s.activity} (Late)"
                        else:
                            s.activity = f"{s.activity} (Batal: Jadwal aslinya {my_sched.activity})"
                            s.points = 0
                    else:
                        s.activity = f"{s.activity} (Batal: Tidak ada jadwal)"
                        s.points = 0

                shift = models.AttendanceShift(
                    attendance_id=attendance.id,
                    shift_number=s.shift_number,
                    shift_label=s.shift_label,
                    time_range=s.time_range,
                    activity=s.activity,
                    points=s.points,
                    is_active=s.points > 0
                )
                db.add(shift)
                total_points += s.points
        
        db.commit()
        
        # Format respons untuk aplikasi
        return {
            "status": "success", 
            "message": f"Absen PULANG berhasil untuk {user.name}", 
            "user_name": user.name,
            "check_out": now, 
            "total_points": round(total_points, 2), 
            "estimated_salary": int(total_points * 7500)
        }
    
    else:
        raise HTTPException(status_code=400, detail="attendance_type harus 'datang' atau 'pulang'")


# ─── SCHEDULE ENDPOINTS ───────────────────────────────────────────────────
@app.post("/schedules/", response_model=schemas.ScheduleResponse)
def create_schedule(sched: schemas.ScheduleCreate, db: Session = Depends(get_db)):
    """Membuat jadwal mingguan baru untuk asisten"""
    new_sched = models.Schedule(
        user_id=sched.user_id,
        day_of_week=sched.day_of_week,
        shift_number=sched.shift_number,
        activity=sched.activity
    )
    db.add(new_sched)
    db.commit()
    db.refresh(new_sched)
    return new_sched

@app.get("/schedules/{user_id}", response_model=List[schemas.ScheduleResponse])
def get_schedules(user_id: int, db: Session = Depends(get_db)):
    """Melihat jadwal asisten tertentu"""
    schedules = db.query(models.Schedule).filter(models.Schedule.user_id == user_id).all()
    return schedules

@app.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Menghapus jadwal asisten"""
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    db.delete(sched)
    db.commit()
    return {"message": "Jadwal berhasil dihapus"}


# ─── ATTENDANCE ENDPOINTS (Server -> Flutter) ─────────────────────────────
@app.get("/attendance/", response_model=schemas.AttendanceListResponse)
def get_attendance_history(
    user_id: Optional[int] = None,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Mendapatkan riwayat absensi (untuk Flutter AttendanceScreen)"""
    query = db.query(models.Attendance)
    
    if user_id:
        query = query.filter(models.Attendance.user_id == user_id)
    
    records = query.order_by(models.Attendance.date.desc()).limit(limit).all()
    
    result = []
    for record in records:
        # Format tanggal sesuai Flutter: "Tuesday, 13 Aug 2024"
        formatted_date = record.date.strftime("%A, %d %b %Y")
        
        shifts_data = []
        for s in record.shifts:
            shifts_data.append(schemas.ShiftResponse(
                shift_number=s.shift_number,
                shift_label=s.shift_label,
                time_range=s.time_range,
                activity=s.activity,
                points=s.points,
                is_active=s.is_active
            ))
        
        result.append(schemas.AttendanceResponse(
            id=record.id,
            user_id=record.user_id,
            date=formatted_date,
            check_in=record.check_in,
            check_out=record.check_out,
            method=record.method,
            verified=record.verified,
            shifts=shifts_data
        ))
    
    return schemas.AttendanceListResponse(total=len(result), records=result)


# ─── DASHBOARD STATS (Server -> Flutter HomeScreen) ──────────────────────
@app.get("/dashboard/{user_id}", response_model=schemas.DashboardStats)
def get_dashboard(user_id: int, db: Session = Depends(get_db)):
    """Statistik untuk Flutter HomeScreen (Total Hadir, Poin, Gaji, dll)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    # Hitung total kehadiran bulan ini
    today = date.today()
    first_day = today.replace(day=1)
    
    monthly_records = db.query(models.Attendance).filter(
        models.Attendance.user_id == user_id,
        models.Attendance.date >= first_day,
        models.Attendance.date <= today
    ).all()
    
    total_hadir = db.query(models.Attendance).filter(
        models.Attendance.user_id == user_id,
        models.Attendance.date >= first_day,
        models.Attendance.date <= today,
        models.Attendance.check_out != None
    ).count()
    
    # Hitung total poin mutu bulan ini dan total durasi di lab
    total_poin = 0
    total_seconds = 0
    for record in monthly_records:
        for shift in record.shifts:
            total_poin += shift.points
            
        if record.check_in and record.check_out:
            try:
                cin = datetime.strptime(record.check_in, "%I:%M %p")
                cout = datetime.strptime(record.check_out, "%I:%M %p")
                diff = cout - cin
                total_seconds += diff.total_seconds()
            except Exception:
                pass
                
    total_hours = int(total_seconds // 3600)
    total_minutes = int((total_seconds % 3600) // 60)
    total_hours_str = f"{total_hours}h {total_minutes}m"
    
    # Hitung gaji (Rp 7.500 per poin mutu - sesuai Kiosk)
    RUPIAH_PER_MUTU = 7500
    gaji = total_poin * RUPIAH_PER_MUTU
    
    # Ambil 5 riwayat absen terakhir untuk preview
    recent = db.query(models.Attendance).filter(
        models.Attendance.user_id == user_id
    ).order_by(models.Attendance.date.desc()).limit(5).all()
    
    recent_list = []
    for r in recent:
        formatted_date = r.date.strftime("%A, %d %b %Y")
        shifts_data = [schemas.ShiftResponse(
            shift_number=s.shift_number, shift_label=s.shift_label,
            time_range=s.time_range, activity=s.activity,
            points=s.points, is_active=s.is_active
        ) for s in r.shifts]
        
        recent_list.append(schemas.AttendanceResponse(
            id=r.id, date=formatted_date, check_in=r.check_in,
            check_out=r.check_out, method=r.method,
            verified=r.verified, shifts=shifts_data
        ))
    # Hitung Rank (Total jam terbanyak dari semua asisten bulan ini)
    all_users = db.query(models.User).all()
    user_durations = []
    
    for u in all_users:
        u_records = db.query(models.Attendance).filter(
            models.Attendance.user_id == u.id,
            models.Attendance.date >= first_day,
            models.Attendance.date <= today
        ).all()
        
        u_seconds = 0
        for r in u_records:
            if r.check_in and r.check_out:
                try:
                    cin = datetime.strptime(r.check_in, "%I:%M %p")
                    cout = datetime.strptime(r.check_out, "%I:%M %p")
                    diff = cout - cin
                    u_seconds += diff.total_seconds()
                except Exception:
                    pass
        
        user_durations.append({"user_id": u.id, "seconds": u_seconds})
        
    # Urutkan berdasarkan seconds (descending)
    user_durations.sort(key=lambda x: x["seconds"], reverse=True)
    
    # Cari rank user ini
    rank = 1
    for idx, stat in enumerate(user_durations):
        if stat["user_id"] == user_id:
            rank = idx + 1
            break

    # Hitung Total Alpha (Hanya untuk Teaching dan Piket)
    user_schedules = db.query(models.Schedule).filter(models.Schedule.user_id == user_id).all()
    
    # Kumpulkan hari di mana ada jadwal Teaching atau Piket
    scheduled_days = set()
    for s in user_schedules:
        act = s.activity.lower()
        if act.startswith("teaching") or act == "piket":
            scheduled_days.add(s.day_of_week.lower())
    
    eng_to_indo_day = {
        0: 'senin', 1: 'selasa', 2: 'rabu', 3: 'kamis',
        4: 'jumat', 5: 'sabtu', 6: 'minggu'
    }
    
    total_alpha = 0
    yesterday = today - timedelta(days=1)
    
    # Jangan hitung alpha sebelum akun dibuat
    start_date = first_day
    if user.created_at:
        user_created_date = user.created_at.date()
        if user_created_date > start_date:
            start_date = user_created_date
    
    current_date = start_date
    while current_date <= yesterday:
        day_name = eng_to_indo_day[current_date.weekday()]
        
        # Jika asisten punya jadwal Teaching/Piket di hari itu
        if day_name in scheduled_days:
            # Cek apakah dia absen pulang di hari tersebut
            has_attendance = any(r.date == current_date and r.check_out is not None for r in monthly_records)
            if not has_attendance:
                total_alpha += 1
                    
        current_date += timedelta(days=1)

    # Fetch latest announcement
    latest_announcement = db.query(models.Announcement).order_by(models.Announcement.created_at.desc()).first()
    announcement_resp = None
    if latest_announcement:
        announcement_resp = schemas.AnnouncementResponse.model_validate(latest_announcement)

    return schemas.DashboardStats(
        total_hadir=total_hadir,
        rank=rank,
        total_alpha=total_alpha,
        poin_mutu=total_poin,
        total_hours_str=total_hours_str,
        gaji_bulan_ini=gaji,
        recent_attendance=recent_list,
        latest_announcement=announcement_resp
    )


# ─── ANNOUNCEMENTS ────────────────────────────────────────────────────────
@app.post("/announcements/", response_model=schemas.AnnouncementResponse)
def create_announcement(
    title: str = Form(...),
    content: str = Form(...),
    tag: str = Form("INFO"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Membuat pengumuman baru dari Admin (dengan gambar opsional)"""
    
    image_url = None
    if image and image.filename:
        ext = image.filename.split('.')[-1]
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join("static", "announcements", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_url = f"/static/announcements/{filename}"

    new_announcement = models.Announcement(
        title=title,
        content=content,
        tag=tag,
        image_url=image_url
    )
    db.add(new_announcement)
    db.commit()
    db.refresh(new_announcement)
    return new_announcement

@app.get("/announcements/", response_model=List[schemas.AnnouncementResponse])
def get_announcements(db: Session = Depends(get_db)):
    """Mendapatkan daftar semua pengumuman dari yang terbaru"""
    return db.query(models.Announcement).order_by(models.Announcement.created_at.desc()).all()






# ─── AUTH ─────────────────────────────────────────────────────────
@app.put("/auth/change-password/{user_id}")
def change_password(user_id: int, req: schemas.ChangePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not auth.verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
        
    user.password_hash = auth.get_password_hash(req.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


# ─── SYSTEM MONITORING (Kiosk Heartbeat) ──────────────────────────────────
# Simpan status terakhir dari Kiosk di memory (tidak perlu database)
_kiosk_status = {
    "rpi_online": False,
    "rfid_ok": False,
    "buzzer_ok": False,
    "led_ok": False,
    "camera_ok": False,
    "last_heartbeat": None,
    "uptime_seconds": 0,
}

@app.post("/system/status")
def report_system_status(report: schemas.SystemStatusReport):
    """Endpoint untuk Kiosk (Raspberry Pi) melapor status hardware-nya"""
    _kiosk_status["rpi_online"] = report.rpi_online
    _kiosk_status["rfid_ok"] = report.rfid_ok
    _kiosk_status["buzzer_ok"] = report.buzzer_ok
    _kiosk_status["led_ok"] = report.led_ok
    _kiosk_status["camera_ok"] = report.camera_ok
    _kiosk_status["uptime_seconds"] = report.uptime_seconds
    _kiosk_status["last_heartbeat"] = datetime.now().isoformat()
    return {"status": "ok", "message": "Heartbeat received"}

@app.get("/system/status", response_model=schemas.SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    """Endpoint untuk Flutter Admin Dashboard mengecek status semua komponen"""
    # Cek apakah database bisa diakses
    db_online = True
    try:
        db.execute(models.User.__table__.select().limit(1))
    except Exception:
        db_online = False
    
    # Cek apakah Kiosk masih online (heartbeat terakhir < 60 detik)
    rpi_online = False
    if _kiosk_status["last_heartbeat"]:
        last_hb = datetime.fromisoformat(_kiosk_status["last_heartbeat"])
        if (datetime.now() - last_hb).total_seconds() < 60:
            rpi_online = _kiosk_status["rpi_online"]
    
    return schemas.SystemStatusResponse(
        backend_online=True,
        database_online=db_online,
        rpi_online=rpi_online,
        rfid_ok=_kiosk_status["rfid_ok"] if rpi_online else False,
        buzzer_ok=_kiosk_status["buzzer_ok"] if rpi_online else False,
        led_ok=_kiosk_status["led_ok"] if rpi_online else False,
        camera_ok=_kiosk_status["camera_ok"] if rpi_online else False,
        last_heartbeat=_kiosk_status["last_heartbeat"],
        uptime_seconds=_kiosk_status["uptime_seconds"] if rpi_online else 0,
    )


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "online",
        "app": "LabTrack Pro API",
        "version": "1.0.0",
        "message": "Server Backend Sistem Absensi Lab aktif dan siap menerima data!"
    }

