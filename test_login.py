import requests

url = "http://127.0.0.1:5000/login"
payload = {"student_number": "123", "password": "abc"}  # replace with actual student number/password

try:
    r = requests.post(url, json=payload)
    print("Status code:", r.status_code)
    print("Response text:", r.text)
except Exception as e:
    print("Error:", e)
