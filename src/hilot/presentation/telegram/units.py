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
