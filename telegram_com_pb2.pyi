from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class MessageRequest(_message.Message):
    __slots__ = ("message", "edit_id")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EDIT_ID_FIELD_NUMBER: _ClassVar[int]
    message: str
    edit_id: int
    def __init__(self, message: _Optional[str] = ..., edit_id: _Optional[int] = ...) -> None: ...

class MessageID(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: int
    def __init__(self, message_id: _Optional[int] = ...) -> None: ...
