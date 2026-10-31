
import random
import os
import time
from getpass import getpass
import requests
from datetime import datetime, timezone
from uuid import uuid4

API_BASE_URL = os.environ.get("BIOSENSE_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_URL = f"{API_BASE_URL}/readings"
DEVICE_ID = "VIRTUAL-READER-001"


def generate_reading(scenario, history):
    settings = {
        "baseline": (0.50, 0.02),
        "elevated": (0.80, 0.02),
        "noisy": (0.60, 0.20),
    }

    mean, noise = settings[scenario]
    raw = max(0.0, min(1.0, random.gauss(mean, noise)))

    history.append(raw)
    history = history[-5:]

    filtered = sum(history) / len(history)

    quality = (
        "VALID" if len(history) == 5
        else "COLLECTING SAMPLES"
    )

    return raw, filtered, quality, history


def run_simulator(scenario="baseline", count=20, email=None, password=None):
    history = []
    email = email or input("BioSense account email: ").strip()
    password = password or getpass("BioSense account password: ")
    session = requests.Session()

    print("VIRTUAL BIOSENSOR SIMULATOR")
    print("Mode: SIMULATED — NOT A MEDICAL TEST")
    print("Sending readings to:", API_URL)
    print("-" * 50)

    try:
        login = session.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=5,
        )
        login.raise_for_status()
    except requests.RequestException as error:
        print("Could not log in to BioSense:", error)
        session.close()
        return

    test_id = f"DEVICE-{uuid4().hex.upper()}"
    for i in range(1, count + 1):
        raw, filtered, quality, history = generate_reading(
            scenario, history
        )

        payload = {
            "device_id": DEVICE_ID,
            "test_id": test_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sample_number": i,
            "raw_signal": round(raw, 4),
            "filtered_signal": round(filtered, 4),
            "signal_quality": quality,
            "simulation_mode": True,
            "scenario": scenario,
        }

        try:
            response = session.post(
                API_URL, json=payload, timeout=5
            )
            response.raise_for_status()

            result = response.json()

            print(
                f"Sample {i:02d} | "
                f"Raw: {raw:.4f} | "
                f"Filtered: {filtered:.4f} | "
                f"Saved record: {result['record_id']}"
            )

        except requests.RequestException as error:
            print("Could not send reading:", error)
            break

        time.sleep(1)

    session.close()
    print("\nSimulation finished.")


if __name__ == "__main__":
    print("\nSelect scenario:")
    print("1. Baseline synthetic signal")
    print("2. Elevated synthetic signal")
    print("3. Noisy synthetic signal")

    choice = input("Enter 1, 2 or 3: ").strip()

    scenarios = {
        "1": "baseline",
        "2": "elevated",
        "3": "noisy"
    }

    if choice in scenarios:
        run_simulator(scenarios[choice])
    else:
        print("Invalid choice.")
