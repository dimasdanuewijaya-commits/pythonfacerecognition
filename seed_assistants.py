import os
import sys

# Tambahkan root path ke sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal, engine
from backend import models, auth

def seed_users():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    users_to_add = [
        {"name": "yudha", "email": "yudha@lab.com", "password": "password123", "role": "asisten"},
        {"name": "zidan", "email": "zidan@lab.com", "password": "password123", "role": "asisten"},
        {"name": "sony", "email": "sony@lab.com", "password": "password123", "role": "asisten"},
    ]
    
    for u in users_to_add:
        existing = db.query(models.User).filter(models.User.email == u["email"]).first()
        if not existing:
            new_user = models.User(
                name=u["name"],
                email=u["email"],
                password_hash=auth.get_password_hash(u["password"]),
                role=u["role"]
            )
            db.add(new_user)
            print(f"Added {u['name']} ({u['email']})")
        else:
            print(f"User {u['name']} already exists.")
            
    db.commit()
    db.close()
    print("Seeding completed.")

if __name__ == "__main__":
    seed_users()
