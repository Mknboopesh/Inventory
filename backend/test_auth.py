import urllib.request
import urllib.error
import json

base = "http://localhost:8000"

def req(path, data):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                f"{base}{path}",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
        )
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "message": json.loads(e.read()).get("detail")}
    except Exception as e:
        return {"error": str(e)}

print("Register owner:", req("/api/auth/owner-register", {
    "companyName": "Test Co",
    "address": "123 Test St",
    "name": "Test Owner",
    "phone": "1234567890",
    "email": "test@test.com",
    "password": "Password123"
}))

print("Login owner:", req("/api/auth/login", {
    "companyName": "Test Co",
    "identity": "test@test.com",
    "password": "Password123"
}))

print("Register staff:", req("/api/auth/staff-register", {
    "companyName": "Test Co",
    "role": "manager",
    "name": "Test Staff",
    "phone": "0987654321",
    "email": "staff@test.com",
    "password": "Password123"
}))

print("Login staff:", req("/api/auth/login", {
    "companyName": "Test Co",
    "identity": "0987654321",
    "password": "Password123"
}))
