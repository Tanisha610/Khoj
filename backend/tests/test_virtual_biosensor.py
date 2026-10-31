import asyncio
import base64
import csv
import re
import sqlite3
import zlib
from contextlib import closing
from http.cookies import SimpleCookie
from datetime import datetime, timezone
from pathlib import Path

import main
from fastapi import Response
from generate_dataset import FIELDNAMES, generate_dataset


def create_patient(db: sqlite3.Connection, email: str) -> sqlite3.Row:
    db.execute(
        """INSERT INTO patients(
            patient_id,full_name,email,password_hash,created_at,consent_at,role
        ) VALUES (?,?,?,?,?,?,?)""",
        (f"BS-{email.split('@')[0]}", "Test Patient", email, "not-a-real-password", "now", "now", "patient"),
    )
    return db.execute("SELECT * FROM patients WHERE email=?", (email,)).fetchone()


def test_dataset_is_reproducible_complete_and_in_range(tmp_path: Path):
    dataset_path = tmp_path / "synthetic_pcna_dataset.csv"
    generate_dataset(dataset_path)
    first_bytes = dataset_path.read_bytes()
    generate_dataset(dataset_path)
    assert dataset_path.read_bytes() == first_bytes

    with dataset_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        assert tuple(reader.fieldnames) == FIELDNAMES
        rows = list(reader)
    assert len(rows) >= 500
    assert {row["signal_quality"] for row in rows} == {"VALID", "INVALID"}
    for row in rows:
        assert 0 <= float(row["simulated_current_uA"])
        assert 0 <= float(row["simulated_voltage_V"]) <= main.ADC_REFERENCE_V
        assert 0 <= int(row["raw_adc_counts"]) <= main.ADC_MAX
        assert 0 <= int(row["filtered_adc_counts"]) <= main.ADC_MAX


