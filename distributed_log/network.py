import multiprocessing
from threading import Event


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
    __connectionState: Event
    __lock = multiprocessing.RLock()
    __heartbeat_alive_limit = 5
    __heartbeat_suspected_limit = 2
    __heartbeat_failed_requests = 0

    def __init__(self, dsn: str, mode: str, alive_limit: int = 5, suspected_rate: int = 2):
        self.__dsn = dsn
        self.__mode = mode
        self.__heartbeat_alive_limit = alive_limit
        self.__heartbeat_suspected_limit = suspected_rate
        self.__connectionState = Event()

        self.mark_as_healthy()

    def get_dsn(self) -> str:
        return self.__dsn

    def mark_as_healthy(self) -> None:
        with self.__lock:
            self.__status = self.__STATUS_HEALTHY
            self.__connectionState.set()  # mark as opened to sending requests
            self.__heartbeat_failed_requests = 0

    def mark_as_suspected(self) -> None:
        with self.__lock:
            self.__status = self.__STATUS_SUSPECTED

    def mark_as_unhealthy(self) -> None:
        with self.__lock:
            self.__status = self.__STATUS_UNHEALTHY
            self.__connectionState.clear()  # mark as closed to sending requests

    def is_healthy(self) -> bool:
        return self.__STATUS_HEALTHY == self.__status

    def is_suspected(self) -> bool:
        return self.__STATUS_SUSPECTED == self.__status

    def is_unhealthy(self) -> bool:
        return self.__STATUS_UNHEALTHY == self.__status

    def get_status(self) -> str:
        if self.is_healthy():
            return 'Healthy'
        elif self.is_suspected():
            return 'Suspected'
        elif self.is_unhealthy():
            return 'Unhealthy'

    def is_master(self) -> bool:
        return self.MODE_MASTER == self.__mode

    def is_secondary(self) -> bool:
        return self.MODE_SECONDARY == self.__mode

    def wait_until_healthy(self):
        self.__connectionState.wait()

    def heartbeat_failed(self):
        is_status_changed = False

        with self.__lock:
            self.__heartbeat_failed_requests += 1

            if self.__heartbeat_failed_requests >= self.__heartbeat_alive_limit:
                if not self.is_unhealthy():
                    is_status_changed = True
                    self.mark_as_unhealthy()
            elif self.__heartbeat_failed_requests >= self.__heartbeat_suspected_limit:
                if not self.is_suspected():
                    is_status_changed = True
                    self.mark_as_suspected()

        return is_status_changed
