"""
Test webhook configuration and connectivity
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

webhook_url = os.getenv("N8N_WEBHOOK_URL")
webhook_token = os.getenv("N8N_WEBHOOK_TOKEN", "")

print("=" * 60)
print("WEBHOOK CONFIGURATION TEST")
print("=" * 60)

print(f"\nBase URL: {webhook_url}")
print(f"Auth Token: {'Set' if webhook_token else 'Not set'}")

print("\n" + "=" * 60)
print("GENERATED ENDPOINT URLs:")
print("=" * 60)

endpoints = ["check_availability", "book_appointment", "log_appointment"]

for endpoint in endpoints:
    full_url = f"{webhook_url}/{endpoint}"
    print(f"\n{endpoint}:")
    print(f"  {full_url}")

print("\n" + "=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print("\n1. Create these webhook endpoints in n8n:")
for endpoint in endpoints:
    print(f"   - {endpoint}")

print("\n2. Test each endpoint with:")
print("   curl -X POST <url> -H 'Content-Type: application/json' -d '{...}'")

print("\n3. Once tested, switch to production by editing .env:")
print("   Comment out: N8N_WEBHOOK_URL=.../webhook-test")
print("   Uncomment: N8N_WEBHOOK_URL=.../webhook")

print("\n" + "=" * 60)
