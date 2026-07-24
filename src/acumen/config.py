"""Configuration loader -- `config.yaml` + `.env`.

Two sources, one loader:

* ``config.yaml`` -- non-secret run settings, committed (CONTEXT 6).
* ``.env`` -- SmartAPI credentials. Values are read on demand and are NEVER printed,
  logged, returned in an exception message, or stored on the :class:`Config` object
  (CLAUDE.md rule 4, CONTEXT 4.3).

``risk_per_trade`` is deliberately REQUIRED-EMPTY. CONTEXT 9 OPEN-1 (the trader's INR risk
amount) is unanswered and the registry states "code takes ``risk_per_trade`` as required
config; no default". Every simulation / position-sizing path must therefore call
:meth:`Config.require_risk_per_trade` before it sizes anything: while the value is null that
call raises :class:`ConfigError` instead of letting a guessed number reach real money.

This module performs file I/O and is NOT part of the pure engine layer; engine functions
receive already-loaded values as arguments (CONTEXT 6).

Source files in this package are ASCII-only on purpose: the operator's console encoding is
cp1252, where printing a traceback whose source line carries a rupee or section sign raises
UnicodeEncodeError. Spec symbols stay in the markdown documents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from dotenv import load_dotenv

#: Repository root -- src/acumen/config.py -> src/acumen -> src -> <repo root>.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Default locations of the two configuration sources.
DEFAULT_CONFIG_PATH: Path = REPO_ROOT / "config.yaml"
DEFAULT_ENV_PATH: Path = REPO_ROOT / ".env"

#: Top-level keys config.yaml is allowed to carry. Unknown keys are a hard error: a typo
#: that silently falls back to a default is exactly the class of bug CLAUDE.md rule 1 bans.
_ALLOWED_KEYS: frozenset[str] = frozenset({"risk_per_trade", "row_size", "paths"})


class ConfigError(RuntimeError):
    """Configuration is missing, malformed, or blocked by an open spec item."""


@dataclass(frozen=True)
class Config:
    """Validated contents of ``config.yaml``. Holds no secrets -- ever."""

    risk_per_trade: float | None
    row_size: int
    paths: Mapping[str, Path]
    source: Path

    def require_risk_per_trade(self) -> float:
        """Return the INR risk per trade, or refuse to run.

        Call this at the top of every simulation / position-sizing path (chunk 8 onward).

        Raises:
            ConfigError: while ``risk_per_trade`` is null -- CONTEXT 9 OPEN-1 is open and
                there is no legal default.
        """
        if self.risk_per_trade is None:
            raise ConfigError(
                "risk_per_trade is not set in "
                f"{self.source}: simulation and position sizing are BLOCKED. "
                "CONTEXT 9 OPEN-1 (the trader's INR risk-per-trade amount) is still open and "
                "CONTEXT 9 allows no default -- the architect must fill risk_per_trade in "
                "config.yaml before any trade can be sized (CONTEXT 3.5)."
            )
        return self.risk_per_trade

    def path(self, name: str) -> Path:
        """Return the resolved filesystem path registered under ``name``."""
        try:
            return self.paths[name]
        except KeyError:
            known = ", ".join(sorted(self.paths)) or "<none>"
            raise ConfigError(
                f"Unknown path key {name!r} in {self.source}. Declared paths: {known}."
            ) from None


def load_env(env_path: Path | None = None, *, override: bool = False) -> Path | None:
    """Load ``.env`` into ``os.environ``.

    Returns the path that was loaded, or ``None`` when no ``.env`` exists (a bare clone is
    valid -- only the network chunks need credentials). The file's CONTENTS are never
    returned, printed or logged.
    """
    path = Path(env_path) if env_path is not None else DEFAULT_ENV_PATH
    if not path.is_file():
        return None
    load_dotenv(path, override=override)
    return path


def env_value(name: str, *, required: bool = True) -> str | None:
    """Return the environment value for ``name`` (loading ``.env`` first if needed).

    Raises:
        ConfigError: when ``required`` and the variable is absent or empty. The message
            names the VARIABLE only -- never its value (CLAUDE.md rule 4).
    """
    load_env()
    value = os.environ.get(name)
    if required and not value:
        raise ConfigError(
            f"Missing required environment variable {name!r}. Add it to .env "
            "(the file is gitignored; never print, log or commit its contents)."
        )
    return value


def load_config(config_path: Path | None = None, *, include_env: bool = True) -> Config:
    """Load and validate ``config.yaml`` (and, by default, ``.env``).

    Args:
        config_path: config file to read; defaults to ``<repo root>/config.yaml``.
        include_env: also load ``.env`` into ``os.environ``. No value is read here -- use
            :func:`env_value` at the point of use.

    Raises:
        ConfigError: the file is missing, is not a mapping, has unknown/missing keys, or
            carries a value that violates CONTEXT.md.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # malformed YAML -- surface the parser's own detail
        raise ConfigError(f"Could not parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a top-level mapping, got {type(raw).__name__}.")

    unknown = sorted(set(raw) - _ALLOWED_KEYS)
    if unknown:
        raise ConfigError(
            f"Unknown key(s) in {path}: {', '.join(unknown)}. "
            f"Allowed keys: {', '.join(sorted(_ALLOWED_KEYS))}."
        )
    missing = sorted(_ALLOWED_KEYS - set(raw))
    if missing:
        raise ConfigError(f"Missing key(s) in {path}: {', '.join(missing)}.")

    if include_env:
        load_env()

    return Config(
        risk_per_trade=_validate_risk_per_trade(raw["risk_per_trade"], path),
        row_size=_validate_row_size(raw["row_size"], path),
        paths=_validate_paths(raw["paths"], path),
        source=path,
    )


def _validate_risk_per_trade(value: Any, path: Path) -> float | None:
    """``null`` (OPEN-1 pending) or a positive INR amount -- nothing else."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"risk_per_trade in {path} must be null (OPEN-1 pending) or a positive INR "
            f"number, got {type(value).__name__}."
        )
    if value <= 0:
        raise ConfigError(f"risk_per_trade in {path} must be > 0, got {value}.")
    return value


def _validate_row_size(value: Any, path: Path) -> int:
    """Volume-profile Row Size N (CONTEXT 3.3) -- a whole number >= 1."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"row_size in {path} must be a whole number (CONTEXT 3.3), "
            f"got {type(value).__name__}."
        )
    if value < 1:
        raise ConfigError(f"row_size in {path} must be >= 1, got {value}.")
    return value


def _validate_paths(value: Any, path: Path) -> Mapping[str, Path]:
    """Resolve every declared path against the config file's directory."""
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"paths in {path} must be a non-empty mapping of name -> directory.")
    base = path.parent
    resolved: dict[str, Path] = {}
    for name, raw_path in value.items():
        if not isinstance(name, str) or not isinstance(raw_path, str) or not raw_path.strip():
            raise ConfigError(
                f"paths entry {name!r} in {path} must map a name to a non-empty path string."
            )
        candidate = Path(raw_path)
        resolved[name] = candidate if candidate.is_absolute() else (base / candidate).resolve()
    return resolved
