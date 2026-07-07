"""metafor engine — the Cochrane-faithful reference implementation.

Rather than link R into the process with rpy2 (fragile across Python/R
architecture mismatches), we call metafor through an `Rscript` subprocess: write
the studies to a CSV, run `metafor_pool.R`, and parse the JSON it prints. Robust
and dependency-light (base-R JSON emit, no jsonlite).
"""

from __future__ import annotations

import csv
import functools
import json
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from ..schema import EffectPoint

_SCRIPT = Path(__file__).with_name("metafor_pool.R")


@functools.lru_cache(maxsize=1)
def available() -> bool:
    """True when Rscript is on PATH and the metafor package loads."""
    from shutil import which

    if which("Rscript") is None:
        return False
    try:
        subprocess.run(
            ["Rscript", "-e", "suppressMessages(library(metafor))"],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return True


def fit(points: Sequence[EffectPoint], method: str = "REML") -> dict:
    if method.upper() != "REML":
        raise ValueError("metafor bridge currently supports REML only")

    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", newline="", delete=False
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(["study_id", "label", "yi", "vi"])
        for p in points:
            writer.writerow([p.study_id, p.label, repr(p.yi), repr(p.vi)])
        csv_path = fh.name

    try:
        proc = subprocess.run(
            ["Rscript", str(_SCRIPT), csv_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        raise RuntimeError(f"metafor bridge failed: {exc.stderr}") from exc
    finally:
        Path(csv_path).unlink(missing_ok=True)

    raw = json.loads(proc.stdout)
    raw["per_study"] = [
        {
            "study_id": sid,
            "label": lbl,
            "yi": yi,
            "vi": vi,
            "weight": wt,
        }
        for sid, lbl, yi, vi, wt in zip(
            raw.pop("study_id"),
            raw.pop("label"),
            raw.pop("yi"),
            raw.pop("vi"),
            raw.pop("weight"),
        )
    ]
    return raw
