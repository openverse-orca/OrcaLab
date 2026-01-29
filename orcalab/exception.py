class TokenExpiredException(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    pass


class ConnectionFailedException(Exception):
    """连接服务器失败异常"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    pass
