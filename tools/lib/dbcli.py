"""The one subprocess boundary for Databricks CLI calls: explicit profile, no ambient credentials."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
PROFILE = re.compile(r"^[A-Za-z0-9._-]+$")
FORBIDDEN = ("--profile", "-p", "--host", "--token", "--account-id")

Runner = Callable[..., subprocess.CompletedProcess]


class CliError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.args_list, self.returncode, self.stderr = args, returncode, stderr.strip()
        super().__init__(f"databricks {' '.join(args)} failed ({returncode}): {self.stderr[:2000]}")


class GuardError(RuntimeError):
    pass


def scrubbed_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Drop DATABRICKS_* overrides so only the selected profile decides host and credentials."""
    env = dict(os.environ if base is None else base)
    return {k: v for k, v in env.items() if not k.startswith("DATABRICKS_") or k == "DATABRICKS_CONFIG_FILE"}


def _run(argv: list[str], env: dict[str, str], timeout: int, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, env=env, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


class Cli:
    def __init__(self, profile: str, runner: Runner = _run, cwd: Path = ROOT):
        if not PROFILE.match(profile or ""):
            raise ValueError(f"invalid profile name {profile!r}")
        self.profile, self._runner, self._cwd = profile, runner, cwd

    def run(self, args: list[str], *, timeout: int = 600) -> str:
        for arg in args:
            if arg.split("=", 1)[0] in FORBIDDEN:
                raise ValueError(f"{arg!r} is not allowed; the profile is always passed explicitly")
        proc = self._runner(["databricks", *args, "--profile", self.profile], scrubbed_env(), timeout, self._cwd)
        if proc.returncode != 0:
            raise CliError(args, proc.returncode, proc.stderr or proc.stdout)
        return proc.stdout

    def json(self, args: list[str], *, timeout: int = 600) -> Any:
        out = self.run([*args, "--output", "json"], timeout=timeout)
        return json.loads(out) if out.strip() else None

    def api(self, method: str, path: str, body: dict | None = None, *, timeout: int = 600) -> Any:
        args = ["api", method, path]
        if body is not None:
            args += ["--json", json.dumps(body)]
        out = self.run(args, timeout=timeout)
        return json.loads(out) if out.strip() else None

    def host(self) -> str:
        """The profile's workspace host. `auth describe` exits 0 even when the login is dead, so check its status."""
        described = self.json(["auth", "describe"]) or {}
        host = ((described.get("details") or {}).get("host") or "").rstrip("/").lower()
        if described.get("status") == "error" or described.get("error"):
            raise GuardError(f"profile {self.profile} cannot authenticate; run: databricks auth login --host {host} "
                             f"--profile {self.profile}")
        if not host:
            raise GuardError(f"profile {self.profile} has no host")
        return host

    def current_user(self) -> str:
        return self.json(["current-user", "me"])["userName"]


def assert_host(cli: Cli, expected: str | None) -> str:
    actual = cli.host()
    if expected and actual != expected.rstrip("/").lower():
        raise GuardError(f"profile {cli.profile} points at {actual}, but the bundle target expects {expected}")
    return actual


def is_missing(error: CliError) -> bool:
    """True only for an explicit 'does not exist' answer; permission errors are never treated as absence."""
    text = error.stderr.lower()
    return ("does not exist" in text or "not found" in text) and "permission" not in text
