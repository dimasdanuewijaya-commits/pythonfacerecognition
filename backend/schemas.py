from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime


# ─── AUTH ─────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "asisten"
    rfid_uid: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    rfid_uid: Optional[str] = None
    photo_url: Optional[str] = None

class UserRfidUpdate(BaseModel):
    rfid_uid: str

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── SCHEDULE ───────────────────────────────────────────────────────────────
class ScheduleCreate(BaseModel):
    user_id: int
    day_of_week: str
    shift_number: int
    activity: str

class ScheduleResponse(BaseModel):
    id: int
    user_id: int
    day_of_week: str
    shift_number: int
    activity: str

    class Config:
        from_attributes = True


# ─── ATTENDANCE (Kiosk -> Server) ─────────────────────────────────────────
class ShiftInput(BaseModel):
    """Data shift yang dikirim dari Kiosk saat Absen Pulang"""
    shift_number: int           # 1-5
    shift_label: str            # "Shift 1 (07:30 - 09:10)"
    time_range: str             # "07:30 - 09:10"
    activity: str = "Kosong"    # "Teaching", "Piket", "Stand By", "Rapat", "Riset", "Kosong"
    points: float = 0.0

class AttendanceCreate(BaseModel):
    """Data yang dikirim Kiosk ke Server saat seseorang absen"""
    user_name: str              # Nama dari Face Recognition / RFID
    method: str = "face"        # "face" atau "rfid"
    attendance_type: str        # "datang" atau "pulang"
    shifts: Optional[List[ShiftInput]] = None  # Hanya diisi saat "pulang"


# ─── ATTENDANCE (Server -> Flutter) ───────────────────────────────────────
class ShiftResponse(BaseModel):
    shift_number: int
    shift_label: str
    time_range: str
    activity: str
    points: float
    is_active: bool

    class Config:
        from_attributes = True

class AttendanceResponse(BaseModel):
    """Format data yang diterima oleh Flutter untuk ditampilkan di AttendanceScreen"""
    id: int
    user_id: Optional[int] = None
    date: str                           # "Tuesday, 13 Aug 2024"
    check_in: Optional[str] = None      # "07:55 AM"
    check_out: Optional[str] = None     # "10:05 AM"
    method: str
    verified: bool
    shifts: List[ShiftResponse] = []

    class Config:
        from_attributes = True

class AttendanceListResponse(BaseModel):
    """Wrapper untuk daftar attendance"""
    total: int
    records: List[AttendanceResponse]


# ─── ANNOUNCEMENTS ────────────────────────────────────────────────────────
class AnnouncementCreate(BaseModel):
    title: str
    content: str
    tag: str = "INFO"

class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    tag: str
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ─── DASHBOARD STATS (Server -> Flutter HomeScreen) ──────────────────────
class DashboardStats(BaseModel):
    """Data statistik untuk HomeScreen Flutter"""
    total_hadir: int
    rank: int
    total_alpha: int
    poin_mutu: float
    total_hours_str: str = "0h 0m"
    gaji_bulan_ini: float
    recent_attendance: List[AttendanceResponse] = []
    latest_announcement: Optional[AnnouncementResponse] = None

class AdminDashboardStats(BaseModel):
    total_asisten: int
    avg_hadir: str
    hadir_hari_ini: int
    terlambat_hari_ini: int
    absen_hari_ini: int


# ─── SYSTEM MONITORING (Kiosk Heartbeat) ─────────────────────────────────
class SystemStatusReport(BaseModel):
    """Data yang dikirim Kiosk (Raspberry Pi) secara berkala ke Backend"""
    rpi_online: bool = True
    rfid_ok: bool = False
    buzzer_ok: bool = False
    led_ok: bool = False
    camera_ok: bool = False
    uptime_seconds: int = 0

class SystemStatusResponse(BaseModel):
    """Format data status sistem yang dikirim ke Flutter"""
    backend_online: bool = True
    database_online: bool = True
    rpi_online: bool = False
    rfid_ok: bool = False
    buzzer_ok: bool = False
    led_ok: bool = False
    camera_ok: bool = False
    last_heartbeat: Optional[str] = None
    uptime_seconds: int = 0
