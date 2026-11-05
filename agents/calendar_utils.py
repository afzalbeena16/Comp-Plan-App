from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).date()
    return start, end


def quarter_bounds(d: date) -> tuple[date, date]:
    q = (d.month - 1) // 3
    start = date(d.year, q * 3 + 1, 1)
    end = (pd.Timestamp(start) + pd.offsets.QuarterEnd(0)).date()
    return start, end


def business_days(start: date, end: date) -> int:
    """Inclusive count of Mon-Fri days between start and end."""
    return int(np.busday_count(start, pd.Timestamp(end).date() + pd.Timedelta(days=1)))


def quarter_months(d: date) -> list[int]:
    q = (d.month - 1) // 3
    return [q * 3 + 1, q * 3 + 2, q * 3 + 3]
