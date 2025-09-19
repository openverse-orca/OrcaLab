import inspect
from typing import List


def create_event_bus[T](interface: T) -> T:
    assert inspect.isclass(interface), "interface must be a class"

    # Singleton Proxy for interface
    class EventBusProxy:
        _instance = None
        handler_type = interface

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)

                # Add any initialization logic here if needed
                cls._instance.init()

            return cls._instance

        def init(self):
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
                        assert method is not None, f"{handler} has no method {name}"
                        method(*args, **kwargs)

                return invoke_wrapper

            elif name in self.async_methods:

                async def async_invoke_wrapper(*args, **kwargs):
                    for handler in self.handlers:
                        attr = getattr(handler, name, None)
                        assert attr is not None, f"{handler} has no method {name}"
                        await attr(*args, **kwargs)

                    return

                return async_invoke_wrapper
            else:
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{name}'"
                )

        def connect(self, handler):
            assert isinstance(handler, interface)
            self.handlers.append(handler)
            # print(f"Connected handler {handler}, total {len(self.handlers)}")

        def disconnect(self, handler):
            assert isinstance(handler, interface)
            self.handlers.remove(handler)
            # print(f"Disconnected handler {handler}, total {len(self.handlers)}")

    return EventBusProxy
