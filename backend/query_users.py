import sys
import os
sys.path.append('backend')
from database import SessionLocal
from models import User
db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(f"ID: {u.id}, Name: {u.name}")
db.close()
