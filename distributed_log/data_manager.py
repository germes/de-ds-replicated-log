from distributed_log import storage
from distributed_log.network import Server
from distributed_log.setup_logger import logger
from threading import Condition
from threading import Timer
from threading import Thread
from typing import Optional
import multiprocessing
import yaml
import os
import json
import requests
import queue


class DataManagerReadonlyModeException(Exception):
    pass


class CountDownLatch:
    def __init__(self, count):
        self.count = count
        self.condition = Condition()

    def count_down(self):
        with self.condition:
            if self.count == 0:
                return

            self.count -= 1

            if self.count == 0:
                self.condition.notify_all()

    def wait(self):
        with self.condition:
            if self.count == 0:
                return

            self.condition.wait()


class RepeatTimer(Timer):
    """
    Service class to implement repeatable actions based on Python thread synchronization primitive Timer
    """

    def __init__(self, interval, function, args=None, kwargs=None):
        super().__init__(interval, function, args, kwargs)

    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class DataManager:
    """
    Responsible for all data processing, represents a thread-safe singleton and supports next features:
     - operating with provided storage - creating/saving/getting data from storage
     - can work both in Master and Secondary mode
     - contains information about secondaries and managing the replication process
    """
    MODE_MASTER = 'master'
    MODE_SECONDARY = 'secondary'

    __QUEUE_ITEM_NODE_STATUS_CHANGED = 'node_status_changed'

    __is_new = True
    __instance = None
    __lock = multiprocessing.Lock()
    __storage: storage.DataStorageInterface
    __mode: str
    __app_name: str
    __quorum_size: int = None
    __readonly = False
    __nodes: dict[str, Server, ] = {}
    __heartbeat_interval = 1
    __heartbeat_threads = []
    __system_queue = queue.Queue()

    def __new__(cls, mode: str, storage_object: storage.DataStorageInterface, app_name: str, config: dict):
        """
        :param mode: Master or Secondary
        :param storage_object: storage object that implements DataStorageInterface
        :param app_name: Application name - used for logging
        """
        if not cls.__instance:
            with cls.__lock:
                if not cls.__instance:
                    cls.__instance = super(DataManager, cls).__new__(cls)
        return cls.__instance

    def __init__(self, mode: str, storage_object: storage.DataStorageInterface, app_name: str, config: dict):
        """
        :param mode: Master or Secondary
        :param storage_object: storage object that implements DataStorageInterface
        :param app_name: Application name - used for logging
        :param config: application config, contains information about secondaries and quorum size
        """

        if not self.__is_new:
            # skip initializing because instance is already set
            return

        self.__is_new = False

        if mode not in [self.MODE_MASTER, self.MODE_SECONDARY]:
            raise Exception("Unsupported mode " + mode)

        self.__mode = mode
        self.__storage = storage_object
        self.__app_name = app_name

        if self.is_master():
            secondaries = {} if 'secondaries' not in config else config['secondaries']

            for secondary_name, secondary_address in secondaries.items():
                self.__nodes[secondary_name] = Server(secondary_address, Server.MODE_SECONDARY)

            if 'quorum' in config:
                self.__quorum_size = config['quorum']

            if 'heartbeat_interval_seconds' in config:
                self.__heartbeat_interval = config['heartbeat_interval_seconds']

    def startup(self):
        self.__log(' node startup')
        self.__start_heartbeat()

        if self.is_master():
            consumer = Thread(target=self.__handle_queue, daemon=True)
            consumer.start()

    def shutdown(self):
        self.__log(' node shutdown')

        if self.is_master():
            self.__system_queue.put(None)  # stop the consumer thread

        self.__stop_heartbeat()

    def __handle_queue(self):
        self.__log('Start DataManager queue processing')

        while True:
            item = self.__system_queue.get(block=True)

            if item is None:
                break

            if self.__QUEUE_ITEM_NODE_STATUS_CHANGED == item:
                self.__check_quorum()

        self.__log('Stop DataManager queue processing')

    def __fire_node_status_changed_event(self):
        self.__system_queue.put(self.__QUEUE_ITEM_NODE_STATUS_CHANGED)

    def __check_quorum(self):
        if not self.is_master():
            return

        with self.__lock:
            nodes_alive = 1 # master itself

            for secondary_name, secondary in self.__nodes.items():
                if not secondary.is_unhealthy():
                    nodes_alive += 1

            if nodes_alive < self.__quorum_size:
                if not self.__readonly:
                    self.__log('Node switched to read-only mode')
                self.__readonly = True
            else:
                if self.__readonly:
                    self.__log('Node switched to normal mode')
                self.__readonly = False

    def get_values(self) -> list[str]:
        """
        Returns all stored and committed items up to first uncommitted one
        """
        items = self.__storage.get_list()
        self.__log(f'get values request, returned items: {json.dumps(items)}')

        return items

    def get_heartbeat_status(self) -> str:
        """
        Returns dummy heartbeat status from server. Can be replaced with some "smart" value
        """

        return 'Alive'

    def __get_write_concern_or_raise_exception(self, write_concern: Optional[int] = None) -> int:
        write_concern_all = len(self.__nodes.items()) + 1

        if write_concern is None:
            write_concern = write_concern_all  # by default use WC=ALL

        if write_concern < 1 or write_concern > write_concern_all:
            msg = f'Write concern value {write_concern} is incorrect'
            self.__log(msg, level='error')
            raise Exception(msg)

        return write_concern

    def add_value(self, value: str, write_concern: Optional[int] = None) -> bool:
        """
        Add new value to the storage and replicate this across all secondaries
        Works only in Master mode
        """
        if not self.is_master():
            msg = 'Adding new values allowed only in Master mode'
            self.__log(msg, level='error')
            raise Exception(msg)

        if self.__readonly:
            raise DataManagerReadonlyModeException('Master is in read-only mode now')

        write_concern = self.__get_write_concern_or_raise_exception(write_concern)

        self.__log(f'adding value: {value} with WC = {write_concern}')

        key = self.__storage.add_value(value)
        self.__log(f'value `{value}`, key = {key} is stored ')

        # on this iteration consider that data will be successfully replicated
        self.__replicate_stored_value(key, write_concern)

        # commit the value on master when it was fully replicated
        self.__storage.commit_value(key)
        self.__log(f'committed value `{value}`, key = {key}, WC = {write_concern}')

        return True

    def set_value(self, key: int, value: str) -> bool:
        """
        Save and commit value into storage with provided key
        Returns False if value is already present in the storage and True in case of success
        Works only in Secondary mode
        """
        self.__log(f'storing value with key = {key}, value = {value}')

        if not self.is_secondary():
            msg = 'Setting values allowed only in Secondary mode'
            self.__log(msg, level='error')
            raise Exception(msg)

        stored = self.__storage.set_value(key, value)

        if stored:
            self.__log(f'value ({key} = {value}) successfully stored')
        else:
            self.__log(f'key `{key}` is already exist')

        return stored

    def set_app_name(self, name: str) -> None:
        self.__app_name = name

    def __log(self, message: str, level='info') -> None:
        log_message = f'{self.__app_name} - ' + message
        log_method = getattr(logger, level, 'info')
        log_method(log_message)

    def is_master(self) -> bool:
        return self.MODE_MASTER == self.__mode

    def is_secondary(self) -> bool:
        return self.MODE_SECONDARY == self.__mode

    def __replicate_stored_value(self, key: int, write_concern: int) -> None:
        value = self.__storage.get_value(key)

        if value is None:
            raise Exception("There is no value stored for key=" + str(key))

        data = {
            "key": key,
            "value": value
        }

        log_message = f'Replication for key=`{key}` with WR={write_concern}'

        if write_concern > 1:
            self.__log(log_message + ' started')
        else:
            self.__log(log_message + ' - sending requests')

        retry_timeout_intervals = (1, 2, 5, 10, 30, 60, 90, 180, 300)

        latch = CountDownLatch(write_concern - 1)

        for secondary_name, secondary in self.__nodes.items():
            thread = Thread(
                target=self.__send_data_to_secondary,
                args=(latch, secondary, data, retry_timeout_intervals, 0, log_message + f' ({secondary_name})')
            )
            thread.start()

        latch.wait()

        if write_concern > 1:
            self.__log(log_message + ' finished')
        else:
            self.__log(log_message + ' - requests are sent')

    def __send_data_to_secondary(self, latch: CountDownLatch, server: Server, data: dict,
                                 retry_timeout_intervals: tuple[int], max_iterations: int = 0,
                                 log_message: str = '') -> requests.Response:
        url = f'{server.get_dsn().rstrip("/")}/message'

        interval_index = 0
        iteration = 0

        def _get_timeout(index) -> tuple:
            interval = retry_timeout_intervals[index]

            if index < len(retry_timeout_intervals) - 1:
                index += 1

            return index, interval

        while True:
            if max_iterations > 0 and iteration >= max_iterations:
                self.__log(log_message + ': Cancel retry process due to max iteration attempts count reached')
                break

            is_unhealthy = server.is_unhealthy()

            if is_unhealthy:
                self.__log(log_message + f': replication paused due to server is in unhealthy status')

            server.wait_until_healthy()

            if is_unhealthy:
                self.__log(log_message + f': replication restored due to server is not unhealthy now')

            iteration += 1
            interval_index, timeout = _get_timeout(interval_index)

            try:
                response = requests.put(url, json=data, timeout=(timeout, timeout))
                self.__log(log_message + f': got response code =`{response.status_code}` url={url}', 'debug')

                if response.status_code == 204:
                    break
            except BaseException as err:
                self.__log(log_message + f': Exception: ' + type(err).__name__, 'debug')

            self.__log(log_message + f': set timeout =`{timeout}')

        latch.count_down()

        return response

    def __start_heartbeat(self) -> None:
        if self.is_secondary():
            return

        self.__log(f'Start heartbeats with interval {self.__heartbeat_interval}')

        for secondary_name, secondary in self.__nodes.items():
            thread = RepeatTimer(
                interval=self.__heartbeat_interval,
                function=self.__heartbeat_handler,
                args=(secondary_name, secondary, self.__heartbeat_interval)
            )
            thread.start()

            self.__heartbeat_threads.append(thread)

    def __stop_heartbeat(self):
        if self.is_secondary():
            return

        self.__log(f'Stop heartbeats')

        for thread in self.__heartbeat_threads:
            thread.cancel()

    def __heartbeat_handler(self, server_name: str, server: Server, timeout: int) -> None:
        url = f'{server.get_dsn().rstrip("/")}/heartbeat'

        is_node_status_changed = False

        try:
            response = requests.get(url, timeout=(timeout / 2, timeout / 2))
            self.__log(f'Heartbeat {server_name}: got response code =`{response.status_code}` url={url}', 'debug')

            if response.status_code == 200:
                is_node_status_changed = not server.is_healthy()
                server.mark_as_healthy()
        except BaseException as err:
            self.__log(f'Heartbeat {server_name}: Exception: ' + type(err).__name__, 'debug')
            is_node_status_changed = server.heartbeat_failed()
        finally:
            if is_node_status_changed:
                self.__fire_node_status_changed_event()
                self.__log(f'Heartbeat {server_name} status "{server.get_status()}"')


def get_data_manager_instance() -> DataManager:
    """Method to get DataManager instance initialized with settings"""

    mode = os.getenv('WORK_MODE', DataManager.MODE_MASTER)
    app_name = os.getenv('APP_NAME', mode)

    with open("config.yml", "r") as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    storage_object = storage.MemoryStorage()
    manager = DataManager(mode, storage_object, app_name, config)

    logger.debug(f'! get data manager instance {app_name}: {str(id(manager))} ({str(id(storage_object))})')

    return manager
