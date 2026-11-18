from datetime import date

from esa_resstay_demo.data.calendar import build_dim_date, us_holidays
from esa_resstay_demo.data.reference import KEY_ACCOUNTS, build_dim_crm_account, build_dim_los, los_bands


def test_dim_date_covers_1980_to_2050_in_esa_layout(tiny_cfg):
    df = build_dim_date(tiny_cfg)
    assert len(df) == 25933 and df["BK_Date_Dim_Id"].is_unique
    leap = df[df["BK_Date_Dim_Id"] == 20240229].iloc[0]
    assert leap["Same_Day_Last_Yr_Dt"] == date(2023, 2, 28) and leap["Same_Weekday_Last_Yr_Dt"] == date(2023, 3, 2)
    assert leap["Week_Start_Dt"] == date(2024, 2, 26) and leap["Month_End_Dt"] == date(2024, 2, 29)
    assert leap["Qtr_Name"] == "Q1" and leap["Day_Of_Week_Name"] == "Thursday" and not leap["Is_Weekend_Flg"]


def test_holidays():
    assert us_holidays(2026)[date(2026, 11, 26)] == "Thanksgiving Day"
    assert date(2020, 6, 19) not in us_holidays(2020)


def test_los_bands_match_the_resstay_tiers(tiny_cfg):
    assert [los_bands(n)[0] for n in (0, 6, 7, 14, 15, 29, 30, 365)] == ["0-6", "0-6", "7-14", "7-14", "15-29", "15-29", "30+", "30+"]
    df = build_dim_los(tiny_cfg)
    assert len(df) == 366 and df["bk_los_id"].tolist()[:3] == ["0", "1", "2"]


def test_crm_accounts(tiny_cfg):
    df = build_dim_crm_account(tiny_cfg)
    assert len(df) == 3000 and df["account_name"].is_unique
    assert df["account_name"].head(len(KEY_ACCOUNTS)).tolist() == [name for name, _ in KEY_ACCOUNTS]
    assert df["key_account_flag"].sum() == len(KEY_ACCOUNTS)
    assert df["account_owner_email"].str.endswith("@example.com").all()
    assert set(df["parent_account_id"].dropna()) <= set(df["bk_crm_account_id"])


def test_as_of_defaults_to_yesterday_in_new_york_not_utc():
    from datetime import datetime, timezone
    from esa_resstay_demo.data.config import yesterday_in_new_york
    # 03:00 UTC on Nov 17 is still Nov 16 in New York, so the last night audit is Nov 15.
    assert yesterday_in_new_york(datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)) == date(2026, 11, 15)
    assert yesterday_in_new_york(datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)) == date(2026, 11, 16)


def test_story_window_refuses_as_of_dates_after_the_planted_renovation():
    import pytest
    from esa_resstay_demo.data.config import STORY_WINDOW_DAYS, check_story_window
    assert STORY_WINDOW_DAYS == 30
    check_story_window(date(2026, 12, 16), date(2026, 11, 16))          # exactly 30 days later is allowed
    with pytest.raises(ValueError, match="more than 30 days after the story anchor 2026-11-16"):
        check_story_window(date(2026, 12, 17), date(2026, 11, 16))