def test_invalid_dataset_is_reported_without_crashing_backend(tmp_path: Path, monkeypatch):
    dataset_path = tmp_path / "invalid.csv"
    dataset_path.write_text("sample_id,wrong_column\nSYN-1,123\n", encoding="utf-8")
    monkeypatch.setattr(main, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(main, "DATASET_ERROR", None)
    monkeypatch.setattr(main, "DATASET_ROWS", [])
    main.load_synthetic_dataset()
    assert main.DATASET_ROWS == []
    assert "missing required columns" in main.DATASET_ERROR


def test_simulation_saves_twenty_samples_and_patient_scoped_report(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "biosense-test.db")
    main.init_db()
    with closing(main.connection()) as db:
        first_patient = create_patient(db, "first@example.test")
        other_patient = create_patient(db, "other@example.test")
        db.commit()

        result = main.simulate(main.SimulationRequest(scenario="valid"), first_patient, db)
        test = result["test"]
        assert test["signal_quality"] == "VALID"
        assert test["sample_count"] == 20
        assert len(test["samples"]) == 20
        assert all(sample["signal_quality"] == "VALID" for sample in test["samples"])
        assert all(sample["quality_explanation"] for sample in test["samples"])
        assert test["simulated_current_uA"] >= 0
        assert test["filtered_current_uA"] >= 0
        assert 0 <= test["simulated_voltage_V"] <= main.ADC_REFERENCE_V
        assert 0 <= test["raw_adc_counts"] <= main.ADC_MAX
        assert 0 <= test["filtered_adc_counts"] <= main.ADC_MAX
        assert test["hypothetical_pcna_ng_ml"] is not None
        assert "not actual patient measurements" in test["disclaimer"]

        saved = db.execute(
            "SELECT COUNT(*) FROM sensor_readings WHERE test_id=?",
            (test["test_id"],),
        ).fetchone()[0]
        assert saved == 20
        assert len({reading["sample_number"] for reading in test["samples"]}) == 20
        assert all(
            0 <= reading["raw_adc_counts"] <= main.ADC_MAX
            and 0 <= reading["filtered_adc_counts"] <= main.ADC_MAX
            and reading["filtered_current_uA"] >= 0
            for reading in test["samples"]
        )
        for index, reading in enumerate(test["samples"]):
            expected_voltage = round(reading["simulated_current_uA"] * 0.1, 6)
            assert abs(reading["simulated_voltage_V"] - expected_voltage) <= 0.0000015
            expected_adc = round(reading["simulated_voltage_V"] / main.ADC_REFERENCE_V * main.ADC_MAX)
            assert abs(reading["raw_adc_counts"] - expected_adc) <= 1
            window = test["samples"][max(0, index - main.FILTER_WINDOW + 1):index + 1]
            expected_filtered = round(sum(sample["simulated_current_uA"] for sample in window) / len(window), 6)
            assert abs(reading["filtered_current_uA"] - expected_filtered) <= 0.0000015
        assert db.execute(
            "SELECT COUNT(*) FROM test_reports WHERE test_id=?",
            (test["test_id"],),
        ).fetchone()[0] == 1
        assert main.owned_test(db, test["test_id"], first_patient)["test_id"] == test["test_id"]

        try:
            main.owned_test(db, test["test_id"], other_patient)
        except main.HTTPException as error:
            assert error.status_code == 404
        else:
            raise AssertionError("A different patient must not access the test.")


def test_invalid_dataset_sample_is_reported_as_technical_invalid(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "biosense-invalid-test.db")
    main.init_db()
    with closing(main.connection()) as db:
        patient = create_patient(db, "invalid@example.test")
        db.commit()
        result = main.simulate(main.SimulationRequest(scenario="invalid"), patient, db)
        assert result["test"]["signal_quality"] == "INVALID"
        assert "designated invalid" in result["test"]["quality_explanation"]
        assert all(sample["signal_quality"] == "INVALID" for sample in result["test"]["samples"])


def test_report_endpoint_returns_pdf_for_owner(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "biosense-report-test.db")
    main.init_db()
    with closing(main.connection()) as db:
        patient = create_patient(db, "report@example.test")
        db.commit()
        result = main.simulate(main.SimulationRequest(scenario="valid"), patient, db)
        test_id = result["test"]["test_id"]
        response = main.download_test_report(test_id, patient, db)
        assert response.media_type == "application/pdf"
        assert response.headers["content-disposition"].endswith(".pdf\"")

        async def read_body():
            return b"".join([part async for part in response.body_iterator])

        body = asyncio.run(read_body())
        assert body.startswith(b"%PDF")
        assert test_id.encode() in body
        streams = re.findall(rb"stream\r?\n(.*?)\r?endstream", body, re.DOTALL)
        decoded_streams = []
        for stream in streams:
            try:
                decoded_streams.append(zlib.decompress(stream))
            except zlib.error:
                decoded_streams.append(zlib.decompress(base64.a85decode(stream.rstrip(b"~>"))))
        report_text = b"\n".join(decoded_streams)
        assert patient["patient_id"].encode() in report_text
        assert test_id.encode() in report_text
        assert result["test"]["timestamp"].encode() in report_text
        assert result["test"]["device_id"].encode() in report_text
        assert b"SIMULATION" in report_text
        assert b"Samples collected:" in report_text
        assert b"(20) Tj" in report_text
        assert b"Hypothetical PCNA input:" in report_text
        assert f"{result['test']['hypothetical_pcna_ng_ml']:.4f}".encode() in report_text
        assert b"actual patient measurements" in report_text


def test_authenticated_device_simulator_persists_samples_and_enforces_ownership(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "device-samples.db")
    main.init_db()
    with closing(main.connection()) as db:
        patient = create_patient(db, "device-owner@example.test")
        other_patient = create_patient(db, "device-other@example.test")
        db.commit()
        test_id = "DEVICE-TEST-1"
        for sample_number in range(1, 21):
            payload = main.DeviceReadingCreate(
                device_id="VIRTUAL-READER-001",
                test_id=test_id,
                timestamp=datetime.now(timezone.utc),
                sample_number=sample_number,
                raw_signal=0.5,
                filtered_signal=0.5,
                signal_quality="VALID" if sample_number >= 5 else "COLLECTING SAMPLES",
                simulation_mode=True,
                scenario="baseline",
            )
            result = main.ingest_device_reading(payload, patient, db)
            assert result["test_id"] == test_id

        assert db.execute(
            "SELECT COUNT(*) FROM device_samples WHERE test_id=?",
            (test_id,),
        ).fetchone()[0] == 20
        summary = db.execute(
            "SELECT sample_number,patient_id FROM readings WHERE test_id=?",
            (test_id,),
        ).fetchone()
        assert summary["sample_number"] == 20
        assert summary["patient_id"] == patient["id"]
        details = main.test_detail(test_id, patient, db)["test"]
        assert details["test_type"] == "device_signal"
        assert details["sample_count"] == 20
        device_readings = main.test_readings(test_id, patient, db)["readings"]
        assert len(device_readings) == 20
        assert device_readings[0]["raw_signal"] == 0.5

        try:
            main.ingest_device_reading(payload, other_patient, db)
        except main.HTTPException as error:
            assert error.status_code == 404
        else:
            raise AssertionError("A different patient must not append to the device test.")

        try:
            main.ingest_device_reading(payload, patient, db)
        except main.HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError("A duplicate sample number must be rejected.")

        for endpoint in (main.test_detail, main.test_readings):
            try:
                endpoint(test_id, other_patient, db)
            except main.HTTPException as error:
                assert error.status_code == 404
            else:
                raise AssertionError("A different patient must not read the device test.")


def test_existing_clinician_review_and_notes_still_work(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "clinician-review.db")
    main.init_db()
    with closing(main.connection()) as db:
        patient = create_patient(db, "review-patient@example.test")
        create_patient(db, "review-clinician@example.test")
        db.execute(
            "UPDATE patients SET role='clinician' WHERE email=?",
            ("review-clinician@example.test",),
        )
        clinician = db.execute(
            "SELECT * FROM patients WHERE email=?",
            ("review-clinician@example.test",),
        ).fetchone()
        db.commit()
        result = main.simulate(main.SimulationRequest(scenario="valid"), patient, db)

        patients = main.clinician_patients(clinician, db)["patients"]
        listed = next(row for row in patients if row["patient_id"] == patient["patient_id"])
        assert listed["test_count"] == 1
        review = main.clinician_review(patient["patient_id"], clinician, db)
        assert review["readings"][0]["test_id"] == result["test"]["test_id"]

        saved = main.save_clinician_note(
            patient["patient_id"],
            {"note": "QA review of synthetic signal only."},
            clinician,
            db,
        )
        assert "created_at" in saved
        assert main.clinician_review(patient["patient_id"], clinician, db)["notes"][0]["note"] == (
            "QA review of synthetic signal only."
        )


def test_registration_and_session_still_work_with_existing_sqlite_schema(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "biosense-auth-test.db")
    main.init_db()
    with closing(main.connection()) as db:
        payload = main.RegisterRequest(
            full_name="Auth Test Patient",
            email="auth-test@example.test",
            password="SecurePass123!",
            confirm_password="SecurePass123!",
            consent=True,
        )
        response = Response()
        registered = main.register(payload, response, db)
        assert registered["patient"]["email"] == payload.email

        cookie = SimpleCookie(response.headers["set-cookie"])
        session = cookie["biosense_session"].value
        authenticated = main.current_patient(session, db)
        assert authenticated["patient_id"] == registered["patient"]["patient_id"]


def test_production_session_cookie_supports_cross_origin_frontend(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "biosense-cookie-test.db")
    monkeypatch.setattr(main, "SESSION_COOKIE_SAMESITE", "none")
    monkeypatch.setattr(main, "SESSION_COOKIE_SECURE", True)
    main.init_db()
    with closing(main.connection()) as db:
        patient = create_patient(db, "cookie-test@example.test")
        db.commit()
        response = Response()
        main.new_session(db, patient["id"], response)

        cookie = SimpleCookie(response.headers["set-cookie"])["biosense_session"]
        assert cookie["httponly"]
        assert cookie["secure"]
        assert cookie["samesite"] == "none"


def test_pregnancy_and_breastfeeding_assessment_answers_persist_and_migrate(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "existing-assessment.db"
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)
    with closing(sqlite3.connect(database_path)) as db:
        db.execute(
            """CREATE TABLE patient_assessments (
                patient_id INTEGER PRIMARY KEY,
                weight_kg REAL, height_cm REAL, bmi REAL,
                breast_cancer_family_history TEXT,
                affected_relative TEXT, relative_diagnosis_age INTEGER,
                ovarian_cancer_family_history TEXT,
                prior_breast_diagnosis TEXT,
                prior_breast_investigation TEXT,
                additional_history TEXT, prefer_not_to_answer INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT, updated_at TEXT NOT NULL
            )"""
        )

    main.init_db()
    with closing(main.connection()) as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(patient_assessments)")}
        assert {"currently_pregnant", "currently_breastfeeding"} <= columns

        patient = create_patient(db, "assessment-test@example.test")
        db.commit()
        answers = main.AssessmentUpdate(currently_pregnant="yes", currently_breastfeeding="no")
        saved = main.save_assessment(answers, patient, db)["assessment"]
        assert saved["currently_pregnant"] == "yes"
        assert saved["currently_breastfeeding"] == "no"

        updated = main.AssessmentUpdate(
            currently_pregnant="prefer_not_to_say",
            currently_breastfeeding="yes",
        )
        saved = main.save_assessment(updated, patient, db)["assessment"]
        assert saved["currently_pregnant"] == "prefer_not_to_say"
        assert saved["currently_breastfeeding"] == "yes"
