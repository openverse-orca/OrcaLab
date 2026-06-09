from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Success: _ClassVar[StatusCode]
    Error: _ClassVar[StatusCode]
Success: StatusCode
Error: StatusCode

class ProcessUrlRequest(_message.Message):
    __slots__ = ("url",)
    URL_FIELD_NUMBER: _ClassVar[int]
    url: str
    def __init__(self, url: _Optional[str] = ...) -> None: ...

class ProcessUrlResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...
