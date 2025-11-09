import inspect
from typing import List, Type


class EventBusProxy[T]:
    """
    For type hinting only.
    """

    def __init__(self):
        raise NotImplementedError("Use create_event_bus to create an EventBus")

    def connect(self, handler: T):
        pass

    def disconnect(self, handler: T):
        pass

    def __call__(self) -> T:
        pass


# EventBus设计上允许多个Handler，接口的返回值会被忽略，返回None。
# 解决方法是把一个list作为参数传入， 结果收集到list里。
def create_event_bus[T](interface: Type[T]) -> EventBusProxy[T]:
    if not inspect.isclass(interface):
        raise TypeError("interface must be a class")

    # Singleton Proxy for interface
    class _EventBusProxy:
        _instance = None
        handler_type = interface

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)

                # Add any initialization logic here if needed
                cls._instance._init()

            return cls._instance

        def _init(self):
            self.handlers = []
            self.methods: List[str] = []
            self.async_methods: List[str] = []

            for name, _ in inspect.getmembers(interface, predicate=inspect.isfunction):
                self.methods.append(name)

            for name, _ in inspect.getmembers(
                interface, predicate=inspect.iscoroutinefunction
            ):
                self.methods.remove(name)
                self.async_methods.append(name)

        def __getattr__(self, name):

            if name in self.methods:

                def invoke_wrapper(*args, **kwargs):
                    for handler in self.handlers:
                        method = getattr(handler, name, None)
                        if method is None:
                            raise AttributeError(f"{handler} has no method {name}")
                        method(*args, **kwargs)

                return invoke_wrapper

            elif name in self.async_methods:

                async def async_invoke_wrapper(*args, **kwargs):
                    for handler in self.handlers:
                        method = getattr(handler, name, None)
                        if method is None:
                            raise AttributeError(f"{handler} has no method {name}")
                        await method(*args, **kwargs)

                return async_invoke_wrapper
            else:
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{name}'"
                )

        def _connect(self, handler):
            if not isinstance(handler, interface):
                raise TypeError(f"handler must be an instance of {interface}")
            self.handlers.append(handler)
            # print(f"Connected handler {handler}, total {len(self.handlers)}")

        def _disconnect(self, handler):
            if not isinstance(handler, interface):
                raise TypeError(f"handler must be an instance of {interface}")
            if handler in self.handlers:
                self.handlers.remove(handler)
            # print(f"Disconnected handler {handler}, total {len(self.handlers)}")

        @classmethod
        def connect(cls, handler: T):
            _EventBusProxy()._connect(handler)

        @classmethod
        def disconnect(cls, handler: T):
            _EventBusProxy()._disconnect(handler)

    return _EventBusProxy
