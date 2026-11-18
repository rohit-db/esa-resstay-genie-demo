"""Generator configuration and the fixed story calendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_SEED = 20261117
DEFAULT_SIM_START = date(2024, 7, 1)
DEFAULT_HISTORY_START = date(2024, 11, 1)
BOOKING_HORIZON_DAYS = 120
MIN_HISTORY_DAYS = 400
OPEN_ENDED = datetime(9999, 12, 31, 23, 59, 59)
ADR_GROWTH = 0.025
STORY_WINDOW_DAYS = 30   # the planted renovation runs until story_anchor_date + 30 days


def check_story_window(as_of: date, anchor: date) -> None:
    """Refuse as-of dates after the planted renovation ends; the stories would no longer hold."""
    if (as_of - anchor).days > STORY_WINDOW_DAYS:
        raise ValueError(f"as-of {as_of} is more than {STORY_WINDOW_DAYS} days after the story anchor {anchor}; "
                         "the planted renovation has ended. Re-anchor with a new --state file (and a fresh catalog).")


def yesterday_in_new_york(now: datetime | None = None) -> date:
    """The last completed night audit, in ESA's corporate time zone."""
    zone = ZoneInfo("America/New_York")
    current = (now or datetime.now(zone)).astimezone(zone)
    return current.date() - timedelta(days=1)


@dataclass(frozen=True)
class StoryDates:
    trend_reference: date
    renovation_start: date
    renovation_end: date
    promo_start: date
    promo_end: date
    account_ramp_start: date
    dm_change: date
    brand_conversion: date


@dataclass(frozen=True)
class GenConfig:
    as_of_date: date
    story_anchor_date: date
    seed: int = DEFAULT_SEED
    scale_properties: int = 600
    sim_start_date: date = DEFAULT_SIM_START
    history_start_date: date = DEFAULT_HISTORY_START

    def __post_init__(self) -> None:
        problems = []
        if self.scale_properties < 1:
            problems.append("scale_properties must be at least 1")
        if not self.sim_start_date < self.history_start_date:
            problems.append("sim_start_date must be before history_start_date")
        if (self.story_anchor_date - self.history_start_date).days < MIN_HISTORY_DAYS:
            problems.append(f"story_anchor_date must be at least {MIN_HISTORY_DAYS} days after history_start_date")
        if self.as_of_date < self.story_anchor_date:
            problems.append("as_of_date must not be before story_anchor_date")
        if problems:
            raise ValueError("; ".join(problems))

    @property
    def horizon_end(self) -> date:
        """Exclusive end of the simulation: future bookings are generated this far ahead."""
        return self.as_of_date + timedelta(days=BOOKING_HORIZON_DAYS)

    @property
    def stories(self) -> StoryDates:
        anchor = self.story_anchor_date
        return StoryDates(
            trend_reference=anchor - timedelta(days=182),
            renovation_start=anchor - timedelta(days=60),
            renovation_end=anchor + timedelta(days=30),
            promo_start=anchor - timedelta(days=120),
            promo_end=anchor + timedelta(days=60),
            account_ramp_start=anchor - timedelta(days=90),
            dm_change=anchor - timedelta(days=200),
            brand_conversion=anchor - timedelta(days=300),
        )

    @property
    def dimension_load_ts(self) -> datetime:
        """Dimensions are reloaded the morning after the as-of night audit."""
        return datetime.combine(self.as_of_date + timedelta(days=1), time(5, 0))

    def day_index(self, value: date) -> int:
        return (value - self.sim_start_date).days

    def date_at(self, index: int) -> date:
        return self.sim_start_date + timedelta(days=int(index))
