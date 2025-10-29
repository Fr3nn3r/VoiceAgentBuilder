"""
Test all three medical agent webhooks
"""
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv(override=True)

base_url = os.getenv("N8N_WEBHOOK_URL")

print("=" * 70)
print("TESTING ALL MEDICAL AGENT WEBHOOKS")
print("=" * 70)

# Test 1: Check Availability
print("\n[1/3] Testing check_availability...")
print("-" * 70)
url1 = f"{base_url}/check_availability"
payload1 = {
    "start_datetime": "2025-11-15T10:00:00",
    "end_datetime": "2025-11-15T10:30:00"
}
try:
    r1 = requests.post(url1, json=payload1, timeout=10)
    print(f"URL: {url1}")
    print(f"Status: {r1.status_code}")
    print(f"Response: {json.dumps(r1.json(), indent=2)}")
    print("✓ check_availability working!" if r1.status_code == 200 else "✗ Failed")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Book Appointment
print("\n[2/3] Testing book_appointment...")
print("-" * 70)
url2 = f"{base_url}/book_appointment"
payload2 = {
    "start_datetime": "2025-11-15T14:00:00",
    "end_datetime": "2025-11-15T14:30:00",
    "summary": "Medical Appointment | Jean Dupont"
}
try:
    r2 = requests.post(url2, json=payload2, timeout=10)
    print(f"URL: {url2}")
    print(f"Status: {r2.status_code}")
    print(f"Response: {json.dumps(r2.json(), indent=2)}")
    print("✓ book_appointment working!" if r2.status_code == 200 else "✗ Failed")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Log Appointment
print("\n[3/3] Testing log_appointment...")
print("-" * 70)
url3 = f"{base_url}/log_appointment"
payload3 = {
    "event": "Booked",
    "date": "2025-11-15",
    "start_time": "14:00",
    "end_time": "14:30",
    "patient_name": "Jean Dupont",
    "birth_date": "1980-05-15",
    "phone_number": "+33612345678",
    "reason": "Consultation générale"
}
try:
    r3 = requests.post(url3, json=payload3, timeout=10)
    print(f"URL: {url3}")
    print(f"Status: {r3.status_code}")
    print(f"Response: {json.dumps(r3.json(), indent=2)}")
    print("✓ log_appointment working!" if r3.status_code == 200 else "✗ Failed")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
