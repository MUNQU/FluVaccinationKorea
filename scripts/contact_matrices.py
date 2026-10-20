"""Korean 6x6 contact matrices from woosikson/age-rt-smoother -> long format.

Writes data/processed/contact_matrices.csv. Convention of the source:
C[i, j] with row i = contactee (susceptible) and column j = infector, so the
force of infection on group i is chi_i * sum_j C[i, j] * I_j / N_j.
"""

import pandas as pd
import requests

from common import PROCESSED, RAW

REPO = "woosikson/age-rt-smoother"
COMMIT = "403d8da6a458d66d74ac960df026170acd6a0c4d"
RAW_DIR = RAW / "github_age_rt_smoother"
FILES = [
    "contact_prem2017.csv",
    "contact_prem2021.csv",
    "Pops_Dec2022.csv",
    "README.md",
]
AGES = ["0-5", "6-11", "12-17", "18-44", "45-64", "65+"]

# Survey-based matrix (Son et al. 2025). The repository writes it in the
# source code, not in a data file: code/02_particle_smoother.jl and
# code/04_nhis.jl, `const C = [...]`.
SON2025 = [
    [1.76, 0.21, 0.03, 0.20, 0.05, 0.05],
    [0.33, 3.75, 0.30, 0.31, 0.14, 0.13],
    [0.05, 0.31, 3.65, 0.22, 0.31, 0.12],
    [2.07, 2.11, 1.38, 1.78, 1.26, 0.84],
    [0.47, 0.88, 1.87, 1.18, 1.97, 1.47],
    [0.30, 0.47, 0.42, 0.45, 0.83, 2.50],
]


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = RAW_DIR / name
        if path.exists():
            continue
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/data/{name}"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)


def to_long(matrix, name: str, source: str) -> pd.DataFrame:
    rows = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            rows.append(
                {
                    "source": source,
                    "matrix": name,
                    "contactee_age_group": AGES[i],
                    "infector_age_group": AGES[j],
                    "value": float(value),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    download()
    frames = [to_long(SON2025, "son2025_survey", f"github:{REPO}@{COMMIT[:7]}")]
    for name in ("prem2017", "prem2021"):
        matrix = pd.read_csv(RAW_DIR / f"contact_{name}.csv", header=None).values
        if matrix.shape != (6, 6):
            raise ValueError(f"{name}: shape {matrix.shape}")
        frames.append(to_long(matrix, name, f"github:{REPO}@{COMMIT[:7]}"))
    df = pd.concat(frames, ignore_index=True)
    path = PROCESSED / "contact_matrices.csv"
    df.to_csv(path, index=False)
    print(path, len(df))


if __name__ == "__main__":
    main()
