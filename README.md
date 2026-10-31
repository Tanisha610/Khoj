# OncoCare virtual biosensor prototype

OncoCare is a software-only demonstration. The virtual PCNA inputs and all
resulting electrical values are synthetic assumptions, not actual patient
measurements, experimentally calibrated sensor values, a diagnosis, or a
clinical result. Signal quality describes technical data checks only.

## Synthetic signal model

`backend/generate_dataset.py` creates 600 reproducible rows using a fixed seed.
For hypothetical PCNA input `C` in ng/mL, the example model is:

```text
simulated current (uA) = max(0, 0.05 + 0.012 * C + Gaussian noise)
simulated voltage (V) = current (uA) * 100,000 ohms / 1,000,000
raw 12-bit ADC count = round(voltage / 3.3 V * 4095)
filtered current and ADC = three-sample moving averages of the raw values
```

The range, baseline, sensitivity, noise, transimpedance resistance, and ADC
reference are illustrative software assumptions. They are not experimental
calibration values. The test simulation selects one hypothetical dataset input
and generates 20 noisy readings from it. It does not use a patient's assessment
to fabricate sensor readings.

The backend generates `backend/synthetic_pcna_dataset.csv` automatically if
the file is absent. If the file exists but has invalid columns or values, the
API stays available and `/dataset/info` reports the dataset error.

## Run locally (Windows PowerShell)

Install backend dependencies once:

```powershell
cd C:\Users\Admin\OneDrive\Desktop\Khoj\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the backend:

```powershell
cd C:\Users\Admin\OneDrive\Desktop\Khoj\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the existing Vite frontend:

```powershell
cd C:\Users\Admin\OneDrive\Desktop\Khoj\frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the backend.
The landing page includes an interactive signal lab comparing deterministic
synthetic raw traces with a three-sample moving average; its values are
illustrative and unrelated to patient records or real PCNA measurements.

## Legacy device simulator

The existing software sensor simulator can post 20 synthetic, unitless device
samples to an authenticated patient account:

```powershell
cd C:\Users\Admin\OneDrive\Desktop\Khoj\backend
.\.venv\Scripts\python.exe .\simulator\sensor_simulator.py
```

It prompts for the OncoCare account email and password. Set
`$env:BIOSENSE_API_URL` before running it to use a backend at another URL. Its
readings appear in patient history as legacy simulated signals; they are not
PCNA/current measurements and do not have a PCNA PDF report. This workspace
does not include a Wokwi diagram or firmware, so a hardware Wokwi circuit
cannot be launched or verified here.

## Test workflow

1. Register a patient and complete or decline the optional assessment.
2. Sign in, open **Virtual test**, and advance through the conceptual stages.
3. The backend generates and stores one test with 20 readings for the signed-in patient.
4. Watch the live synthetic signal playback during processing. Open **Test history**,
   select the test, inspect the raw/filtered chart and sample table, then choose
   **Download PDF report**.
5. Re-run a test or inspect the API response. Tests are persisted in the existing
   `backend/biosense.db` SQLite database.

## API endpoints

- `GET /health` — backend status.
- `GET /dataset/info` — CSV availability, number of rows, columns, and mode.
- `POST /simulate` — authenticated; optional JSON body
  `{"scenario":"random"}`, `{"scenario":"valid"}`, or `{"scenario":"invalid"}`.
- `GET /readings` and `GET /patients/me/readings` — authenticated patient's history.
- `POST /readings` — authenticated ingestion for one legacy unitless device sample.
- `GET /patients/{patient_id}/tests` — authenticated patient's own tests only.
- `GET /tests/{test_id}` — authenticated test detail, owner only (including legacy device signals).
- `GET /tests/{test_id}/readings` — authenticated samples, owner only.
- `GET /tests/{test_id}/report` — authenticated downloadable PDF, owner only.

Run backend tests from the backend folder:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```
