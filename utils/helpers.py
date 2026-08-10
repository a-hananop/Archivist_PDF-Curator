"""
utils/helpers.py
=================
Small generic utilities: timing context manager, batching iterator,
statistics helpers used by the heading-detection heuristics, and an
`__init__.py`-free package marker for utils.
"""

from __future__ import annotations

import statistics
import time
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Sequence, TypeVar

T = TypeVar("T")


@contextmanager
def timer():
    """Context manager yielding an object with `.elapsed` seconds once exited."""
    class _Timer:
        elapsed: float = 0.0

    t = _Timer()
    start = time.perf_counter()
    try:
        yield t
    finally:
        t.elapsed = time.perf_counter() - start


def batched(iterable: Iterable[T], size: int) -> Iterator[List[T]]:
    """Yield successive lists of length `size` (last one may be shorter)."""
    batch: List[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def median(values: Sequence[float], default: float = 0.0) -> float:
    values = [v for v in values if v is not None]
    if not values:
        return default
    try:
        return statistics.median(values)
    except statistics.StatisticsError:
        return default


def most_common(values: Sequence[T], default: T = None) -> T:
    if not values:
        return default
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def safe_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {sec:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {sec:.1f}s"
