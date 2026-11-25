from datetime import timedelta


class TranscriptionQuotaExceededError(Exception):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(retry_after)

        self.retry_after: timedelta = retry_after


class NoAudioError(Exception):
    pass


# the audio is larger than the recognizer takes
class SpeechTooLongError(Exception):
    pass
