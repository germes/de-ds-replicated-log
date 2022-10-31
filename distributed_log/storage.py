import multiprocessing
from sortedcontainers import SortedSet


class DataStorageInterface:
    """Data Storage Interface for Replicated Log"""

    def add_value(self, value: str, commit=False) -> int:
        pass

    def set_value(self, key: int, value: str, commit=True, override=False) -> bool:
        """
        Save value to storage with provided index.
        In case if provided key is already present in storage method will return False,
        otherwise store data and return True.
        """
        pass

    def get_value(self, key: int) -> str:
        pass

    def commit_value(self, key: int) -> bool:
        """
        Marks value in storage as committed using provided key.
        """
        pass

    def rollback_value(self, key: int) -> bool:
        """
        Marks value in storage as rolled back using provided key.
        Returns False if provided key is not exist in storage
        """
        pass

    def get_list(self) -> list[str]:
        """Returns list of stored values"""
        pass


class MemoryStorage(DataStorageInterface):
    """
    Simple memory storage that represents a thread-safe singleton and supports next features:
     - thread-safe indexing of data in storage to avoid overriding data in case of multiple connections
     - a simple mechanism to commit and rollback changes
     - several modes to get the list of stored values
     - returns list of values sorted by index
    """
    LIST_MODE_ALL = 'LIST_ALL'
    LIST_MODE_ALL_COMMITTED = 'LIST_COMMITTED'
    LIST_MODE_CONSISTENT_ORDER = 'LIST_CONSISTENT_ORDER'

    __instance = None
    __lock = multiprocessing.Lock()
    __data = {}
    __index = 0
    __index_pool = SortedSet()
    __mode = LIST_MODE_CONSISTENT_ORDER

    def __new__(cls):
        if not cls.__instance:
            with cls.__lock:
                if not cls.__instance:
                    cls.__instance = super(MemoryStorage, cls).__new__(cls)
        return cls.__instance

    def add_value(self, value: str, commit=False) -> int:
        item = self.__DataItem(value)

        if commit:
            item.commit()

        with self.__lock:
            index = self.__index + 1
            self.__data[index] = item
            self.__index_pool.add(index)
            self.__index = index

        return index

    def set_value(self, key: int, value: str, commit=True, override=False) -> bool:
        """
        Save value to storage with provided index.
        In case if provided key is already present in storage method will return False,
        otherwise store data and return True.
        Does not override values by default
        """
        if key in self.__data and not override:
            return False

        item = self.__DataItem(value)

        if commit:
            item.commit()

        with self.__lock:
            self.__data[key] = item
            self.__index_pool.add(key)
            self.__index = max(self.__index, key)

        return True

    def commit_value(self, key: int) -> bool:
        """
        Marks value in storage as committed using provided key.
        Returns False if provided key is not exist in storage
        """
        if key not in self.__data:
            return False

        with self.__lock:
            self.__data[key].commit()

    def rollback_value(self, key: int) -> bool:
        """
        Marks value in storage as rolled back using provided key.
        Returns False if provided key is not exist in storage
        """
        if key not in self.__data:
            return False

        with self.__lock:
            self.__data[key].rollback()

    def get_list(self) -> list[str]:
        """
        Returns list of stored values ordered by key based on the set LIST_MODE:
         - LIST_MODE_ALL - all values regardless are they committed or not
         - LIST_MODE_CONSISTENT_ORDER - all committed values up to the first not committed value or gap in indexes
         - LIST_MODE_ALL_COMMITTED - all committed values
        """
        values = []

        with self.__lock:
            previous_index = None

            for index in self.__index_pool:
                distance = index - (previous_index if previous_index is not None else index)
                previous_index = index
                item = self.__data.get(index)

                if self.__mode == self.LIST_MODE_CONSISTENT_ORDER and (item.is_added() or distance > 1):
                    break
                elif self.__mode == self.LIST_MODE_ALL_COMMITTED and (not item.is_committed()):
                    continue

                if item.is_committed() or self.__mode == self.LIST_MODE_ALL:
                    values.append(item.get_value())

        return values

    def get_value(self, key: int) -> str:
        return self.__data[key].get_value() if key in self.__data else None

    def set_getting_list_mode(self, mode: str) -> None:
        if mode not in [self.LIST_MODE_ALL_COMMITTED, self.LIST_MODE_CONSISTENT_ORDER]:
            raise Exception("Unsupported mode " + mode)

        self.__mode = mode

    def get_count(self) -> int:
        return len(self.__index_pool)

    class __DataItem:
        """
        The service class for MemoryStorage represents a simple data object with value and status
        """
        __STATUS_ADDED = 0
        __STATUS_COMMITTED = 1
        __STATUS_ROLLED_BACK = 2

        __value: str
        __status: int

        def __init__(self, value: str) -> object:
            self.__value = value
            self.__status = self.__STATUS_ADDED

        def get_value(self) -> str:
            return self.__value

        def commit(self) -> None:
            self.__status = self.__STATUS_COMMITTED

        def rollback(self) -> None:
            self.__status = self.__STATUS_ROLLED_BACK

        def is_added(self) -> bool:
            return self.__STATUS_ADDED == self.__status

        def is_committed(self) -> bool:
            return self.__STATUS_COMMITTED == self.__status

        def is_rolled_back(self) -> bool:
            return self.__STATUS_ROLLED_BACK == self.__status
