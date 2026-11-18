"""Seeded synthetic names. No real ESA employees, guests, or customers."""

from __future__ import annotations

import numpy as np

FIRST_NAMES = (
    "Avery", "Blake", "Casey", "Dana", "Elliot", "Finley", "Gray", "Harper", "Indigo", "Jordan",
    "Kendall", "Logan", "Morgan", "Noel", "Oakley", "Parker", "Quinn", "Reese", "Sage", "Taylor",
    "Rowan", "Skyler", "Emerson", "Hayden", "Jamie", "Kai", "Lane", "Marlow", "Nico", "Peyton",
    "Remy", "Sawyer", "Tatum", "Wren", "Arden", "Brooks", "Cameron", "Devon", "Ellis", "Frankie",
    "Greer", "Hollis", "Jules", "Kris", "Linden", "Micah", "Nova", "Oren", "Phoenix", "River",
    "Shiloh", "Tegan", "Umber", "Vale", "Winter", "Xen", "Yael", "Zion", "Ashton", "Bellamy",
)
LAST_NAMES = (
    "Alder", "Brightwater", "Calloway", "Dunmore", "Ellsworth", "Fairbanks", "Galloway", "Hartwell",
    "Ingram", "Jasper", "Kingsley", "Lockhart", "Merriweather", "Northcott", "Oakridge", "Prescott",
    "Quimby", "Radcliffe", "Sterling", "Thorne", "Underwood", "Vance", "Whitlock", "Yardley",
    "Ashby", "Blackwood", "Crestwood", "Driscoll", "Everly", "Fenwick", "Grantham", "Holloway",
    "Islington", "Jennings", "Kessler", "Langford", "Montague", "Norwood", "Ogden", "Pembroke",
    "Ravenscroft", "Sutherland", "Templeton", "Upton", "Westbrook", "Winslow", "Yates", "Zeller",
    "Abernathy", "Beaumont", "Chandler", "Delacroix", "Easton", "Fitzgerald", "Goodwin", "Hawthorne",
    "Irving", "Jacobsen", "Kincaid", "Lowell", "Mercer", "Nash", "Osborne", "Pryor", "Redford",
    "Sinclair", "Talbot", "Vaughn", "Whitaker", "York", "Ainsley", "Barrow", "Carrington", "Dempsey",
    "Eastwood", "Forsythe", "Garrison", "Huxley", "Jarvis", "Keaton",
)

COMPANY_PREFIXES = (
    "Summit", "Harbor Point", "Prairie", "Granite", "Blue Ridge", "Ironwood", "Lakeshore", "Redwood",
    "Keystone", "Silver Creek", "North Star", "Pioneer", "Cedar", "Atlas", "Beacon", "Canyon",
    "Evergreen", "Frontier", "Liberty", "Meridian", "Oakmont", "Pinnacle", "Riverbend", "Sterling",
    "Trailhead", "Vantage", "Westfield", "Willow", "Copper", "Highland",
)
COMPANY_SUFFIXES = ("LLC", "Inc.", "Co.", "Group", "Partners", "Holdings")


def person_names(rng: np.random.Generator, count: int) -> list[str]:
    """Return `count` distinct 'First Last' names."""
    pool = len(FIRST_NAMES) * len(LAST_NAMES)
    if count > pool:
        raise ValueError(f"cannot draw {count} distinct names from a pool of {pool}")
    picks = rng.choice(pool, size=count, replace=False)
    return [f"{FIRST_NAMES[p // len(LAST_NAMES)]} {LAST_NAMES[p % len(LAST_NAMES)]}" for p in picks]


def email_for(name: str) -> str:
    first, last = name.lower().split(" ", 1)
    return f"{first}.{last.replace(' ', '')}@example.com"


def company_name(rng: np.random.Generator, cores: tuple[str, ...], used: set[str]) -> str:
    """A distinct synthetic company name built from a prefix, an industry word, and a suffix."""
    for _ in range(50):
        name = (
            f"{COMPANY_PREFIXES[rng.integers(len(COMPANY_PREFIXES))]} "
            f"{cores[rng.integers(len(cores))]} "
            f"{COMPANY_SUFFIXES[rng.integers(len(COMPANY_SUFFIXES))]}"
        )
        if name not in used:
            used.add(name)
            return name
    base = f"{COMPANY_PREFIXES[rng.integers(len(COMPANY_PREFIXES))]} {cores[0]}"
    suffix = 2
    while f"{base} {suffix}" in used:
        suffix += 1
    used.add(f"{base} {suffix}")
    return f"{base} {suffix}"
