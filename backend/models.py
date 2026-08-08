from sqlalchemy import Column, Integer, String, Date, Time, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    """Tabel Pengguna (Asisten & Admin)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="asisten")  # "asisten" atau "admin"
    rfid_uid = Column(String, unique=True, nullable=True)  # UID kartu RFID (opsional)
    
    # Relasi ke tabel attendance
    attendances = relationship("Attendance", back_populates="user")


class Attendance(Base):
    """Tabel Riwayat Absensi - disesuaikan dengan data Flutter"""
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(String, nullable=True)   # "07:55 AM"
    check_out = Column(String, nullable=True)   # "10:05 AM"
    method = Column(String, default="face")     # "face" atau "rfid"
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relasi
    user = relationship("User", back_populates="attendances")
    shifts = relationship("AttendanceShift", back_populates="attendance", cascade="all, delete-orphan")


class AttendanceShift(Base):
    """Detail Shift per Hari Absensi - cocok dengan ShiftData di Flutter"""
    __tablename__ = "attendance_shifts"

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False)
    shift_number = Column(Integer, nullable=False)           # 1-5
    shift_label = Column(String, nullable=False)              # "Shift 1 (07:30 - 09:10)"
    time_range = Column(String, nullable=False)               # "07:30 - 09:10"
    activity = Column(String, default="Kosong")               # "Teaching", "Piket", "Stand By", "Rapat", "Riset", "Kosong"
    points = Column(Integer, default=0)                       # Poin mutu
    is_active = Column(Boolean, default=False)                # Apakah shift ini diambil?

    # Relasi
    attendance = relationship("Attendance", back_populates="shifts")


class SwapRequest(Base):
    """Permintaan Tukar Shift - cocok dengan NewSwapRequestScreen Flutter"""
    __tablename__ = "swap_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_assistant_name = Column(String, nullable=False)
    course = Column(String, nullable=False)        # "JKL - 2DC02-B"
    date = Column(String, nullable=False)           # "Oct 24, 2023"
    shift = Column(String, nullable=False)          # "SHIFT 1 08:00 AM - 10:00 AM"
    reason = Column(String, nullable=True)
    status = Column(String, default="pending")      # "pending", "approved", "rejected"
    created_at = Column(DateTime, default=datetime.utcnow)
