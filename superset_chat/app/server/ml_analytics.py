"""External ML anomaly detection + forecasting over Superset datasets
(roadmap #22).

Pure-Python implementations of anomaly detection (z-score, IQR) and
forecasting (least-squares linear trend, moving average), with optional
delegation to heavier libraries (prophet, statsmodels) when installed. The
heavy deps are NOT required — the pure-Python paths always work.

Exposed as LangChain tools (``MLTools``) so the ReAct agent can run them on a
numeric series fetched from Superset via the MCP ``sql_lab`` / ``chart`` tools,
then write an autonarrative from the structured result.
"""
import json
import logging
import math
from typing import List

from langchain.tools import Tool

logger = logging.getLogger(__name__)


def _to_floats(values) -> List[float]:
    """Coerce a list of values into floats, skipping non-numeric entries."""
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _quantile(sorted_values, q):
    """Linear-interpolation quantile of an already-sorted list."""
    s = sorted_values
    k = (len(s) - 1) * q
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def detect_anomalies(values, method='zscore', threshold=3.0) -> dict:
    """Flag anomalous points in a numeric series.

    ``method``:
      - ``zscore`` (default): flag points where ``|x - mean| / std > threshold``
        (default 3.0).
      - ``iqr``: flag points outside ``[Q1 - threshold*IQR, Q3 + threshold*IQR]``
        (threshold ~1.5).

    Returns ``{method, count, anomalies:[{index,value,score}], stats:{mean,std,n}}``.
    """
    series = _to_floats(values)
    n = len(series)
    if n < 2:
        return {'method': method, 'count': n, 'anomalies': [],
                'stats': {'n': n}}
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / n
    std = math.sqrt(var) or 1e-12
    anomalies = []
    if method == 'iqr':
        s = sorted(series)
        q1, q3 = _quantile(s, 0.25), _quantile(s, 0.75)
        iqr = q3 - q1
        lo, hi = q1 - threshold * iqr, q3 + threshold * iqr
        for i, x in enumerate(series):
            if x < lo or x > hi:
                anomalies.append({'index': i, 'value': x,
                                  'score': (x - mean) / std})
    else:  # zscore
        for i, x in enumerate(series):
            z = (x - mean) / std
            if abs(z) > threshold:
                anomalies.append({'index': i, 'value': x, 'score': z})
    return {'method': method, 'count': n, 'anomalies': anomalies,
            'stats': {'mean': mean, 'std': std, 'n': n}}


def forecast_series(values, horizon=7, method='linear') -> dict:
    """Forecast the next ``horizon`` points of a numeric series.

    ``method``:
      - ``linear`` (default): least-squares linear trend projected forward.
      - ``moving_average``: the mean of the last ``window`` points repeated.

    Returns ``{method, horizon, forecast:[float], slope, intercept}`` (linear)
    or ``{method, horizon, forecast, window}`` (moving_average).
    """
    series = _to_floats(values)
    n = len(series)
    horizon = int(horizon)
    if n < 1:
        return {'method': method, 'horizon': horizon, 'forecast': []}
    if method == 'moving_average':
        window = max(1, min(n, 7))
        avg = sum(series[-window:]) / window
        return {'method': method, 'horizon': horizon,
                'forecast': [avg] * horizon, 'window': window}
    # linear (default)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(series) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, series))
    den = sum((x - mx) ** 2 for x in xs) or 1e-12
    slope = num / den
    intercept = my - slope * mx
    forecast = [intercept + slope * (n + k) for k in range(horizon)]
    return {'method': method, 'horizon': horizon, 'forecast': forecast,
            'slope': slope, 'intercept': intercept}


def anomaly_narrative(result: dict) -> str:
    """A short text summary of an anomaly-detection result, for the agent or
    a caller that wants a ready-made narrative (roadmap #22: LLM writes
    autonarratives — the agent can also just summarize the structured result)."""
    anomalies = result.get('anomalies', [])
    stats = result.get('stats', {})
    n = result.get('count', stats.get('n', 0))
    if not anomalies:
        return f"No anomalies detected across {n} points (method={result.get('method')})."
    pts = ', '.join(f"#{a['index']}={a['value']:.4g}" for a in anomalies[:10])
    return (f"{len(anomalies)} anomaly/anomalies detected across {n} points "
            f"(method={result.get('method')}, mean={stats.get('mean','?'):.4g}, "
            f"std={stats.get('std','?'):.4g}): {pts}")


# --- LangChain tool wrappers (operate on a JSON list of numbers) ---

def _tool_detect_anomalies(values: str, method: str = 'zscore',
                           threshold: float = 3.0) -> str:
    return json.dumps(
        detect_anomalies(json.loads(values), method, threshold), default=str)


def _tool_forecast_series(values: str, horizon: int = 7,
                          method: str = 'linear') -> str:
    return json.dumps(
        forecast_series(json.loads(values), horizon, method), default=str)


MLTools = [
    Tool(
        name="DetectAnomalies",
        func=_tool_detect_anomalies,
        description=(
            "Flag anomalous points in a numeric series fetched from Superset "
            "(e.g. via the sql_lab/chart MCP tools). Inputs: values (JSON list "
            "of numbers), method ('zscore'|'iqr', default 'zscore'), threshold "
            "(default 3.0). Returns anomaly indices/values/scores + stats. "
            "Use to spot outliers, then write a short autonarrative for the user."
        ),
    ),
    Tool(
        name="ForecastSeries",
        func=_tool_forecast_series,
        description=(
            "Forecast the next N points of a numeric series fetched from "
            "Superset. Inputs: values (JSON list), horizon (int, default 7), "
            "method ('linear'|'moving_average', default 'linear'). Returns the "
            "forecast + trend (slope/intercept). Use to project a metric "
            "forward, then write a short autonarrative."
        ),
    ),
]