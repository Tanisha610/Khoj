import argparse
import sqlite3

from main import DATABASE_PATH, connection, hash_password


parser = argparse.ArgumentParser(description="Create a BioSense clinician account.")
parser.add_argument("name")
parser.add_argument("email")
parser.add_argument("password")
args = parser.parse_args()

with connection() as db:
    if db.execute("SELECT 1 FROM patients WHERE email=?", (args.email.lower(),)).fetchone():
        raise SystemExit("An account with that email already exists.")
    db.execute(
        """INSERT INTO patients
        (patient_id, full_name, email, password_hash, created_at, consent_at, role)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), 'clinician')""",
        ("CLINICIAN-" + args.email.split("@")[0][:12].upper(), args.name.strip(), args.email.lower(), hash_password(args.password)),
    )
    db.commit()
print("Clinician account created.")
