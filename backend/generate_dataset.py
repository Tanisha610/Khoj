"""Generate a reproducible, entirely synthetic BioSense demonstration dataset.

For hypothetical concentration C, the illustrative model is
I_uA = max(0, 0.05 + 0.012*C + Gaussian noise), V = I_uA*100000/1e6,
and ADC = round(V/3.3*4095). Filtered counts use a three-sample moving average.
The concentration range, coefficients, noise, circuit, and ADC reference are
software assumptions, not validated calibration values or patient measurements.
"""

import csv
import random
from pathlib import Path

DATASET_PATH = Path(__file__).with_name("synthetic_pcna_dataset.csv")
RECORD_COUNT = 600
RANDOM_SEED = 20261031
ADC_MAX = 4095
ADC_REFERENCE_V = 3.3
SIMULATED_TIA_RESISTANCE_OHM = 100_000
BASELINE_CURRENT_UA = 0.05
CURRENT_SENSITIVITY_UA_PER_NG_ML = 0.012
CURRENT_NOISE_STDDEV_UA = 0.006

FIELDNAMES = (
    "sample_id",
    "hypothetical_pcna_ng_ml",
    "simulated_current_uA",
    "simulated_voltage_V",
    "raw_adc_counts",
    "filtered_adc_counts",
    "signal_quality",
)


def generate_dataset(path: Path = DATASET_PATH, record_count: int = RECORD_COUNT) -> Path:
    if record_count < 500:
        raise ValueError("The synthetic dataset must contain at least 500 records.")

    rng = random.Random(RANDOM_SEED)
    rows = []
    current_window: list[float] = []
    for index in range(1, record_count + 1):
        concentration = rng.uniform(0, 100)
        current_ua = max(
            0.0,
            BASELINE_CURRENT_UA
            + CURRENT_SENSITIVITY_UA_PER_NG_ML * concentration
            + rng.gauss(0, CURRENT_NOISE_STDDEV_UA),
        )
        voltage_v = current_ua * SIMULATED_TIA_RESISTANCE_OHM / 1_000_000
        adc_count = max(0, min(ADC_MAX, round(voltage_v / ADC_REFERENCE_V * ADC_MAX)))
        current_window.append(float(adc_count))
        current_window = current_window[-3:]
        filtered_adc = round(sum(current_window) / len(current_window))
        quality = "INVALID" if index % 20 == 0 else "VALID"
        rows.append(
            {
                "sample_id": f"SYN-{index:04d}",
                "hypothetical_pcna_ng_ml": round(concentration, 4),
                "simulated_current_uA": round(current_ua, 6),
                "simulated_voltage_V": round(voltage_v, 6),
                "raw_adc_counts": adc_count,
                "filtered_adc_counts": filtered_adc,
                "signal_quality": quality,
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as dataset_file:
        writer = csv.DictWriter(dataset_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def ensure_dataset(path: Path = DATASET_PATH) -> Path:
    if not path.exists():
        return generate_dataset(path)
    return path


if __name__ == "__main__":
    print(f"Generated {RECORD_COUNT} synthetic records: {generate_dataset()}")
