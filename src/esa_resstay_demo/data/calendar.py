"""common.dim_date: one row per day, 1980-01-01 through 2050-12-31, in ESA's PascalCase layout."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from esa_resstay_demo.data.config import GenConfig
from esa_resstay_demo.data.frames import with_meta

DATE_START = date(1980, 1, 1)
DATE_END = date(2050, 12, 31)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def us_holidays(year: int) -> dict[date, str]:
    """US federal holidays on their actual (not observed) dates."""
    mon, thu = 0, 3
    holidays = {
        date(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 1, mon, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, mon, 3): "Presidents' Day",
        _last_weekday(year, 5, mon): "Memorial Day",
        date(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, mon, 1): "Labor Day",
        _nth_weekday(year, 10, mon, 2): "Columbus Day",
        date(year, 11, 11): "Veterans Day",
        _nth_weekday(year, 11, thu, 4): "Thanksgiving Day",
        date(year, 12, 25): "Christmas Day",
    }
    if year >= 2021:
        holidays[date(year, 6, 19)] = "Juneteenth"
    return holidays


def date_id(value: date) -> int:
    return value.year * 10000 + value.month * 100 + value.day


def build_dim_date(cfg: GenConfig) -> pd.DataFrame:
    idx = pd.date_range(DATE_START, DATE_END, freq="D")
    holidays: dict[date, str] = {}
    for year in range(DATE_START.year, DATE_END.year + 1):
        holidays.update(us_holidays(year))
    dates = pd.Series(idx.date)
    week_start = idx - pd.to_timedelta(idx.dayofweek, unit="D")
    month_start = idx - pd.to_timedelta(idx.day - 1, unit="D")
    holiday_names = dates.map(holidays)
    df = pd.DataFrame({
        "BK_Date_Dim_Id": (idx.year * 10000 + idx.month * 100 + idx.day).astype("int64"),
        "Date_Dt": dates,
        "Day_Of_Week_Nbr": (idx.dayofweek + 1).astype("int64"),
        "Day_Of_Week_Name": idx.day_name(),
        "Day_Of_Month_Nbr": idx.day.astype("int64"),
        "Day_Of_Year_Nbr": idx.dayofyear.astype("int64"),
        "Week_Of_Year_Nbr": idx.isocalendar().week.astype("int64").to_numpy(),
        "Week_Start_Dt": pd.Series(week_start.date),
        "Week_End_Dt": pd.Series((week_start + pd.Timedelta(days=6)).date),
        "Month_Nbr": idx.month.astype("int64"),
        "Month_Name": idx.month_name(),
        "Month_Start_Dt": pd.Series(month_start.date),
        "Month_End_Dt": pd.Series((idx + pd.offsets.MonthEnd(0)).date),
        "Qtr_Nbr": idx.quarter.astype("int64"),
        "Qtr_Name": "Q" + pd.Series(idx.quarter).astype(str),
        "Yr_Nbr": idx.year.astype("int64"),
        "Yr_Month_Nbr": (idx.year * 100 + idx.month).astype("int64"),
        "Is_Weekend_Flg": idx.dayofweek >= 5,
        "Is_Holiday_Flg": holiday_names.notna().to_numpy(),
        "Holiday_Name": holiday_names.where(holiday_names.notna(), None),
        "Same_Day_Last_Yr_Dt": pd.Series((idx - pd.DateOffset(years=1)).date),
        "Same_Weekday_Last_Yr_Dt": pd.Series((idx - pd.Timedelta(days=364)).date),
    })
    return with_meta(df, "ESA.REF.CALENDAR", cfg.dimension_load_ts, datetime(1980, 1, 1))
