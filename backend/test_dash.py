from database import SessionLocal
import models
from main import get_dashboard

db = SessionLocal()
try:
    stats = get_dashboard(2, db)
    print(stats)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
