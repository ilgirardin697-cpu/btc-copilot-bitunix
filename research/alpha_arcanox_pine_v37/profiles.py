"""Two explicit profiles. Risk rules belong only to OWNER_B, never to Pine."""
from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

SOURCE_SHA256 = '058532c5c7964eefa3993b8aae761aef7598a542c7e43c7469ad0531f39e03a7'


@dataclass(frozen=True)
class Profile:
    name: str
    timezone_name: str
    asia_start: int
    asia_candles: int
    london_start: int
    london_candles: int
    whole_body: bool
    independent_sides: bool
    top_inset_pct: float = 3.0
    bottom_inset_pct: float = 3.0
    top_band: float = 500.0
    bottom_band: float = 500.0
    forward_bars: int = 24

    @property
    def tz(self):
        return (timezone(timedelta(hours=-4)) if self.timezone_name == 'UTC-4'
                else ZoneInfo(self.timezone_name))

    def metadata(self):
        return asdict(self)


PINE_A = Profile('PINE_A', 'America/New_York', 20, 4, 2, 4, False, True)
OWNER_B = Profile('OWNER_B', 'UTC-4', 20, 5, 1, 4, True, False)
PROFILES = {p.name: p for p in (PINE_A, OWNER_B)}
