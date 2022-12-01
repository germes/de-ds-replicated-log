from distributed_log import storage
from distributed_log.network import Server
from distributed_log.setup_logger import logger
from threading import Thread
from threading import Condition
from typing import Optional
import multiprocessing
import os
import json
import requests


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


class DataManager:
    """
    Responsible for all data processing, represents a thread-safe singleton and supports next features:
     - operating with provided storage - creating/saving/getting data from storage
     - can work both in Master and Secondary mode
     - contains information about secondaries and managing the replication process
    """
    MODE_MASTER = 'master'
    MODE_SECONDARY = 'secondary'

    __instance = None
    __lock = multiprocessing.Lock()
    __storage: storage.DataStorageInterface
    __mode: str
    __app_name: str
    __readonly: False  # todo: clarify when master should switch to read-only
    __nodes: dict[str, Server]

    def __new__(cls, mode: str, storage_object: storage.DataStorageInterface, app_name: str):
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

    def __init__(self, mode: str, storage_object: storage.DataStorageInterface, app_name: str):
        """
        :param mode: Master or Secondary
        :param storage_object: storage object that implements DataStorageInterface
        :param app_name: Application name - used for logging
        """
        if mode not in [self.MODE_MASTER, self.MODE_SECONDARY]:
            raise Exception("Unsupported mode " + mode)

        self.__mode = mode
        self.__storage = storage_object
        self.__app_name = app_name

        # todo: fill secondaries list from config
        if self.is_master():
            self.__nodes = {
                'secondary_1': Server("http://secondary1:8000/", Server.MODE_SECONDARY),
                'secondary_2': Server("http://secondary2:8000/", Server.MODE_SECONDARY)
            }

    def get_values(self) -> list[str]:
        """
        Returns all stored and committed items up to first uncommitted one
        """
        items = self.__storage.get_list()
        self.__log(f'get values request, returned items: {json.dumps(items)}')

        return items

    def __get_write_concern_or_raise_exception(self, write_concern: Optional[int] = None) -> int:
        write_concern_all = len(self.__nodes.items()) + 1

        if write_concern is None:
            write_concern = write_concern_all  # by default use WC=ALL

        if write_concern<1 or write_concern>write_concern_all:
            msg = f'Write concern value {write_concern} is incorrect'
            self.__log(msg, level='error')
            raise Exception(msg)

        return write_concern

    def add_value(self, value: str, write_concern: Optional[int] = None) -> bool:
        """
        Add new value to the storage and replicate this across all secondaries
        Works only in Master mode
        """
        write_concern = self.__get_write_concern_or_raise_exception(write_concern)

        self.__log(f'adding value: {value} with WC = {write_concern}')

        if not self.is_master():
            msg = 'Adding new values allowed only in Master mode'
            self.__log(msg, level='error')
            raise Exception(msg)

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

        if write_concern > 1:
            self.__log(f'Replication for key=`{key}` with WR={write_concern} started')
        else:
            self.__log(f'Sending replication requests for key=`{key}` with WR={write_concern}')

        latch = CountDownLatch(write_concern - 1)

        for secondary_name, secondary in self.__nodes.items():
            thread = Thread(target=self.__send_data_to_secondary, args=(latch, secondary, data))
            thread.start()

        latch.wait()

        if write_concern > 1:
            self.__log(f'Replication for key=`{key}` with WR={write_concern} finished')
        else:
            self.__log(f'Replication requests for key=`{key}` with WR={write_concern} are sent')

    def __send_data_to_secondary(self, latch: CountDownLatch, server: Server, data: dict) -> requests.Response:
        url = f'{server.get_dsn().rstrip("/")}/message'
        # in the current version, it supposes that all requests to secondary are success
        response = requests.put(url, json=data)

        latch.count_down()

        return response


def get_data_manager_instance() -> DataManager:
    """Method to get DataManager instance initialized with settings"""

    mode = os.getenv('WORK_MODE', DataManager.MODE_MASTER)
    app_name = os.getenv('APP_NAME', mode)

    storage_object = storage.MemoryStorage()
    manager = DataManager(mode, storage_object, app_name)

    logger.debug(f'! get data manager instance {app_name}: {str(id(manager))} ({str(id(storage_object))})')

    return manager
