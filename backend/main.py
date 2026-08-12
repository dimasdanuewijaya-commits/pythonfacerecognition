from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, date
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
        return {"status": "success", "message": f"Absen DATANG berhasil untuk {user.name}", "check_in": now}
    
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
                        # Cek apakah dia Swap menggantikan orang lain (Tukar Guling)
                        # Artinya dia bertindak sebagai target_user, mengambil requester_schedule_id
                        swap = db.query(models.SwapRequest).filter(
                            models.SwapRequest.target_user_id == user.id,
                            models.SwapRequest.status == "approved",
                            models.SwapRequest.swap_date == today_str
                        ).first()
                        
                        if swap:
                            orig_sched = db.query(models.Schedule).filter(
                                models.Schedule.id == swap.requester_schedule_id,
                                models.Schedule.shift_number == s.shift_number
                            ).first()
                            
                            expected = orig_sched.activity if orig_sched else "Stand By"
                            if s.activity.lower() != expected.lower():
                                s.activity = f"{s.activity} (Batal: Jadwal Swap aslinya {expected})"
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
        total_rp = int(total_points * 7500)
        return {
            "status": "success", 
            "message": f"Absen PULANG berhasil untuk {user.name}", 
            "check_out": now,
            "total_points": total_points,
            "total_rp": total_rp
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
    # Hitung total izin (Permit) = Jumlah swap request APPROVED
    total_izin = db.query(models.SwapRequest).filter(
        models.SwapRequest.requester_id == user_id,
        models.SwapRequest.status == "approved"
    ).count()

    # Fetch latest announcement
    latest_announcement = db.query(models.Announcement).order_by(models.Announcement.created_at.desc()).first()
    announcement_resp = None
    if latest_announcement:
        announcement_resp = schemas.AnnouncementResponse.model_validate(latest_announcement)

    return schemas.DashboardStats(
        total_hadir=total_hadir,
        total_izin=total_izin,
        total_alpha=0,
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


# ─── SWAP REQUESTS ────────────────────────────────────────────────────────
@app.post("/swap-requests/", response_model=schemas.SwapRequestResponse)
def create_swap_request(data: schemas.SwapRequestCreate, user_id: int, db: Session = Depends(get_db)):
    """Membuat permintaan tukar shift baru (Tukar Guling)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    target_user = db.query(models.User).filter(models.User.id == data.target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target User tidak ditemukan")

    swap = models.SwapRequest(
        requester_id=user_id,
        target_user_id=data.target_user_id,
        requester_schedule_id=data.requester_schedule_id,
        target_schedule_id=data.target_schedule_id,
        swap_date=data.swap_date,
        reason=data.reason
    )
    db.add(swap)
    db.commit()
    db.refresh(swap)
    
    req_sched = db.query(models.Schedule).filter(models.Schedule.id == swap.requester_schedule_id).first()
    target_sched = db.query(models.Schedule).filter(models.Schedule.id == swap.target_schedule_id).first()
    
    req_detail = f"Shift {req_sched.shift_number} - {req_sched.activity}" if req_sched else "Unknown"
    tgt_detail = f"Shift {target_sched.shift_number} - {target_sched.activity}" if target_sched else "Unknown"
    
    return schemas.SwapRequestResponse(
        id=swap.id,
        requester_id=swap.requester_id,
        target_user_id=swap.target_user_id,
        requester_schedule_id=swap.requester_schedule_id,
        target_schedule_id=swap.target_schedule_id,
        swap_date=swap.swap_date,
        reason=swap.reason,
        status=swap.status,
        requester_name=user.name,
        target_name=target_user.name,
        requester_schedule_detail=req_detail,
        target_schedule_detail=tgt_detail
    )


@app.get("/swap-requests/", response_model=List[schemas.SwapRequestResponse])
def get_swap_requests(user_id: Optional[int] = None, type: str = "all", db: Session = Depends(get_db)):
    """
    type: 'incoming' (user as target), 'outgoing' (user as requester), 'all'
    """
    query = db.query(models.SwapRequest)
    if user_id:
        if type == "incoming":
            query = query.filter(models.SwapRequest.target_user_id == user_id)
        elif type == "outgoing":
            query = query.filter(models.SwapRequest.requester_id == user_id)
        else:
            query = query.filter((models.SwapRequest.requester_id == user_id) | (models.SwapRequest.target_user_id == user_id))
    
    swaps = query.order_by(models.SwapRequest.created_at.desc()).all()
    
    result = []
    for s in swaps:
        req_user = db.query(models.User).filter(models.User.id == s.requester_id).first()
        tgt_user = db.query(models.User).filter(models.User.id == s.target_user_id).first()
        req_sched = db.query(models.Schedule).filter(models.Schedule.id == s.requester_schedule_id).first()
        tgt_sched = db.query(models.Schedule).filter(models.Schedule.id == s.target_schedule_id).first()
        
        result.append(schemas.SwapRequestResponse(
            id=s.id,
            requester_id=s.requester_id,
            target_user_id=s.target_user_id,
            requester_schedule_id=s.requester_schedule_id,
            target_schedule_id=s.target_schedule_id,
            swap_date=s.swap_date,
            reason=s.reason,
            status=s.status,
            requester_name=req_user.name if req_user else "Unknown",
            target_name=tgt_user.name if tgt_user else "Unknown",
            requester_schedule_detail=f"Shift {req_sched.shift_number} - {req_sched.activity}" if req_sched else "Unknown",
            target_schedule_detail=f"Shift {tgt_sched.shift_number} - {tgt_sched.activity}" if tgt_sched else "Unknown"
        ))
    
    return result

class SwapRespond(BaseModel):
    status: str

@app.put("/swap-requests/{swap_id}/respond")
def respond_swap_request(swap_id: int, data: SwapRespond, db: Session = Depends(get_db)):
    """Asisten B menerima atau menolak permintaan (Tukar Guling)"""
    swap = db.query(models.SwapRequest).filter(models.SwapRequest.id == swap_id).first()
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request tidak ditemukan")
    
    if data.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status tidak valid")
        
    swap.status = data.status
    db.commit()
    return {"message": f"Swap request {data.status} successfully"}




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


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "online",
        "app": "LabTrack Pro API",
        "version": "1.0.0",
        "message": "Server Backend Sistem Absensi Lab aktif dan siap menerima data!"
    }
