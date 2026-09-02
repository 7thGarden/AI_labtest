import threading

_delay_ms = 0

_lock = threading.Lock()


def set_delay_ms(ms: int) -> int:
    global _delay_ms
    with _lock:
        _delay_ms = max(0, int(ms))
        return _delay_ms


def get_delay_ms() -> int:
    with _lock:
        return _delay_ms


def get_delay_seconds() -> float:
    with _lock:
        return _delay_ms / 1000.0