class AlreadySentError(Exception):
    pass


class FileReferenceExpiredError(Exception):
    pass


class MessageGoneError(Exception):
    pass


class ButtonNotFoundError(Exception):
    pass


# the inline bot can't message the account, which hasn't started it, the chat doesn't take inline bots, or the bot fails
class RichUnavailableError(Exception):
    pass
