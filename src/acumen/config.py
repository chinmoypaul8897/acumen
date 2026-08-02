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
(OPEN-1 was answered in Round 3 -- 1000 rupees -- and the committed config carries it; the
guard stays because a config that LOSES the amount must fail loudly, not size on a guess.)

``cost_per_trade`` and ``initial_capital`` are the same discipline for the other two money
numbers CONTEXT 3.5 fixes: the flat 100-rupee round-trip cost (R1-Q23) and the 1,00,000-rupee
starting capital (R1-Q21a). They live here, next to the risk amount, rather than as literals in
the simulator or the portfolio layer -- a money constant typed into an engine module is
invisible to the operator and to the architect's spec sync, which is exactly what REVIEW_9A
finding C1 caught. All three amounts are declared in RUPEES (the units
CONTEXT 3.5 states them in) and are converted ONCE, exactly, to the integer paise the engines
work in (CONTEXT 7-E11) by :meth:`Config.require_risk_per_trade_paise`,
:meth:`Config.cost_per_trade_paise` and :meth:`Config.initial_capital_paise`. The conversion
goes through ``Decimal`` so a fractional
rupee amount can never arrive as a float-rounded number of paise: an amount that is not a
whole number of paise is refused.

``paths.data_root`` and ``paths.cache_root`` are the other required-and-checked pair, for a
different reason: they name the MUTABLE STORES, and CLAUDE.md's Q-18 layer 1 puts those
outside the repository tree so that no git command can reach them. The loader refuses a
missing, relative, or in-repo store root rather than resolving one -- see
:func:`_require_outside_repo`. Every store and cache path in ``src/`` is derived from these
two keys; nothing hardcodes a store location.

This module performs file I/O and is NOT part of the pure engine layer; engine functions
receive already-loaded values as arguments (CONTEXT 6).

Source files in this package are ASCII-only on purpose: the operator's console encoding is
cp1252, where printing a traceback whose source line carries a rupee or section sign raises
UnicodeEncodeError. Spec symbols stay in the markdown documents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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
#: Every key is also REQUIRED to be present -- a missing money key must not resolve to a
#: default either.
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"risk_per_trade", "cost_per_trade", "initial_capital", "row_size", "paths"}
)

#: Keys that MAY be absent. Both belong to the Round-3 Q40-d capital-infeasibility flags and
#: both are deliberately unset until the trader answers Q43: a flag computed against a guessed
#: capital figure would mark real trades "infeasible" on this repo's authority, not his. Absent
#: (or null) means the flags are NOT COMPUTED and every output says so -- there is no default.
_OPTIONAL_KEYS: frozenset[str] = frozenset({"capital_reference", "margin_basis"})

#: CONTEXT 7-E11: prices and money are integer paise inside the engines. Rupee amounts in
#: config.yaml (the units CONTEXT 3.5 states them in) cross into that domain exactly once,
#: here.
PAISE_PER_RUPEE: int = 100

#: The two path keys that name the MUTABLE STORES. Q-18 layer 1 (CLAUDE.md, "Data-store
#: safety"): both must be present, both must be absolute, and neither may lie inside the
#: repository tree. Enforced by :func:`_validate_paths` rather than left to convention --
#: the whole point of the layer is that no git command can reach a store, and a store that
#: drifts back under the repo root is reachable again the moment someone runs
#: ``git worktree remove --force`` or ``git clean -xfd``.
STORE_ROOT_KEYS: tuple[str, ...] = ("data_root", "cache_root")


class ConfigError(RuntimeError):
    """Configuration is missing, malformed, or blocked by an open spec item."""


