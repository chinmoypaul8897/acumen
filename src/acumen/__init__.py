"""Acumen Intelligence -- backtester + live screener for one frozen intraday NSE strategy.

The strategy specification lives in CONTEXT.md (section 3) and is LAW; this package
implements it and never improves on it. Engine modules (`bias`, `poc`, `signals`,
`simulate`) are pure functions over candles -- no I/O, no network, no clock reads
(CONTEXT 6, 7-E11/E12).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
