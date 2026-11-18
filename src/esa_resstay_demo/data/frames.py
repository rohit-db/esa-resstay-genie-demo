"""Load-metadata columns every staging frame carries; the SQL load turns them into history columns."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from esa_resstay_demo.data.config import OPEN_ENDED

META_COLUMNS = ("_record_source", "_load_ts", "_dq_status", "_version_start", "_version_end", "_is_current")


def with_meta(
    df: pd.DataFrame,
    record_source: str,
    load_ts,
    version_start,
    version_end: datetime = OPEN_ENDED,
    is_current=True,
    dq_status="PASS",
) -> pd.DataFrame:
    """Return a copy of `df` with the six load-metadata columns (scalars or per-row sequences)."""
    out = df.copy()
    out["_record_source"] = record_source
    out["_load_ts"] = microseconds(load_ts, len(out))
    out["_dq_status"] = dq_status
    out["_version_start"] = microseconds(version_start, len(out))
    out["_version_end"] = microseconds(version_end, len(out))
    out["_is_current"] = is_current
    return out


def microseconds(value, length: int) -> np.ndarray:
    """Timestamps at microsecond resolution, so the 9999-12-31 open end date fits."""
    if isinstance(value, (datetime, pd.Timestamp, np.datetime64)):
        return np.full(length, np.datetime64(value, "us"))
    return np.asarray(value).astype("datetime64[us]")


def business_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META_COLUMNS]
