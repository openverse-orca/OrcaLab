import inspect
import asyncio
from PySide6 import QtCore, QtWidgets, QtGui


def connect(signal: QtCore.SignalInstance, func):

    assert isinstance(signal, QtCore.SignalInstance)

    if inspect.iscoroutinefunction(func):

        def wrapper(*args, **kwargs):
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_running_loop()
                # 使用create_task而不是ensure_future
                loop.create_task(func(*args, **kwargs))
            except RuntimeError:
                # 如果没有运行的事件循环，使用ensure_future
                asyncio.ensure_future(func(*args, **kwargs))

        signal.connect(wrapper)

    elif inspect.isfunction(func) or inspect.ismethod(func) or inspect.isbuiltin(func):
        signal.connect(func)
    else:
        raise Exception("Invalid function type.")
