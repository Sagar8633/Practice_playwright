# helpers.py
import uuid

def generate_unique_email():
    return f"test_{uuid.uuid4().hex[:10]}@example.com"