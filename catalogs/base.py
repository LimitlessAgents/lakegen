from abc import ABC, abstractmethod

class BaseCatalog(ABC):

    @abstractmethod
    def list_databases(self):
        pass
    
    @abstractmethod
    def list_tables(self):
        pass

    @abstractmethod
    def load_table(self):
        pass