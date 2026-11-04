"""Production clock has no CLI override. Tests inject clocks into pure boundaries."""
import time


class Clock:
    def now_ms(self):
        return time.time_ns() // 1_000_000

    def monotonic_ms(self):
        return time.monotonic_ns() // 1_000_000
