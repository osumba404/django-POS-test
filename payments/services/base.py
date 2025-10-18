from abc import ABC, abstractmethod

class PaymentProvider(ABC):
    @abstractmethod
    def initiate(self, **kwargs):
        raise NotImplementedError
