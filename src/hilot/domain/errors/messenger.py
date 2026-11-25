class AlreadySentError(Exception):
    pass


class FileReferenceExpiredError(Exception):
    pass


class MessageGoneError(Exception):
    pass


class ButtonNotFoundError(Exception):
    pass


# the inline bot can't message the account, which hasn't started it, or the chat doesn't take inline bots
class RichUnavailableError(Exception):
    pass
