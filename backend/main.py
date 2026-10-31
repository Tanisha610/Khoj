import csv
import io
import logging
import math
import random
import secrets
import sqlite3
from datetime import datetime, date, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from generate_dataset import FIELDNAMES, ensure_dataset

DATABASE_PATH = Path(os.environ.get("BIOSENSE_DATABASE_PATH", Path(__file__).with_name("biosense.db")))
DATASET_PATH = Path(__file__).with_name("synthetic_pcna_dataset.csv")
SESSION_COOKIE = "biosense_session"
SESSION_DAYS = 7
SESSION_SECRET = os.environ.get("BIOSENSE_SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_COOKIE_SAMESITE = os.environ.get("BIOSENSE_COOKIE_SAMESITE", "lax").lower()
if SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise ValueError("BIOSENSE_COOKIE_SAMESITE must be lax, strict, or none.")
SESSION_COOKIE_SECURE = os.environ.get("BIOSENSE_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
if SESSION_COOKIE_SAMESITE == "none" and not SESSION_COOKIE_SECURE:
    raise ValueError("BIOSENSE_COOKIE_SECURE must be true when BIOSENSE_COOKIE_SAMESITE is none.")
DEVICE_ID = "VS-001"
ADC_MAX = 4095
ADC_REFERENCE_V = 3.3
TIA_RESISTANCE_OHM = 100_000
SAMPLE_COUNT = 20
FILTER_WINDOW = 3
SIMULATION_DISCLAIMER = (
    "Software-only synthetic demonstration. Values are hypothetical and are not "
    "actual patient measurements, experimentally validated PCNA measurements, "
    "a diagnosis, or a clinical result."
)
logger = logging.getLogger(__name__)
DATASET_ROWS: list[dict] = []
DATASET_ERROR: str | None = None
app = FastAPI(title="BioSense Patient Portal API", version="2.0.0")
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5177",
    "http://127.0.0.1:5177",
)
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("BIOSENSE_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


def connection():
    # FastAPI may execute synchronous handlers in worker threads.
    db = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def get_db():
    db = connection()
    try:
        yield db
    finally:
        db.close()


def init_db():
    with connection() as db:
        for table, required in (("patients", "full_name"), ("readings", "patient_id")):
            columns = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
            if columns and required not in columns:
                legacy_name = f"legacy_{table}"
                suffix = 1
                while db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (legacy_name,),
                ).fetchone():
                    suffix += 1
                    legacy_name = f"legacy_{table}_{suffix}"
                db.execute(f"ALTER TABLE {table} RENAME TO {legacy_name}")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                consent_at TEXT NOT NULL,
                date_of_birth TEXT,
                sex TEXT,
                phone TEXT,
                role TEXT NOT NULL DEFAULT 'patient'
            );
            CREATE TABLE IF NOT EXISTS patient_assessments (
                patient_id INTEGER PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
                weight_kg REAL, height_cm REAL, bmi REAL,
                breast_cancer_family_history TEXT,
                affected_relative TEXT, relative_diagnosis_age INTEGER,
                ovarian_cancer_family_history TEXT,
                currently_pregnant TEXT, currently_breastfeeding TEXT,
                prior_breast_diagnosis TEXT,
                prior_breast_investigation TEXT,
                additional_history TEXT, prefer_not_to_answer INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS readings (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                device_id TEXT NOT NULL, test_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL, sample_number INTEGER NOT NULL,
                raw_signal REAL NOT NULL, filtered_signal REAL NOT NULL,
                signal_quality TEXT NOT NULL, simulation_mode INTEGER NOT NULL,
                scenario TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clinician_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                clinician_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS biosense_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL UNIQUE,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                test_status TEXT NOT NULL,
                simulation_mode INTEGER NOT NULL DEFAULT 1,
                sample_id TEXT NOT NULL,
                hypothetical_pcna_ng_ml REAL NOT NULL,
                simulated_current_uA REAL NOT NULL,
                filtered_current_uA REAL NOT NULL DEFAULT 0,
                simulated_voltage_V REAL NOT NULL,
                raw_adc_counts INTEGER NOT NULL,
                filtered_adc_counts INTEGER NOT NULL,
                signal_quality TEXT NOT NULL,
                sample_count INTEGER NOT NULL,
                quality_explanation TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_biosense_tests_patient_timestamp
                ON biosense_tests(patient_id, timestamp DESC);
            CREATE TABLE IF NOT EXISTS sensor_readings (
                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL REFERENCES biosense_tests(test_id) ON DELETE CASCADE,
                sample_number INTEGER NOT NULL,
                simulated_current_uA REAL NOT NULL,
                filtered_current_uA REAL NOT NULL DEFAULT 0,
                simulated_voltage_V REAL NOT NULL,
                raw_adc_counts INTEGER NOT NULL,
                filtered_adc_counts INTEGER NOT NULL,
                signal_quality TEXT NOT NULL,
                quality_explanation TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(test_id, sample_number)
            );
            CREATE INDEX IF NOT EXISTS idx_sensor_readings_test_sample
                ON sensor_readings(test_id, sample_number);
            CREATE TABLE IF NOT EXISTS test_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL UNIQUE REFERENCES biosense_tests(test_id) ON DELETE CASCADE,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                report_timestamp TEXT NOT NULL,
                technical_result TEXT NOT NULL,
                simulation_disclaimer TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_test_reports_patient
                ON test_reports(patient_id, report_timestamp DESC);
            CREATE TABLE IF NOT EXISTS device_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL REFERENCES readings(test_id) ON DELETE CASCADE,
                patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sample_number INTEGER NOT NULL,
                raw_signal REAL NOT NULL,
                filtered_signal REAL NOT NULL,
                signal_quality TEXT NOT NULL,
                simulation_mode INTEGER NOT NULL,
                scenario TEXT,
                UNIQUE(test_id, sample_number)
            );
            CREATE INDEX IF NOT EXISTS idx_device_samples_test
                ON device_samples(test_id, sample_number);
            """
        )
        patient_columns = {r["name"] for r in db.execute("PRAGMA table_info(patients)")}
        if "role" not in patient_columns:
            db.execute("ALTER TABLE patients ADD COLUMN role TEXT NOT NULL DEFAULT 'patient'")
        assessment_columns = {r["name"] for r in db.execute("PRAGMA table_info(patient_assessments)")}
        for column in ("currently_pregnant", "currently_breastfeeding"):
            if column not in assessment_columns:
                db.execute(f"ALTER TABLE patient_assessments ADD COLUMN {column} TEXT")
        test_columns = {r["name"] for r in db.execute("PRAGMA table_info(biosense_tests)")}
        if "filtered_current_uA" not in test_columns:
            db.execute("ALTER TABLE biosense_tests ADD COLUMN filtered_current_uA REAL NOT NULL DEFAULT 0")
            db.execute(
                "UPDATE biosense_tests SET filtered_current_uA=simulated_current_uA"
            )
        sample_columns = {r["name"] for r in db.execute("PRAGMA table_info(sensor_readings)")}
        if "filtered_current_uA" not in sample_columns:
            db.execute("ALTER TABLE sensor_readings ADD COLUMN filtered_current_uA REAL NOT NULL DEFAULT 0")
            db.execute(
                """UPDATE sensor_readings AS current SET filtered_current_uA=(
                    SELECT AVG(previous.simulated_current_uA) FROM sensor_readings previous
                    WHERE previous.test_id=current.test_id
                    AND previous.sample_number BETWEEN current.sample_number-2 AND current.sample_number
                )"""
            )


init_db()


def load_synthetic_dataset() -> None:
    global DATASET_ROWS, DATASET_ERROR
    try:
        ensure_dataset(DATASET_PATH)
        with DATASET_PATH.open(newline="", encoding="utf-8") as dataset_file:
            reader = csv.DictReader(dataset_file)
            missing = set(FIELDNAMES) - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")
            rows = list(reader)
        if not rows:
            raise ValueError("Dataset contains no records.")
        sample_ids = set()
        for row in rows:
            if not row.get("sample_id", "").strip() or row["sample_id"] in sample_ids:
                raise ValueError("Dataset sample IDs must be present and unique.")
            sample_ids.add(row["sample_id"])
            for name in FIELDNAMES[1:6]:
                row[name] = float(row[name]) if name in FIELDNAMES[1:4] else int(row[name])
            if not all(math.isfinite(row[name]) for name in FIELDNAMES[1:4]):
                raise ValueError("Dataset contains a non-finite concentration, current, or voltage.")
            if row["hypothetical_pcna_ng_ml"] < 0 or row["simulated_current_uA"] < 0:
                raise ValueError("Dataset concentration and current values must be non-negative.")
            if not 0 <= row["simulated_voltage_V"] <= ADC_REFERENCE_V:
                raise ValueError("Dataset voltage is outside the configured ADC reference range.")
            if not 0 <= row["raw_adc_counts"] <= ADC_MAX or not 0 <= row["filtered_adc_counts"] <= ADC_MAX:
                raise ValueError("Dataset ADC counts are outside the configured 12-bit range.")
            if row["signal_quality"] not in {"VALID", "INVALID"}:
                raise ValueError("Dataset contains an unsupported signal_quality value.")
        DATASET_ROWS = rows
        DATASET_ERROR = None
    except (OSError, csv.Error, ValueError, TypeError) as error:
        DATASET_ROWS = []
        DATASET_ERROR = str(error)
        logger.exception("Could not load synthetic PCNA dataset")


load_synthetic_dataset()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError):
        return False


def public_patient(row):
    return {k: row[k] for k in ("patient_id", "full_name", "email", "created_at", "consent_at", "date_of_birth", "sex", "phone", "role")}


def new_session(db, patient_id, response):
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token_hash, patient_id, expires.isoformat()))
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        max_age=SESSION_DAYS * 86400,
    )


def current_patient(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: sqlite3.Connection = Depends(get_db),
):
    if not session:
        raise HTTPException(401, "Please log in to continue.")
    token_hash = hashlib.sha256(session.encode()).hexdigest()
    row = db.execute(
        "SELECT p.* FROM patients p JOIN sessions s ON s.patient_id=p.id WHERE s.token_hash=? AND s.expires_at>?",
        (token_hash, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    if not row:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return row


def current_clinician(patient=Depends(current_patient)):
    if patient["role"] != "clinician":
        raise HTTPException(403, "Clinician access is required.")
    return patient


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    consent: bool
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.lower().strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @model_validator(mode="after")
    def validate_registration(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if not self.consent:
            raise ValueError("Consent is required.")
        return self


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=30)


class AssessmentUpdate(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    height_cm: float | None = Field(default=None, gt=0, le=300)
    breast_cancer_family_history: Literal["yes", "no", "not_sure", "prefer_not_to_say"] | None = None
    affected_relative: str | None = Field(default=None, max_length=80)
    relative_diagnosis_age: int | None = Field(default=None, ge=0, le=120)
    ovarian_cancer_family_history: Literal["yes", "no", "not_sure", "prefer_not_to_say"] | None = None
    currently_pregnant: Literal["yes", "no", "not_sure", "prefer_not_to_say"] | None = None
    currently_breastfeeding: Literal["yes", "no", "not_sure", "prefer_not_to_say"] | None = None
    prior_breast_diagnosis: str | None = Field(default=None, max_length=500)
    prior_breast_investigation: str | None = Field(default=None, max_length=500)
    additional_history: str | None = Field(default=None, max_length=1000)
    prefer_not_to_answer: bool = False

    @model_validator(mode="after")
    def validate_measurements(self):
        if (self.weight_kg is None) != (self.height_cm is None) and not self.prefer_not_to_answer:
            raise ValueError("Provide both weight and height, or leave both blank.")
        answers = (
            self.weight_kg, self.height_cm, self.breast_cancer_family_history,
            self.affected_relative, self.relative_diagnosis_age,
            self.ovarian_cancer_family_history, self.currently_pregnant,
            self.currently_breastfeeding, self.prior_breast_diagnosis,
            self.prior_breast_investigation, self.additional_history,
        )
        if not self.prefer_not_to_answer and not any(
            value is not None and (not isinstance(value, str) or value.strip())
            for value in answers
        ):
            raise ValueError("Answer at least one question or choose to decline the optional health questions.")
        return self


class SimulationRequest(BaseModel):
    scenario: Literal["random", "valid", "invalid"] = "random"


class DeviceReadingCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    test_id: str = Field(min_length=1, max_length=120)
    timestamp: datetime
    sample_number: int = Field(ge=1, le=1000)
    raw_signal: float = Field(ge=0, le=1)
    filtered_signal: float = Field(ge=0, le=1)
    signal_quality: Literal["VALID", "INVALID", "COLLECTING SAMPLES"]
    simulation_mode: bool = True
    scenario: str | None = Field(default=None, max_length=80)


def assessment_public(row):
    if not row:
        return None
    data = dict(row)
    data["prefer_not_to_answer"] = bool(data["prefer_not_to_answer"])
    return data


@app.get("/")
def home():
    return {"message": "BioSense Patient Portal API", "mode": "SIMULATED"}


@app.get("/health")
def health():
    return {"status": "online"}


@app.get("/dataset/info")
def dataset_info():
    if DATASET_ERROR:
        return {
            "total_records": 0,
            "columns": list(FIELDNAMES),
            "simulation_mode": "SIMULATED",
            "available": False,
            "error": DATASET_ERROR,
            "disclaimer": SIMULATION_DISCLAIMER,
        }
    return {
        "total_records": len(DATASET_ROWS),
        "columns": list(FIELDNAMES),
        "simulation_mode": "SIMULATED",
        "available": bool(DATASET_ROWS),
        "disclaimer": SIMULATION_DISCLAIMER,
    }


@app.post("/auth/register", status_code=201)
def register(payload: RegisterRequest, response: Response, db=Depends(get_db)):
    if db.execute("SELECT 1 FROM patients WHERE email=?", (payload.email,)).fetchone():
        raise HTTPException(409, "An account with this email already exists.")
    now = datetime.now(timezone.utc).isoformat()
    patient_id = f"BS-{secrets.token_hex(4).upper()}"
    cursor = db.execute(
        "INSERT INTO patients(patient_id,full_name,email,password_hash,created_at,consent_at,date_of_birth,sex,phone) VALUES (?,?,?,?,?,?,?,?,?)",
        (patient_id, payload.full_name.strip(), payload.email, hash_password(payload.password), now, now,
         payload.date_of_birth.isoformat() if payload.date_of_birth else None, payload.sex, payload.phone),
    )
    new_session(db, cursor.lastrowid, response)
    db.commit()
    return {"message": "Account created", "patient": public_patient(db.execute("SELECT * FROM patients WHERE id=?", (cursor.lastrowid,)).fetchone())}


@app.post("/auth/login")
def login(payload: dict, response: Response, db=Depends(get_db)):
    full_name = str(payload.get("full_name", "")).strip()
    email = str(payload.get("email", "")).lower().strip()
    password = str(payload.get("password", ""))
    if full_name:
        row = db.execute(
            "SELECT * FROM patients WHERE lower(full_name)=lower(?)",
            (full_name,),
        ).fetchone()
    elif email:
        row = db.execute("SELECT * FROM patients WHERE email=?", (email,)).fetchone()
    else:
        row = None
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Invalid patient name or password.")
    new_session(db, row["id"], response)
    db.commit()
    return {"message": "Logged in", "patient": public_patient(row)}


@app.post("/auth/logout")
def logout(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    response: Response = None,
    db=Depends(get_db),
):
    if session:
        token_hash = hashlib.sha256(session.encode()).hexdigest()
        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
        db.commit()
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    return {"message": "Logged out"}


@app.get("/auth/me")
def me(patient=Depends(current_patient)):
    return {"patient": public_patient(patient)}


@app.get("/patients/me")
def profile(patient=Depends(current_patient)):
    return {"patient": public_patient(patient)}


@app.patch("/patients/me")
def update_profile(payload: ProfileUpdate, patient=Depends(current_patient), db=Depends(get_db)):
    db.execute("UPDATE patients SET full_name=?,date_of_birth=?,sex=?,phone=? WHERE id=?",
               (payload.full_name, payload.date_of_birth.isoformat() if payload.date_of_birth else None, payload.sex, payload.phone, patient["id"]))
    db.commit()
    return profile(db.execute("SELECT * FROM patients WHERE id=?", (patient["id"],)).fetchone())


@app.get("/patients/me/assessment")
def read_assessment(patient=Depends(current_patient), db=Depends(get_db)):
    row = db.execute("SELECT * FROM patient_assessments WHERE patient_id=?", (patient["id"],)).fetchone()
    return {"assessment": assessment_public(row)}


@app.put("/patients/me/assessment")
def save_assessment(payload: AssessmentUpdate, patient=Depends(current_patient), db=Depends(get_db)):
    data = payload.model_dump()
    bmi = round(data["weight_kg"] / ((data["height_cm"] / 100) ** 2), 2) if data["weight_kg"] and data["height_cm"] else None
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO patient_assessments(patient_id,weight_kg,height_cm,bmi,breast_cancer_family_history,
        affected_relative,relative_diagnosis_age,ovarian_cancer_family_history,currently_pregnant,
        currently_breastfeeding,prior_breast_diagnosis,
        prior_breast_investigation,additional_history,prefer_not_to_answer,completed_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(patient_id) DO UPDATE SET weight_kg=excluded.weight_kg,height_cm=excluded.height_cm,
        bmi=excluded.bmi,breast_cancer_family_history=excluded.breast_cancer_family_history,
        affected_relative=excluded.affected_relative,relative_diagnosis_age=excluded.relative_diagnosis_age,
        ovarian_cancer_family_history=excluded.ovarian_cancer_family_history,
        currently_pregnant=excluded.currently_pregnant,
        currently_breastfeeding=excluded.currently_breastfeeding,
        prior_breast_diagnosis=excluded.prior_breast_diagnosis,prior_breast_investigation=excluded.prior_breast_investigation,
        additional_history=excluded.additional_history,prefer_not_to_answer=excluded.prefer_not_to_answer,
        updated_at=excluded.updated_at""",
        (patient["id"], data["weight_kg"], data["height_cm"], bmi, data["breast_cancer_family_history"],
         data["affected_relative"], data["relative_diagnosis_age"], data["ovarian_cancer_family_history"],
         data["currently_pregnant"], data["currently_breastfeeding"],
         data["prior_breast_diagnosis"], data["prior_breast_investigation"], data["additional_history"],
         int(data["prefer_not_to_answer"]), now, now),
    )
    db.commit()
    return {"assessment": assessment_public(db.execute("SELECT * FROM patient_assessments WHERE patient_id=?", (patient["id"],)).fetchone())}