@dataclass(frozen=True)
class Config:
    """Validated contents of ``config.yaml``. Holds no secrets -- ever."""

    risk_per_trade: float | None
    cost_per_trade: float
    initial_capital: float
    row_size: int
    paths: Mapping[str, Path]
    source: Path
    #: Q40-d capital-infeasibility inputs. ``None`` means the trader's Q43 answer has not
    #: arrived and the flags are NOT COMPUTED (CONTEXT 3.5's disclosure list, chunk 9).
    capital_reference: float | None = None
    margin_basis: Decimal | None = None

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

    def require_risk_per_trade_paise(self) -> int:
        """The CONTEXT 3.5 risk per trade as exact integer paise -- what the sizer divides by.

        The simulator works entirely in integer paise (CONTEXT 7-E11), so the rupee amount
        crosses into that domain HERE and nowhere else: ``qty = floor(risk_paise /
        per_share_risk_paise)`` is then exact integer arithmetic with no float anywhere near
        a share count.

        Raises:
            ConfigError: ``risk_per_trade`` is null (see :meth:`require_risk_per_trade`), or
                it is not a whole number of paise.
        """
        return _rupees_to_paise(self.require_risk_per_trade(), "risk_per_trade", self.source)

    def cost_per_trade_paise(self) -> int:
        """The CONTEXT 3.5 flat round-trip cost as exact integer paise (R1-Q23: 100 rupees).

        Charged once per EXECUTED round trip; a day that produced no executed trade pays
        nothing (there is no round trip to charge).

        Raises:
            ConfigError: the amount is not a whole number of paise.
        """
        return _rupees_to_paise(self.cost_per_trade, "cost_per_trade", self.source)

    def initial_capital_paise(self) -> int:
        """CONTEXT 3.5's starting capital as exact integer paise (R1-Q21a: 1,00,000 rupees).

        The base of the equity curve and the denominator of return-on-initial-capital, CAGR and
        the E13 benchmark. There is NO default anywhere in ``src/`` -- ``acumen.portfolio``
        takes this value as a required argument, so a run whose config lost the amount cannot
        quietly fall back on a number typed into an engine module (REVIEW_9A finding C1).

        Raises:
            ConfigError: the amount is not a whole number of paise.
        """
        return _rupees_to_paise(self.initial_capital, "initial_capital", self.source)

    def capital_reference_paise(self) -> int | None:
        """The Q40-d capital reference as exact integer paise, or ``None`` while Q43 is open.

        ``None`` is a first-class answer here, unlike ``risk_per_trade``: the flags simply are
        not computed and the report says so in the words
        :data:`acumen.backtest.CAPITAL_FLAGS_PENDING_NOTE` carries.
        """
        if self.capital_reference is None:
            return None
        return _rupees_to_paise(self.capital_reference, "capital_reference", self.source)

    def margin_basis_text(self) -> str | None:
        """The Q40-d margin basis as its exact decimal TEXT, or ``None`` while Q43 is open.

        Text, not a float: it travels into a run manifest that must be byte-identical across
        runs, and a Decimal's own string form is exact.
        """
        return None if self.margin_basis is None else str(self.margin_basis)

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

    unknown = sorted(set(raw) - _ALLOWED_KEYS - _OPTIONAL_KEYS)
    if unknown:
        raise ConfigError(
            f"Unknown key(s) in {path}: {', '.join(unknown)}. "
            f"Allowed keys: {', '.join(sorted(_ALLOWED_KEYS | _OPTIONAL_KEYS))}."
        )
    missing = sorted(_ALLOWED_KEYS - set(raw))
    if missing:
        raise ConfigError(f"Missing key(s) in {path}: {', '.join(missing)}.")

    if include_env:
        load_env()

    return Config(
        risk_per_trade=_validate_risk_per_trade(raw["risk_per_trade"], path),
        cost_per_trade=_validate_cost_per_trade(raw["cost_per_trade"], path),
        initial_capital=_validate_initial_capital(raw["initial_capital"], path),
        row_size=_validate_row_size(raw["row_size"], path),
        capital_reference=_validate_capital_reference(raw.get("capital_reference"), path),
        margin_basis=_validate_margin_basis(raw.get("margin_basis"), path),
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


def _validate_cost_per_trade(value: Any, path: Path) -> float:
    """The flat round-trip cost (CONTEXT 3.5, R1-Q23) -- a positive INR amount, never null.

    Unlike ``risk_per_trade`` there is no open item behind this number: CONTEXT 3.5 states it
    outright, so a null here is a config that lost a spec value, not a pending answer.
    """
    if value is None:
        raise ConfigError(
            f"cost_per_trade is null in {path}: CONTEXT 3.5 fixes the flat round-trip cost "
            "(R1-Q23) and allows no default -- fill the spec amount in config.yaml."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"cost_per_trade in {path} must be a positive INR number (CONTEXT 3.5), "
            f"got {type(value).__name__}."
        )
    if value <= 0:
        raise ConfigError(f"cost_per_trade in {path} must be > 0, got {value}.")
    return value


def _validate_initial_capital(value: Any, path: Path) -> float:
    """CONTEXT 3.5's starting capital -- a positive INR amount, never null.

    Like ``cost_per_trade`` and unlike ``capital_reference``, there is no open item behind this
    number: CONTEXT 3.5 states it outright (R1-Q21a), so a null here is a config that LOST a
    spec value rather than a pending trader answer.
    """
    if value is None:
        raise ConfigError(
            f"initial_capital is null in {path}: CONTEXT 3.5 fixes the starting capital "
            "(R1-Q21a) and allows no default -- fill the spec amount in config.yaml."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"initial_capital in {path} must be a positive INR number (CONTEXT 3.5), "
            f"got {type(value).__name__}."
        )
    if value <= 0:
        raise ConfigError(f"initial_capital in {path} must be > 0, got {value}.")
    return value


def _validate_capital_reference(value: Any, path: Path) -> float | None:
    """``null``/absent (Q43 pending) or a positive INR amount -- nothing else.

    CONTEXT 3.5's Q40-d disclosure list needs a capital figure to mark the trades his capital
    could not actually have taken. The figure is the TRADER's (Q43); until it arrives this stays
    null and the flags are not computed. There is deliberately no default -- not even CONTEXT
    3.5's own 1,00,000 capital line, because the flag question the architect put to him is
    which figure the FLAGS should use.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"capital_reference in {path} must be null (Q43 pending) or a positive INR "
            f"number, got {type(value).__name__}."
        )
    if value <= 0:
        raise ConfigError(f"capital_reference in {path} must be > 0, got {value}.")
    return value


def _validate_margin_basis(value: Any, path: Path) -> Decimal | None:
    """``null``/absent (Q43 pending) or a positive multiple of the capital reference.

    A "typical MIS tier" in CONTEXT 3.5's own words is a MULTIPLE of the cash capital (his
    example: 1,00,000 cash vs a 5,00,000 tier). Stored as a Decimal so the tier boundary is
    exact paise arithmetic, never a float comparison (CONTEXT 7-E11).
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ConfigError(
            f"margin_basis in {path} must be null (Q43 pending) or a positive multiple of "
            f"capital_reference, got {type(value).__name__}."
        )
    try:
        basis = Decimal(str(value))
    except InvalidOperation as exc:
        raise ConfigError(f"margin_basis in {path} is not a number: {value!r}.") from exc
    if basis <= 0:
        raise ConfigError(f"margin_basis in {path} must be > 0, got {value}.")
    return basis


