import requests
import json
try:
    r = requests.get('http://127.0.0.1:8000/dashboard/2')
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