@app.get("/patients/me/readings")
@app.get("/readings")
def readings(patient=Depends(current_patient), db=Depends(get_db)):
    rows = db.execute(
        """SELECT r.*,t.hypothetical_pcna_ng_ml,t.simulated_current_uA,t.filtered_current_uA,
        t.simulated_voltage_V,t.raw_adc_counts,t.filtered_adc_counts,t.sample_count,
        t.quality_explanation,t.test_status
        FROM readings r LEFT JOIN biosense_tests t ON t.test_id=r.test_id
        WHERE r.patient_id=? ORDER BY r.record_id DESC""",
        (patient["id"],),
    ).fetchall()
    return {"total": len(rows), "readings": [dict(row) for row in rows]}


@app.get("/patients/me/readings/{reading_id}")
def reading_detail(reading_id: int, patient=Depends(current_patient), db=Depends(get_db)):
    row = db.execute("SELECT * FROM readings WHERE record_id=? AND patient_id=?", (reading_id, patient["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Reading not found.")
    return {"reading": dict(row)}


@app.post("/readings", status_code=201)
def ingest_device_reading(
    payload: DeviceReadingCreate,
    patient=Depends(current_patient),
    db=Depends(get_db),
):
    timestamp = payload.timestamp.astimezone(timezone.utc).isoformat()
    existing = db.execute(
        "SELECT patient_id,device_id FROM readings WHERE test_id=?",
        (payload.test_id,),
    ).fetchone()
    if db.execute(
        "SELECT 1 FROM biosense_tests WHERE test_id=?",
        (payload.test_id,),
    ).fetchone():
        raise HTTPException(409, "Test ID is already associated with a BioSense PCNA simulation.")
    if existing and existing["patient_id"] != patient["id"]:
        raise HTTPException(404, "Test not found.")
    if existing and existing["device_id"] != payload.device_id:
        raise HTTPException(409, "Test ID is already associated with a different device.")
    try:
        if not existing:
            db.execute(
                """INSERT INTO readings(
                    patient_id,device_id,test_id,timestamp,sample_number,raw_signal,
                    filtered_signal,signal_quality,simulation_mode,scenario
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    patient["id"], payload.device_id, payload.test_id, timestamp,
                    payload.sample_number, payload.raw_signal, payload.filtered_signal,
                    payload.signal_quality, int(payload.simulation_mode), payload.scenario,
                ),
            )
        db.execute(
            """INSERT INTO device_samples(
                test_id,patient_id,device_id,timestamp,sample_number,raw_signal,
                filtered_signal,signal_quality,simulation_mode,scenario
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                payload.test_id, patient["id"], payload.device_id, timestamp,
                payload.sample_number, payload.raw_signal, payload.filtered_signal,
                payload.signal_quality, int(payload.simulation_mode), payload.scenario,
            ),
        )
        db.execute(
            """UPDATE readings SET timestamp=?,sample_number=?,raw_signal=?,
            filtered_signal=?,signal_quality=?,simulation_mode=?,scenario=?
            WHERE test_id=? AND patient_id=?""",
            (
                timestamp, payload.sample_number, payload.raw_signal,
                payload.filtered_signal, payload.signal_quality,
                int(payload.simulation_mode), payload.scenario,
                payload.test_id, patient["id"],
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This sample number has already been saved for the test.") from error
    row = db.execute(
        "SELECT * FROM readings WHERE test_id=? AND patient_id=?",
        (payload.test_id, patient["id"]),
    ).fetchone()
    return {"message": "Device sample saved.", "record_id": row["record_id"], "test_id": payload.test_id}


@app.post("/simulate")
def simulate(
    payload: SimulationRequest | None = None,
    patient=Depends(current_patient),
    db=Depends(get_db),
):
    if DATASET_ERROR:
        raise HTTPException(503, f"Synthetic dataset is unavailable: {DATASET_ERROR}")
    if not DATASET_ROWS:
        raise HTTPException(503, "Synthetic dataset is unavailable.")

    scenario = payload.scenario if payload else "random"
    candidates = DATASET_ROWS
    if scenario != "random":
        candidates = [row for row in DATASET_ROWS if row["signal_quality"] == scenario.upper()]
    if not candidates:
        raise HTTPException(503, f"No {scenario} synthetic samples are available.")

    rng = random.Random(secrets.randbits(64))
    sample = rng.choice(candidates)
    sample_count = SAMPLE_COUNT
    timestamp = datetime.now(timezone.utc).isoformat()
    test_id = f"BS-TEST-{secrets.token_hex(8).upper()}"
    concentration = float(sample["hypothetical_pcna_ng_ml"])
    baseline_current = float(sample["simulated_current_uA"])
    raw_currents: list[float] = []
    filtered_currents: list[float] = []
    raw_voltages: list[float] = []
    raw_counts: list[int] = []
    filtered_counts: list[int] = []
    readings_to_save = []

    for sample_number in range(1, sample_count + 1):
        current_ua = max(0.0, rng.gauss(baseline_current, max(0.002, baseline_current * 0.035)))
        voltage_v = current_ua * TIA_RESISTANCE_OHM / 1_000_000
        adc_count = round(voltage_v / ADC_REFERENCE_V * ADC_MAX)
        raw_currents.append(current_ua)
        filtered_current = sum(raw_currents[-FILTER_WINDOW:]) / min(len(raw_currents), FILTER_WINDOW)
        filtered_currents.append(filtered_current)
        raw_voltages.append(voltage_v)
        raw_counts.append(adc_count)
        filtered_adc = round(sum(raw_counts[-FILTER_WINDOW:]) / min(len(raw_counts), FILTER_WINDOW))
        filtered_counts.append(filtered_adc)
        readings_to_save.append(
            {
                "sample_number": sample_number,
                "simulated_current_uA": round(current_ua, 6),
                "filtered_current_uA": round(filtered_current, 6),
                "simulated_voltage_V": round(voltage_v, 6),
                "raw_adc_counts": adc_count,
                "filtered_adc_counts": filtered_adc,
            }
        )

    issues = []
    if len(readings_to_save) != SAMPLE_COUNT:
        issues.append(f"Expected {SAMPLE_COUNT} samples but collected {len(readings_to_save)}.")
    if sample["signal_quality"] != "VALID":
        issues.append("The selected dataset record is designated invalid for technical quality-check testing.")
    for reading in readings_to_save:
        if not all(
            math.isfinite(reading[field])
            for field in ("simulated_current_uA", "simulated_voltage_V")
        ):
            issues.append("A sample contains a missing or non-finite current or voltage.")
            break
        if not 0 <= reading["simulated_current_uA"] <= ADC_REFERENCE_V * 1_000_000 / TIA_RESISTANCE_OHM:
            issues.append("A simulated current is outside the configured voltage-converter range.")
            break
        if not 0 <= reading["simulated_voltage_V"] <= ADC_REFERENCE_V:
            issues.append("A simulated voltage is outside the ADC reference range.")
            break
        if not 0 <= reading["raw_adc_counts"] <= ADC_MAX or not 0 <= reading["filtered_adc_counts"] <= ADC_MAX:
            issues.append("An ADC reading is outside the configured 12-bit range.")
            break

    quality = "INVALID" if issues else "VALID"
    explanation = " ".join(issues) if issues else "All generated samples passed technical range and completeness checks."
    for reading in readings_to_save:
        reading["signal_quality"] = quality
        reading["quality_explanation"] = explanation
    average_current = round(sum(raw_currents) / len(raw_currents), 6)
    average_filtered_current = round(sum(filtered_currents) / len(filtered_currents), 6)
    average_voltage = round(sum(raw_voltages) / len(raw_voltages), 6)
    average_raw_adc = round(sum(raw_counts) / len(raw_counts))
    average_filtered_adc = round(sum(filtered_counts) / len(filtered_counts))
    technical_result = "TECHNICALLY VALID SYNTHETIC SIGNAL" if quality == "VALID" else "INVALID SYNTHETIC SIGNAL"

    try:
        db.execute(
            """INSERT INTO biosense_tests(
                test_id,patient_id,device_id,timestamp,test_status,simulation_mode,sample_id,
                hypothetical_pcna_ng_ml,simulated_current_uA,filtered_current_uA,
                simulated_voltage_V,raw_adc_counts,
                filtered_adc_counts,signal_quality,sample_count,quality_explanation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                test_id, patient["id"], DEVICE_ID, timestamp, "COMPLETED", 1,
                sample["sample_id"], concentration, average_current, average_filtered_current, average_voltage,
                average_raw_adc, average_filtered_adc, quality, len(readings_to_save), explanation,
            ),
        )
        db.executemany(
            """INSERT INTO sensor_readings(
                test_id,sample_number,simulated_current_uA,simulated_voltage_V,raw_adc_counts,
                filtered_current_uA,filtered_adc_counts,signal_quality,quality_explanation,timestamp
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    test_id, reading["sample_number"], reading["simulated_current_uA"],
                    reading["simulated_voltage_V"], reading["raw_adc_counts"],
                    reading["filtered_current_uA"],
                    reading["filtered_adc_counts"], quality, explanation, timestamp,
                )
                for reading in readings_to_save
            ],
        )
        db.execute(
            """INSERT INTO readings(
                patient_id,device_id,test_id,timestamp,sample_number,raw_signal,filtered_signal,
                signal_quality,simulation_mode,scenario
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                patient["id"], DEVICE_ID, test_id, timestamp, sample_count,
                average_current, average_current, quality, 1, "synthetic_pcna",
            ),
        )
        db.execute(
            """INSERT INTO test_reports(
                test_id,patient_id,report_timestamp,technical_result,simulation_disclaimer
            ) VALUES (?,?,?,?,?)""",
            (test_id, patient["id"], timestamp, technical_result, SIMULATION_DISCLAIMER),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        logger.exception("Could not save synthetic test %s", test_id)
        raise HTTPException(500, "Could not save the synthetic test. Please try again.") from error

    result = {
        "test_id": test_id,
        "patient_id": patient["patient_id"],
        "device_id": DEVICE_ID,
        "timestamp": timestamp,
        "test_status": "COMPLETED",
        "simulation_mode": "SIMULATED",
        "sample_id": sample["sample_id"],
        "hypothetical_pcna_ng_ml": concentration,
        "simulated_current_uA": average_current,
        "filtered_current_uA": average_filtered_current,
        "simulated_voltage_V": average_voltage,
        "raw_adc_counts": average_raw_adc,
        "filtered_adc_counts": average_filtered_adc,
        "signal_quality": quality,
        "quality_explanation": explanation,
        "sample_count": len(readings_to_save),
        "samples": readings_to_save,
        "disclaimer": SIMULATION_DISCLAIMER,
    }
    legacy = db.execute("SELECT * FROM readings WHERE test_id=?", (test_id,)).fetchone()
    return {"message": "Synthetic test completed and saved.", "test": result, "reading": dict(legacy)}


def owned_test(db, test_id: str, patient):
    test = db.execute(
        "SELECT * FROM biosense_tests WHERE test_id=? AND patient_id=?",
        (test_id, patient["id"]),
    ).fetchone()
    if not test:
        raise HTTPException(404, "Test not found.")
    return test


def test_public(test, patient):
    return {
        **dict(test),
        "patient_id": patient["patient_id"],
        "simulation_mode": "SIMULATED",
        "disclaimer": SIMULATION_DISCLAIMER,
    }


@app.get("/patients/{patient_id}/tests")
def patient_tests(patient_id: str, patient=Depends(current_patient), db=Depends(get_db)):
    if patient["role"] != "patient" or patient_id != patient["patient_id"]:
        raise HTTPException(404, "Patient not found.")
    rows = db.execute(
        "SELECT * FROM biosense_tests WHERE patient_id=? ORDER BY timestamp DESC",
        (patient["id"],),
    ).fetchall()
    return {"total": len(rows), "tests": [test_public(row, patient) for row in rows]}


@app.get("/tests/{test_id}")
def test_detail(test_id: str, patient=Depends(current_patient), db=Depends(get_db)):
    test = db.execute(
        "SELECT * FROM biosense_tests WHERE test_id=? AND patient_id=?",
        (test_id, patient["id"]),
    ).fetchone()
    if test:
        return {"test": test_public(test, patient)}
    reading = db.execute(
        "SELECT * FROM readings WHERE test_id=? AND patient_id=?",
        (test_id, patient["id"]),
    ).fetchone()
    if not reading:
        raise HTTPException(404, "Test not found.")
    legacy_test = dict(reading)
    legacy_test.update(
        {
            "test_type": "device_signal",
            "patient_id": patient["patient_id"],
            "test_status": "LEGACY SIMULATED",
            "simulation_mode": "SIMULATED",
            "sample_count": reading["sample_number"],
            "quality_explanation": (
                "Legacy device values are unitless synthetic signals, not measured "
                "current, PCNA concentration, or a clinical result."
            ),
            "disclaimer": SIMULATION_DISCLAIMER,
        }
    )
    return {"test": legacy_test}


@app.get("/tests/{test_id}/readings")
def test_readings(test_id: str, patient=Depends(current_patient), db=Depends(get_db)):
    test = db.execute(
        "SELECT 1 FROM biosense_tests WHERE test_id=? AND patient_id=?",
        (test_id, patient["id"]),
    ).fetchone()
    if test:
        rows = db.execute(
            "SELECT * FROM sensor_readings WHERE test_id=? ORDER BY sample_number",
            (test_id,),
        ).fetchall()
    else:
        reading = db.execute(
            "SELECT 1 FROM readings WHERE test_id=? AND patient_id=?",
            (test_id, patient["id"]),
        ).fetchone()
        if not reading:
            raise HTTPException(404, "Test not found.")
        rows = db.execute(
            "SELECT * FROM device_samples WHERE test_id=? AND patient_id=? ORDER BY sample_number",
            (test_id, patient["id"]),
        ).fetchall()
    return {"total": len(rows), "readings": [dict(row) for row in rows]}


@app.get("/tests/{test_id}/report")
def download_test_report(test_id: str, patient=Depends(current_patient), db=Depends(get_db)):
    test = owned_test(db, test_id, patient)
    report = db.execute(
        "SELECT * FROM test_reports WHERE test_id=? AND patient_id=?",
        (test_id, patient["id"]),
    ).fetchone()
    if not report:
        raise HTTPException(404, "Test report not found.")
    samples = db.execute(
        "SELECT * FROM sensor_readings WHERE test_id=? ORDER BY sample_number",
        (test_id,),
    ).fetchall()

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as error:
        raise HTTPException(503, "PDF report generation is unavailable on this server.") from error

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    page_width, page_height = letter
    pdf.setTitle(f"BioSense virtual test report {test_id}")
    pdf.setFillColorRGB(0.29, 0.24, 0.61)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, page_height - 54, "BioSense Virtual Test Report")
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, page_height - 82, "SOFTWARE SIMULATION - NOT A CLINICAL MEASUREMENT")

    details = [
        ("Patient ID", patient["patient_id"]),
        ("Test ID", test["test_id"]),
        ("Test date/time (UTC)", test["timestamp"]),
        ("Device ID", test["device_id"]),
        ("Status", test["test_status"]),
        ("Mode", "SIMULATED"),
        ("Hypothetical PCNA input", f"{test['hypothetical_pcna_ng_ml']:.4f} ng/mL (synthetic input only)"),
        ("Average raw simulated current", f"{test['simulated_current_uA']:.6f} uA"),
        ("Average filtered current", f"{test['filtered_current_uA']:.6f} uA"),
        ("Average simulated voltage", f"{test['simulated_voltage_V']:.6f} V"),
        ("Average raw ADC count", str(test["raw_adc_counts"])),
        ("Average filtered ADC count", str(test["filtered_adc_counts"])),
        ("Technical signal quality", test["signal_quality"]),
        ("Samples collected", str(test["sample_count"])),
        ("Technical quality check", test["quality_explanation"]),
    ]
    y = page_height - 110
    for label, value in details:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(48, y, f"{label}:")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(190, y, str(value)[:92])
        y -= 17

    chart_left, chart_bottom, chart_width, chart_height = 58, 112, page_width - 116, 150
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(chart_left, chart_bottom + chart_height + 20, "Raw versus filtered ADC samples")
    pdf.setStrokeColor(colors.lightgrey)
    pdf.rect(chart_left, chart_bottom, chart_width, chart_height)
    if samples:
        maximum = max(1, max(max(row["raw_adc_counts"], row["filtered_adc_counts"]) for row in samples))
        for key, color in (("raw_adc_counts", colors.HexColor("#9a8bd8")), ("filtered_adc_counts", colors.HexColor("#4a3e9b"))):
            pdf.setStrokeColor(color)
            pdf.setLineWidth(1.7)
            points = []
            for index, row in enumerate(samples):
                x = chart_left + index * chart_width / max(1, len(samples) - 1)
                point_y = chart_bottom + 8 + row[key] / maximum * (chart_height - 16)
                points.append((x, point_y))
            for first, second in zip(points, points[1:]):
                pdf.line(first[0], first[1], second[0], second[1])
        pdf.setFillColor(colors.HexColor("#9a8bd8"))
        pdf.drawString(chart_left + 4, chart_bottom - 15, "Raw ADC")
        pdf.setFillColor(colors.HexColor("#4a3e9b"))
        pdf.drawString(chart_left + 82, chart_bottom - 15, "Filtered ADC")

    pdf.setFillColor(colors.HexColor("#5f596d"))
    pdf.setFont("Helvetica", 8)
    disclaimer = SIMULATION_DISCLAIMER
    pdf.drawString(48, 48, disclaimer[:130])
    pdf.drawString(48, 37, disclaimer[130:260])
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="biosense-{test_id}.pdf"'},
    )


@app.get("/clinician/patients")
def clinician_patients(clinician=Depends(current_clinician), db=Depends(get_db)):
    rows = db.execute(
        """SELECT p.patient_id, p.full_name, p.created_at,
        COUNT(r.record_id) AS test_count, MAX(r.timestamp) AS latest_test
        FROM patients p LEFT JOIN readings r ON r.patient_id=p.id
        WHERE p.role='patient' GROUP BY p.id ORDER BY p.created_at DESC"""
    ).fetchall()
    return {"patients": [dict(row) for row in rows]}


@app.get("/clinician/patients/{patient_id}/review")
def clinician_review(patient_id: str, clinician=Depends(current_clinician), db=Depends(get_db)):
    patient = db.execute("SELECT * FROM patients WHERE patient_id=? AND role='patient'", (patient_id,)).fetchone()
    if not patient:
        raise HTTPException(404, "Patient not found.")
    assessment_row = db.execute("SELECT * FROM patient_assessments WHERE patient_id=?", (patient["id"],)).fetchone()
    readings_rows = db.execute("SELECT * FROM readings WHERE patient_id=? ORDER BY record_id DESC", (patient["id"],)).fetchall()
    notes = db.execute(
        "SELECT note, created_at FROM clinician_notes WHERE patient_id=? ORDER BY id DESC",
        (patient["id"],),
    ).fetchall()
    return {
        "patient": public_patient(patient),
        "assessment": assessment_public(assessment_row),
        "readings": [dict(row) for row in readings_rows],
        "notes": [dict(row) for row in notes],
        "interpretation_scope": "Synthetic signal review only. Not a diagnosis or clinical result.",
    }


@app.post("/clinician/patients/{patient_id}/notes")
def save_clinician_note(
    patient_id: str,
    payload: dict,
    clinician=Depends(current_clinician),
    db=Depends(get_db),
):
    patient = db.execute("SELECT id FROM patients WHERE patient_id=? AND role='patient'", (patient_id,)).fetchone()
    note = str(payload.get("note", "")).strip()
    if not patient:
        raise HTTPException(404, "Patient not found.")
    if not note or len(note) > 2000:
        raise HTTPException(422, "Enter a review note of up to 2,000 characters.")
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO clinician_notes(patient_id, clinician_id, note, created_at) VALUES (?,?,?,?)",
        (patient["id"], clinician["id"], note, now),
    )
    db.commit()
    return {"message": "Research review note saved.", "created_at": now}


def random_signal():
    import random
    return random.uniform(0.35, 0.75)