def _rupees_to_paise(value: float, field: str, path: Path) -> int:
    """Rupees -> exact integer paise (CONTEXT 7-E11). Refuses a fractional paisa.

    ``Decimal(str(value))`` rather than ``value * 100``: the second is float arithmetic on a
    money amount, which is exactly what CONTEXT 7-E11 keeps out of this codebase.
    """
    try:
        scaled = Decimal(str(value)) * PAISE_PER_RUPEE
    except InvalidOperation as exc:  # pragma: no cover -- the validators reject non-numbers
        raise ConfigError(f"{field} in {path} is not a number: {value!r}.") from exc
    if scaled != scaled.to_integral_value():
        raise ConfigError(
            f"{field} in {path} must be a whole number of paise (CONTEXT 7-E11); "
            f"{value} rupees is {scaled} paise."
        )
    return int(scaled)


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
    """Resolve every declared path, then enforce Q-18 layer 1 on the two store roots."""
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"paths in {path} must be a non-empty mapping of name -> directory.")
    base = path.parent
    resolved: dict[str, Path] = {}
    declared: dict[str, Path] = {}
    for name, raw_path in value.items():
        if not isinstance(name, str) or not isinstance(raw_path, str) or not raw_path.strip():
            raise ConfigError(
                f"paths entry {name!r} in {path} must map a name to a non-empty path string."
            )
        candidate = Path(raw_path)
        declared[name] = candidate
        resolved[name] = candidate if candidate.is_absolute() else (base / candidate).resolve()

    missing = [name for name in STORE_ROOT_KEYS if name not in resolved]
    if missing:
        raise ConfigError(
            f"paths in {path} is missing {', '.join(missing)}. CLAUDE.md's Q-18 layer 1 requires "
            f"the mutable stores to be declared here and to live OUTSIDE the repository tree; "
            f"there is no default, because a store nobody declared is a store nobody snapshots."
        )
    for name in STORE_ROOT_KEYS:
        _require_outside_repo(name, declared[name], resolved[name], path)
    return resolved


def _require_outside_repo(name: str, declared: Path, root: Path, source: Path) -> None:
    """Refuse a store root that is not absolute, or that lies inside the repository tree.

    Q-18 layer 1 (CLAUDE.md, "Data-store safety"), made structural. On 31-Jul-2026 the local
    ``data/`` and ``cache/`` trees were destroyed because they sat inside the repo and a
    ``git worktree remove --force`` reached them through two NTFS junctions. Outside the tree,
    no git command can reach a store however it is invoked -- but only while the config keeps
    pointing outside, which is what this check holds in place. It is deliberately a REFUSAL
    and not a warning: a silently in-repo store is the exact failure mode the layer exists to
    end, and it is invisible until the day it is fatal.
    """
    if not declared.is_absolute():
        raise ConfigError(
            f"paths.{name} in {source} must be an ABSOLUTE path outside the repository tree "
            f"(CLAUDE.md Q-18 layer 1); got the relative value {str(declared)!r}. A relative "
            f"store root is resolved against the config file's own directory -- which, for the "
            f"committed config, IS the repository root -- so it names an in-repo store however "
            f"it is spelled. Write the absolute path."
        )
    repo = REPO_ROOT.resolve()
    try:
        inside = root.resolve().is_relative_to(repo)
    except OSError:  # pragma: no cover -- an unresolvable root is caught at first use
        inside = False
    if inside:
        raise ConfigError(
            f"paths.{name} in {source} points INSIDE the repository tree ({root}). CLAUDE.md's "
            f"Q-18 layer 1 requires the mutable stores to live outside it, so that no git "
            f"command can reach them -- an in-repo store was destroyed by "
            f"`git worktree remove --force` on 31-Jul-2026 (QUESTIONS.md Q-18). Move the store "
            f"and point {name} at its new home; do not point it back inside."
        )
