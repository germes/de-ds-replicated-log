class Server:
    """
    The service class for DataManager represents a simple data object for dealing with replica instance information
    """
    __STATUS_HEALTHY = 'healthy'
    __STATUS_SUSPECTED = 'suspected'
    __STATUS_UNHEALTHY = 'unhealthy'

    MODE_MASTER = 'master'
    MODE_SECONDARY = 'secondary'

    __dsn: str
    __mode: str
    __status: str

    def __init__(self, dsn: str, mode: str) -> object:
        self.__dsn = dsn
        self.__mode = mode
        self.__status = self.__STATUS_HEALTHY

    def get_dsn(self) -> str:
        return self.__dsn

    def mark_as_healthy(self) -> None:
        self.__status = self.__STATUS_HEALTHY

    def mark_as_suspected(self) -> None:
        self.__status = self.__STATUS_SUSPECTED

    def mark_as_unhealthy(self) -> None:
        self.__status = self.__STATUS_UNHEALTHY

    def is_healthy(self) -> bool:
        return self.__STATUS_HEALTHY == self.__status

    def is_master(self) -> bool:
        return self.__MODE_MASTER == self.__mode

    def is_secondary(self) -> bool:
        return self.__MODE_SECONDARY == self.__mode
