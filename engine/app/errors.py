class AppError(Exception):
    def __init__(self, status: int, message: str, *, retryable: bool = False, retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after
