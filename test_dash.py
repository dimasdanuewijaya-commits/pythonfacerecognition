import requests
import json
try:
    r = requests.get('https://transformation-outlined-stated-camera.trycloudflare.com/dashboard/2')
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
