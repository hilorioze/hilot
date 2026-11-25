import math
from datetime import timedelta


def format_size(size: int) -> str:
    if size >= 1024**3:
        return f"{round(size / 1024**3, 1):g} GB"

    if size >= 1024**2:
        return f"{round(size / 1024**2, 1):g} MB"

    return f"{round(size / 1024):g} KB"


def format_duration(duration: float) -> str:
    minutes, seconds = divmod(round(duration), 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


# a wait shows rounded up, in hours once it's longer than one
def format_wait(wait: timedelta) -> str:
    hours: int = math.ceil(wait.total_seconds() / 3600)

    return f"{hours} h" if hours > 1 else f"{math.ceil(wait.total_seconds() / 60)} min"
