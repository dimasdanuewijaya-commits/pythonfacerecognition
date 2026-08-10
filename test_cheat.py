from backend.database import SessionLocal
from backend import models
import datetime

db = SessionLocal()
# Create a dummy user
user = db.query(models.User).filter(models.User.email=="dimas_lagi@lab.com").first()
if not user:
    user = models.User(name="dimas_lagi", email="dimas_lagi@lab.com", password_hash="hash", role="asisten", rfid_uid="999")
    db.add(user)
    db.commit()

# Delete old attendance
db.query(models.Attendance).filter(models.Attendance.user_id==user.id).delete()
db.commit()

# Create dummy check_in at 09:01 AM today
today = datetime.date.today()
a = models.Attendance(user_id=user.id, date=today, check_in="09:01 AM", method="face", verified=True)
db.add(a)
db.commit()

import requests

payload = {
    "user_name": "dimas_lagi",
    "method": "face",
    "attendance_type": "pulang",
    "shifts": [
        {"shift_number": 1, "shift_label": "Shift 1", "time_range": "08:00 - 10:00", "activity": "Teaching", "points": 3},
        {"shift_number": 2, "shift_label": "Shift 2", "time_range": "10:00 - 12:00", "activity": "Piket", "points": 2},
        {"shift_number": 3, "shift_label": "Shift 3", "time_range": "12:00 - 14:00", "activity": "Stand By", "points": 1},
    ]
}

# we need to simulate current time as 11:50 AM to test.
# Let's mock datetime inside the main module temporarily? 
# Easier to just test the endpoint if we run it, but current time is 14:45.
# Let's just run it with current time (e.g. 14:50).
# If check_in is 09:01 AM and check_out is 02:50 PM, then shift 1, 2, 3, 4 are valid.
# So to test the boundary, let's make check_in = 11:50 AM and check_out = 12:50 PM.
# Then Shift 1 (08-10) -> check_in < 10 (11:50 < 10) FALSE -> Invalid!
# Shift 2 (10-12) -> check_in < 12 (11:50 < 12) TRUE, check_out > 10 (12:50 > 10) TRUE -> Valid!
# Shift 3 (12-14) -> check_in < 14 (11:50 < 14) TRUE, check_out > 12 (12:50 > 12) TRUE -> Valid!
# Shift 4 (14-16) -> check_in < 16 (11:50 < 16) TRUE, check_out > 14 (12:50 > 14) FALSE -> Invalid!
