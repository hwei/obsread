class ObsreadError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code
