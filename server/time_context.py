"""Use the connected computer's persisted IANA timezone for agent-facing time."""
from datetime import datetime, timezone as datetime_timezone
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 128 or any(c in value for c in "\0\r\n"):
        raise ValueError("timezone must be an IANA timezone such as America/New_York")
    value = value.strip()
    try:
        return ZoneInfo(value).key
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Unknown IANA timezone: " + value) from exc


def machine_timezone():
    """Fallback before a desktop/browser has supplied its local timezone."""
    candidates = [os.environ.get("TZ", "").removeprefix(":")]
    try:
        candidates.append(Path("/etc/timezone").read_text().strip())
    except OSError:
        pass
    try:
        target = str(Path("/etc/localtime").resolve())
        if "/zoneinfo/" in target:
            candidates.append(target.split("/zoneinfo/", 1)[1])
    except OSError:
        pass
    for candidate in candidates:
        try:
            return validate_timezone(candidate)
        except ValueError:
            continue
    return "UTC"


def local_time_context(timezone=None, now=None):
    zone = validate_timezone(timezone) if timezone is not None else machine_timezone()
    if isinstance(now, datetime):
        if now.tzinfo is None:
            raise ValueError("Time context requires an aware datetime or an epoch timestamp")
        instant = now
    else:
        instant = datetime.fromtimestamp(time.time() if now is None else now, datetime_timezone.utc)
    local = instant.astimezone(ZoneInfo(zone))
    offset = local.strftime("%z")
    return {"timezone": zone, "current_time": local.isoformat(timespec="seconds"),
            "current_date": local.date().isoformat(), "utc_offset": offset[:3] + ":" + offset[3:],
            "timezone_abbreviation": local.tzname()}
