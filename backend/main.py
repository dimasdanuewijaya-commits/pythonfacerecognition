from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Optional

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
    
    # Buat Asisten default (sesuai dengan nama di Flutter & Kiosk)
    dimas = models.User(
        name="Dimas Danue Wijaya",
        email="dimas@lab.com",
        password_hash=auth.get_password_hash("dimas123"),
        role="asisten",
        rfid_uid="887577706921"  # UID kartu RFID yang terbaca di Raspberry Pi
    )
    
    db.add_all([admin, dimas])
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
    now = datetime.now().strftime("%I:%M %p")  # Format "07:55 AM"
    
    if data.attendance_type == "datang":
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
        
        # Simpan data shift jika ada
        if data.shifts:
            for s in data.shifts:
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
        
        db.commit()
        return {"status": "success", "message": f"Absen PULANG berhasil untuk {user.name}", "check_out": now}
    
    else:
        raise HTTPException(status_code=400, detail="attendance_type harus 'datang' atau 'pulang'")


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
    
    total_hadir = len(monthly_records)
    
    # Hitung total poin mutu bulan ini
    total_poin = 0
    for record in monthly_records:
        for shift in record.shifts:
            total_poin += shift.points
    
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
    
    return schemas.DashboardStats(
        total_hadir=total_hadir,
        total_izin=0,
        total_alpha=0,
        poin_mutu=total_poin,
        gaji_bulan_ini=gaji,
        recent_attendance=recent_list
    )


# ─── SWAP REQUESTS ────────────────────────────────────────────────────────
@app.post("/swap-requests/", response_model=schemas.SwapRequestResponse)
def create_swap_request(data: schemas.SwapRequestCreate, user_id: int, db: Session = Depends(get_db)):
    """Membuat permintaan tukar shift baru (Flutter -> Server)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    swap = models.SwapRequest(
        requester_id=user_id,
        target_assistant_name=data.target_assistant_name,
        course=data.course,
        date=data.date,
        shift=data.shift,
        reason=data.reason
    )
    db.add(swap)
    db.commit()
    db.refresh(swap)
    
    return schemas.SwapRequestResponse(
        id=swap.id,
        requester_name=user.name,
        target_assistant_name=swap.target_assistant_name,
        course=swap.course,
        date=swap.date,
        shift=swap.shift,
        reason=swap.reason,
        status=swap.status
    )


@app.get("/swap-requests/", response_model=List[schemas.SwapRequestResponse])
def get_swap_requests(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Mendapatkan daftar permintaan tukar shift (untuk SwapNotificationsScreen)"""
    query = db.query(models.SwapRequest)
    if user_id:
        query = query.filter(models.SwapRequest.requester_id == user_id)
    
    swaps = query.order_by(models.SwapRequest.created_at.desc()).all()
    
    result = []
    for s in swaps:
        user = db.query(models.User).filter(models.User.id == s.requester_id).first()
        result.append(schemas.SwapRequestResponse(
            id=s.id,
            requester_name=user.name if user else "Unknown",
            target_assistant_name=s.target_assistant_name,
            course=s.course,
            date=s.date,
            shift=s.shift,
            reason=s.reason,
            status=s.status
        ))
    
    return result


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "online",
        "app": "LabTrack Pro API",
        "version": "1.0.0",
        "message": "Server Backend Sistem Absensi Lab aktif dan siap menerima data!"
    }
