from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Success: _ClassVar[StatusCode]
    Error: _ClassVar[StatusCode]

class Space(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Local: _ClassVar[Space]
    World: _ClassVar[Space]

class PropertyType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Unknown: _ClassVar[PropertyType]
    Bool: _ClassVar[PropertyType]
    Int: _ClassVar[PropertyType]
    Float: _ClassVar[PropertyType]
    String: _ClassVar[PropertyType]
    ENUM: _ClassVar[PropertyType]
    ASSET: _ClassVar[PropertyType]
Success: StatusCode
Error: StatusCode
Local: Space
World: Space
Unknown: PropertyType
Bool: PropertyType
Int: PropertyType
Float: PropertyType
String: PropertyType
ENUM: PropertyType
ASSET: PropertyType

class Transform(_message.Message):
    __slots__ = ("pos", "quat", "scale")
    POS_FIELD_NUMBER: _ClassVar[int]
    QUAT_FIELD_NUMBER: _ClassVar[int]
    SCALE_FIELD_NUMBER: _ClassVar[int]
    pos: _containers.RepeatedScalarFieldContainer[float]
    quat: _containers.RepeatedScalarFieldContainer[float]
    scale: float
    def __init__(self, pos: _Optional[_Iterable[float]] = ..., quat: _Optional[_Iterable[float]] = ..., scale: _Optional[float] = ...) -> None: ...

class AlohaRequest(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class AlohaResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "value")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    value: int
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...

class AddGroupRequest(_message.Message):
    __slots__ = ("actor_name", "parent_actor_path", "transform", "space")
    ACTOR_NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    SPACE_FIELD_NUMBER: _ClassVar[int]
    actor_name: str
    parent_actor_path: str
    transform: Transform
    space: Space
    def __init__(self, actor_name: _Optional[str] = ..., parent_actor_path: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ..., space: _Optional[_Union[Space, str]] = ...) -> None: ...

class AddAssetActorRequest(_message.Message):
    __slots__ = ("spawnable_name", "actor_name", "parent_actor_path", "transform", "space")
    SPAWNABLE_NAME_FIELD_NUMBER: _ClassVar[int]
    ACTOR_NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    SPACE_FIELD_NUMBER: _ClassVar[int]
    spawnable_name: str
    actor_name: str
    parent_actor_path: str
    transform: Transform
    space: Space
    def __init__(self, spawnable_name: _Optional[str] = ..., actor_name: _Optional[str] = ..., parent_actor_path: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ..., space: _Optional[_Union[Space, str]] = ...) -> None: ...

class AddActorRequestUnion(_message.Message):
    __slots__ = ("asset_actor", "group_actor")
    ASSET_ACTOR_FIELD_NUMBER: _ClassVar[int]
    GROUP_ACTOR_FIELD_NUMBER: _ClassVar[int]
    asset_actor: AddAssetActorRequest
    group_actor: AddGroupRequest
    def __init__(self, asset_actor: _Optional[_Union[AddAssetActorRequest, _Mapping]] = ..., group_actor: _Optional[_Union[AddGroupRequest, _Mapping]] = ...) -> None: ...

class AddActorBatchRequest(_message.Message):
    __slots__ = ("requests", "stop_on_error")
    REQUESTS_FIELD_NUMBER: _ClassVar[int]
    STOP_ON_ERROR_FIELD_NUMBER: _ClassVar[int]
    requests: _containers.RepeatedCompositeFieldContainer[AddActorRequestUnion]
    stop_on_error: bool
    def __init__(self, requests: _Optional[_Iterable[_Union[AddActorRequestUnion, _Mapping]]] = ..., stop_on_error: bool = ...) -> None: ...

class AddActorBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "errors")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class DeleteActorBatchRequest(_message.Message):
    __slots__ = ("actor_paths",)
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class DeleteActorBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "errors")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class SetActorTransformRequest(_message.Message):
    __slots__ = ("actor_path", "transform", "space")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    SPACE_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    transform: Transform
    space: Space
    def __init__(self, actor_path: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ..., space: _Optional[_Union[Space, str]] = ...) -> None: ...

class SetActorTransformResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class SetActorTransformBatchRequest(_message.Message):
    __slots__ = ("actor_paths", "transforms")
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    TRANSFORMS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    transforms: _containers.RepeatedCompositeFieldContainer[Transform]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ..., transforms: _Optional[_Iterable[_Union[Transform, _Mapping]]] = ...) -> None: ...

class SetActorTransformBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetPendingOperationsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetPendingOperationsResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "operations")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    OPERATIONS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    operations: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., operations: _Optional[_Iterable[str]] = ...) -> None: ...

class GetPendingActorTransformRequest(_message.Message):
    __slots__ = ("status_code", "error_message", "actor_path", "space")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    SPACE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    actor_path: str
    space: Space
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., actor_path: _Optional[str] = ..., space: _Optional[_Union[Space, str]] = ...) -> None: ...

class GetPendingActorTransformResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transform")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transform: Transform
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ...) -> None: ...

class GetPendingActorTransformBatchRequest(_message.Message):
    __slots__ = ("actor_paths",)
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class GetPendingActorTransformBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transforms")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORMS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transforms: _containers.RepeatedCompositeFieldContainer[Transform]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transforms: _Optional[_Iterable[_Union[Transform, _Mapping]]] = ...) -> None: ...

class ClearSceneRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClearSceneResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetActorAssetsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetActorAssetsResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "actor_asset_names")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_ASSET_NAMES_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    actor_asset_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., actor_asset_names: _Optional[_Iterable[str]] = ...) -> None: ...

class GetPendingAddItemRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetPendingAddItemResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transform", "actor_name")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    ACTOR_NAME_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transform: Transform
    actor_name: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ..., actor_name: _Optional[str] = ...) -> None: ...

class SelectionData(_message.Message):
    __slots__ = ("selected_actor_paths", "active_actor_path", "active_entity_id")
    SELECTED_ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    selected_actor_paths: _containers.RepeatedScalarFieldContainer[str]
    active_actor_path: str
    active_entity_id: int
    def __init__(self, selected_actor_paths: _Optional[_Iterable[str]] = ..., active_actor_path: _Optional[str] = ..., active_entity_id: _Optional[int] = ...) -> None: ...

class GetPendingSelectionChangeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetPendingSelectionChangeResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "selection")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SELECTION_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    selection: SelectionData
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., selection: _Optional[_Union[SelectionData, _Mapping]] = ...) -> None: ...

class SetSelectionRequest(_message.Message):
    __slots__ = ("selection",)
    SELECTION_FIELD_NUMBER: _ClassVar[int]
    selection: SelectionData
    def __init__(self, selection: _Optional[_Union[SelectionData, _Mapping]] = ...) -> None: ...

class SetSelectionResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class SaveStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SaveStateResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class RestoreStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestoreStateResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class DeleteActorRequest(_message.Message):
    __slots__ = ("actor_path",)
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    def __init__(self, actor_path: _Optional[str] = ...) -> None: ...

class DeleteActorResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class RenameActorRequest(_message.Message):
    __slots__ = ("actor_path", "new_name")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    NEW_NAME_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    new_name: str
    def __init__(self, actor_path: _Optional[str] = ..., new_name: _Optional[str] = ...) -> None: ...

class RenameActorResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class MoveActorBatchRequest(_message.Message):
    __slots__ = ("actor_paths", "new_parent_paths")
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    NEW_PARENT_PATHS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    new_parent_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ..., new_parent_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class MoveActorBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetWindowIdRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetWindowIdResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "window_id")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    WINDOW_ID_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    window_id: int
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., window_id: _Optional[int] = ...) -> None: ...

class GetGeneratePosRequest(_message.Message):
    __slots__ = ("posX", "posY")
    POSX_FIELD_NUMBER: _ClassVar[int]
    POSY_FIELD_NUMBER: _ClassVar[int]
    posX: float
    posY: float
    def __init__(self, posX: _Optional[float] = ..., posY: _Optional[float] = ...) -> None: ...

class GetGeneratePosResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transform")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transform: Transform
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ...) -> None: ...

class GetCacheFolderRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCacheFolderResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "cache_folder")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CACHE_FOLDER_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    cache_folder: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., cache_folder: _Optional[str] = ...) -> None: ...

class ChangeManipulatorTypeRequest(_message.Message):
    __slots__ = ("manipulator_type",)
    MANIPULATOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    manipulator_type: int
    def __init__(self, manipulator_type: _Optional[int] = ...) -> None: ...

class ChangeManipulatorTypeResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetCameraPNGRequest(_message.Message):
    __slots__ = ("camera_name", "png_path", "png_name")
    CAMERA_NAME_FIELD_NUMBER: _ClassVar[int]
    PNG_PATH_FIELD_NUMBER: _ClassVar[int]
    PNG_NAME_FIELD_NUMBER: _ClassVar[int]
    camera_name: str
    png_path: str
    png_name: str
    def __init__(self, camera_name: _Optional[str] = ..., png_path: _Optional[str] = ..., png_name: _Optional[str] = ...) -> None: ...

class GetCameraPNGResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class LoadPackageRequest(_message.Message):
    __slots__ = ("file_path",)
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    file_path: str
    def __init__(self, file_path: _Optional[str] = ...) -> None: ...

class LoadPackageResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class ChangeSimStateRequest(_message.Message):
    __slots__ = ("sim_process_running",)
    SIM_PROCESS_RUNNING_FIELD_NUMBER: _ClassVar[int]
    sim_process_running: bool
    def __init__(self, sim_process_running: bool = ...) -> None: ...

class ChangeSimStateResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetSyncFromMujocoToSceneRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSyncFromMujocoToSceneResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "value")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    value: bool
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., value: bool = ...) -> None: ...

class SetSyncFromMujocoToSceneRequest(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: bool
    def __init__(self, value: bool = ...) -> None: ...

class SetSyncFromMujocoToSceneResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class PublishSceneRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PublishSceneResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetActorAssetAabbRequest(_message.Message):
    __slots__ = ("actor_path",)
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    def __init__(self, actor_path: _Optional[str] = ...) -> None: ...

class GetActorAssetAabbResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "min", "max")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    min: _containers.RepeatedScalarFieldContainer[float]
    max: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., min: _Optional[_Iterable[float]] = ..., max: _Optional[_Iterable[float]] = ...) -> None: ...

class FindNonOverlappingPositionRequest(_message.Message):
    __slots__ = ("actor_path",)
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    def __init__(self, actor_path: _Optional[str] = ...) -> None: ...

class FindNonOverlappingPositionResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "position")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    position: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., position: _Optional[_Iterable[float]] = ...) -> None: ...

class QueueMouseEventRequest(_message.Message):
    __slots__ = ("button", "action", "x", "y")
    BUTTON_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    button: int
    action: int
    x: float
    y: float
    def __init__(self, button: _Optional[int] = ..., action: _Optional[int] = ..., x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...

class QueueMouseEventResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class QueueMouseWheelEventRequest(_message.Message):
    __slots__ = ("delta",)
    DELTA_FIELD_NUMBER: _ClassVar[int]
    delta: int
    def __init__(self, delta: _Optional[int] = ...) -> None: ...

class QueueMouseWheelEventResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class QueueKeyEventRequest(_message.Message):
    __slots__ = ("key", "action")
    KEY_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    key: int
    action: int
    def __init__(self, key: _Optional[int] = ..., action: _Optional[int] = ...) -> None: ...

class QueueKeyEventResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class CameraBrief(_message.Message):
    __slots__ = ("name", "index", "source", "actor_path")
    NAME_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    name: str
    index: int
    source: str
    actor_path: str
    def __init__(self, name: _Optional[str] = ..., index: _Optional[int] = ..., source: _Optional[str] = ..., actor_path: _Optional[str] = ...) -> None: ...

class GetCamerasRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCamerasResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "cameras")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CAMERAS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    cameras: _containers.RepeatedCompositeFieldContainer[CameraBrief]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., cameras: _Optional[_Iterable[_Union[CameraBrief, _Mapping]]] = ...) -> None: ...

class GetActiveCameraRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetActiveCameraResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "index")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    index: int
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., index: _Optional[int] = ...) -> None: ...

class SetActiveCameraRequest(_message.Message):
    __slots__ = ("index",)
    INDEX_FIELD_NUMBER: _ClassVar[int]
    index: int
    def __init__(self, index: _Optional[int] = ...) -> None: ...

class SetActiveCameraResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetFlyCameraTransformRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetFlyCameraTransformResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "flycamera_transform")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FLYCAMERA_TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    flycamera_transform: Transform
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., flycamera_transform: _Optional[_Union[Transform, _Mapping]] = ...) -> None: ...

class SetFlyCameraTransformRequest(_message.Message):
    __slots__ = ("flycamera_transform",)
    FLYCAMERA_TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    flycamera_transform: Transform
    def __init__(self, flycamera_transform: _Optional[_Union[Transform, _Mapping]] = ...) -> None: ...

class SetFlyCameraTransformResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetViewportCameraTransformRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetViewportCameraTransformResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transform")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transform: Transform
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ...) -> None: ...

class GetCameraDataPNGRequest(_message.Message):
    __slots__ = ("camera_name", "png_path", "index")
    CAMERA_NAME_FIELD_NUMBER: _ClassVar[int]
    PNG_PATH_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    camera_name: str
    png_path: str
    index: int
    def __init__(self, camera_name: _Optional[str] = ..., png_path: _Optional[str] = ..., index: _Optional[int] = ...) -> None: ...

class GetCameraDataPNGResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "transform", "has_color", "has_depth", "has_normal", "has_object_color")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    HAS_COLOR_FIELD_NUMBER: _ClassVar[int]
    HAS_DEPTH_FIELD_NUMBER: _ClassVar[int]
    HAS_NORMAL_FIELD_NUMBER: _ClassVar[int]
    HAS_OBJECT_COLOR_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    transform: Transform
    has_color: bool
    has_depth: bool
    has_normal: bool
    has_object_color: bool
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., transform: _Optional[_Union[Transform, _Mapping]] = ..., has_color: bool = ..., has_depth: bool = ..., has_normal: bool = ..., has_object_color: bool = ...) -> None: ...

class PropertyValue(_message.Message):
    __slots__ = ("value_bool", "value_int", "value_float", "value_string", "value_asset")
    VALUE_BOOL_FIELD_NUMBER: _ClassVar[int]
    VALUE_INT_FIELD_NUMBER: _ClassVar[int]
    VALUE_FLOAT_FIELD_NUMBER: _ClassVar[int]
    VALUE_STRING_FIELD_NUMBER: _ClassVar[int]
    VALUE_ASSET_FIELD_NUMBER: _ClassVar[int]
    value_bool: bool
    value_int: int
    value_float: float
    value_string: str
    value_asset: str
    def __init__(self, value_bool: bool = ..., value_int: _Optional[int] = ..., value_float: _Optional[float] = ..., value_string: _Optional[str] = ..., value_asset: _Optional[str] = ...) -> None: ...

class PropertyValueList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[PropertyValue]
    def __init__(self, items: _Optional[_Iterable[_Union[PropertyValue, _Mapping]]] = ...) -> None: ...

class AssetInfo(_message.Message):
    __slots__ = ("asset_id", "relative_path")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_PATH_FIELD_NUMBER: _ClassVar[int]
    asset_id: str
    relative_path: str
    def __init__(self, asset_id: _Optional[str] = ..., relative_path: _Optional[str] = ...) -> None: ...

class GetAssetsByTypePageRequest(_message.Message):
    __slots__ = ("asset_type_uuid", "page_index", "page_size")
    ASSET_TYPE_UUID_FIELD_NUMBER: _ClassVar[int]
    PAGE_INDEX_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    asset_type_uuid: str
    page_index: int
    page_size: int
    def __init__(self, asset_type_uuid: _Optional[str] = ..., page_index: _Optional[int] = ..., page_size: _Optional[int] = ...) -> None: ...

class GetAssetsByTypePageResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "page_index", "total_pages", "total_count", "assets")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_INDEX_FIELD_NUMBER: _ClassVar[int]
    TOTAL_PAGES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    page_index: int
    total_pages: int
    total_count: int
    assets: _containers.RepeatedCompositeFieldContainer[AssetInfo]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., page_index: _Optional[int] = ..., total_pages: _Optional[int] = ..., total_count: _Optional[int] = ..., assets: _Optional[_Iterable[_Union[AssetInfo, _Mapping]]] = ...) -> None: ...

class Property(_message.Message):
    __slots__ = ("type", "name", "display_name", "read_only", "editor_hint", "enum_values", "post_read_fields", "post_read_delay_ms")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    EDITOR_HINT_FIELD_NUMBER: _ClassVar[int]
    ENUM_VALUES_FIELD_NUMBER: _ClassVar[int]
    POST_READ_FIELDS_FIELD_NUMBER: _ClassVar[int]
    POST_READ_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    type: PropertyType
    name: str
    display_name: str
    read_only: bool
    editor_hint: str
    enum_values: _containers.RepeatedScalarFieldContainer[str]
    post_read_fields: _containers.RepeatedScalarFieldContainer[str]
    post_read_delay_ms: int
    def __init__(self, type: _Optional[_Union[PropertyType, str]] = ..., name: _Optional[str] = ..., display_name: _Optional[str] = ..., read_only: bool = ..., editor_hint: _Optional[str] = ..., enum_values: _Optional[_Iterable[str]] = ..., post_read_fields: _Optional[_Iterable[str]] = ..., post_read_delay_ms: _Optional[int] = ...) -> None: ...

class PropertyGroup(_message.Message):
    __slots__ = ("prefix", "name", "display_name", "hint", "properties", "entity_id", "component_type_id")
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    HINT_FIELD_NUMBER: _ClassVar[int]
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    prefix: str
    name: str
    display_name: str
    hint: str
    properties: _containers.RepeatedCompositeFieldContainer[Property]
    entity_id: int
    component_type_id: str
    def __init__(self, prefix: _Optional[str] = ..., name: _Optional[str] = ..., display_name: _Optional[str] = ..., hint: _Optional[str] = ..., properties: _Optional[_Iterable[_Union[Property, _Mapping]]] = ..., entity_id: _Optional[int] = ..., component_type_id: _Optional[str] = ...) -> None: ...

class PropertyKey(_message.Message):
    __slots__ = ("actor_path", "entity_id", "component_type", "field_path", "property_type")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_TYPE_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    entity_id: int
    component_type: str
    field_path: str
    property_type: PropertyType
    def __init__(self, actor_path: _Optional[str] = ..., entity_id: _Optional[int] = ..., component_type: _Optional[str] = ..., field_path: _Optional[str] = ..., property_type: _Optional[_Union[PropertyType, str]] = ...) -> None: ...

class PropertyKeyList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[PropertyKey]
    def __init__(self, items: _Optional[_Iterable[_Union[PropertyKey, _Mapping]]] = ...) -> None: ...

class GetPropertyGroupsRequest(_message.Message):
    __slots__ = ("actor_path",)
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    def __init__(self, actor_path: _Optional[str] = ...) -> None: ...

class GetPropertyGroupsResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "property_groups")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_GROUPS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    property_groups: _containers.RepeatedCompositeFieldContainer[PropertyGroup]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., property_groups: _Optional[_Iterable[_Union[PropertyGroup, _Mapping]]] = ...) -> None: ...

class GetPropertiesRequest(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: PropertyKeyList
    def __init__(self, keys: _Optional[_Union[PropertyKeyList, _Mapping]] = ...) -> None: ...

class GetPropertiesResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "values")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    values: PropertyValueList
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., values: _Optional[_Union[PropertyValueList, _Mapping]] = ...) -> None: ...

class SetPropertiesRequest(_message.Message):
    __slots__ = ("keys", "values")
    KEYS_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    keys: PropertyKeyList
    values: PropertyValueList
    def __init__(self, keys: _Optional[_Union[PropertyKeyList, _Mapping]] = ..., values: _Optional[_Union[PropertyValueList, _Mapping]] = ...) -> None: ...

class SetPropertiesResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class PropertyGroupList(_message.Message):
    __slots__ = ("elements",)
    ELEMENTS_FIELD_NUMBER: _ClassVar[int]
    elements: _containers.RepeatedCompositeFieldContainer[PropertyGroup]
    def __init__(self, elements: _Optional[_Iterable[_Union[PropertyGroup, _Mapping]]] = ...) -> None: ...

class GetPropertyGroupsBatchRequest(_message.Message):
    __slots__ = ("actor_paths",)
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class GetPropertyGroupsBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "property_group_lists")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_GROUP_LISTS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    property_group_lists: _containers.RepeatedCompositeFieldContainer[PropertyGroupList]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., property_group_lists: _Optional[_Iterable[_Union[PropertyGroupList, _Mapping]]] = ...) -> None: ...

class EntityInfoMessage(_message.Message):
    __slots__ = ("entity_id", "name", "entity_path", "children")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ENTITY_PATH_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    entity_id: int
    name: str
    entity_path: str
    children: _containers.RepeatedCompositeFieldContainer[EntityInfoMessage]
    def __init__(self, entity_id: _Optional[int] = ..., name: _Optional[str] = ..., entity_path: _Optional[str] = ..., children: _Optional[_Iterable[_Union[EntityInfoMessage, _Mapping]]] = ...) -> None: ...

class GetEntityHierarchyBatchRequest(_message.Message):
    __slots__ = ("actor_paths",)
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class GetEntityHierarchyBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "root_entities", "errors")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ROOT_ENTITIES_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    root_entities: _containers.RepeatedCompositeFieldContainer[EntityInfoMessage]
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., root_entities: _Optional[_Iterable[_Union[EntityInfoMessage, _Mapping]]] = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class GetEntityPropertyGroupsRequest(_message.Message):
    __slots__ = ("actor_path", "entity_id")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    entity_id: int
    def __init__(self, actor_path: _Optional[str] = ..., entity_id: _Optional[int] = ...) -> None: ...

class GetEntityPropertyGroupsResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "property_groups")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_GROUPS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    property_groups: _containers.RepeatedCompositeFieldContainer[PropertyGroup]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., property_groups: _Optional[_Iterable[_Union[PropertyGroup, _Mapping]]] = ...) -> None: ...

class GetEntityPropertyGroupsBatchRequest(_message.Message):
    __slots__ = ("actor_path", "entity_ids")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ENTITY_IDS_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    entity_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, actor_path: _Optional[str] = ..., entity_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class GetEntityPropertyGroupsBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "property_group_lists")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_GROUP_LISTS_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    property_group_lists: _containers.RepeatedCompositeFieldContainer[PropertyGroupList]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., property_group_lists: _Optional[_Iterable[_Union[PropertyGroupList, _Mapping]]] = ...) -> None: ...

class EntityPropertyGroupEntry(_message.Message):
    __slots__ = ("entity_id", "entity_path", "component_type", "component_display_name", "property_group")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_PATH_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    PROPERTY_GROUP_FIELD_NUMBER: _ClassVar[int]
    entity_id: int
    entity_path: str
    component_type: str
    component_display_name: str
    property_group: PropertyGroup
    def __init__(self, entity_id: _Optional[int] = ..., entity_path: _Optional[str] = ..., component_type: _Optional[str] = ..., component_display_name: _Optional[str] = ..., property_group: _Optional[_Union[PropertyGroup, _Mapping]] = ...) -> None: ...

class GetAllEntityPropertyGroupsRequest(_message.Message):
    __slots__ = ("actor_path",)
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    def __init__(self, actor_path: _Optional[str] = ...) -> None: ...

class GetAllEntityPropertyGroupsResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "entries")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    entries: _containers.RepeatedCompositeFieldContainer[EntityPropertyGroupEntry]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., entries: _Optional[_Iterable[_Union[EntityPropertyGroupEntry, _Mapping]]] = ...) -> None: ...

class FieldValue(_message.Message):
    __slots__ = ("field_path", "type", "value", "read_only", "display_name", "enum_values")
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ENUM_VALUES_FIELD_NUMBER: _ClassVar[int]
    field_path: str
    type: PropertyType
    value: PropertyValue
    read_only: bool
    display_name: str
    enum_values: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, field_path: _Optional[str] = ..., type: _Optional[_Union[PropertyType, str]] = ..., value: _Optional[_Union[PropertyValue, _Mapping]] = ..., read_only: bool = ..., display_name: _Optional[str] = ..., enum_values: _Optional[_Iterable[str]] = ...) -> None: ...

class ComponentFieldValues(_message.Message):
    __slots__ = ("component_type", "component_display_name", "fields")
    COMPONENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    component_type: str
    component_display_name: str
    fields: _containers.RepeatedCompositeFieldContainer[FieldValue]
    def __init__(self, component_type: _Optional[str] = ..., component_display_name: _Optional[str] = ..., fields: _Optional[_Iterable[_Union[FieldValue, _Mapping]]] = ...) -> None: ...

class EntityFieldValues(_message.Message):
    __slots__ = ("entity_id", "components")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    COMPONENTS_FIELD_NUMBER: _ClassVar[int]
    entity_id: int
    components: _containers.RepeatedCompositeFieldContainer[ComponentFieldValues]
    def __init__(self, entity_id: _Optional[int] = ..., components: _Optional[_Iterable[_Union[ComponentFieldValues, _Mapping]]] = ...) -> None: ...

class EntityFieldWrite(_message.Message):
    __slots__ = ("entity_id", "component_type", "field_path", "value")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    entity_id: int
    component_type: str
    field_path: str
    value: PropertyValue
    def __init__(self, entity_id: _Optional[int] = ..., component_type: _Optional[str] = ..., field_path: _Optional[str] = ..., value: _Optional[_Union[PropertyValue, _Mapping]] = ...) -> None: ...

class GetEntityAllFieldValuesRequest(_message.Message):
    __slots__ = ("actor_path", "entity_id")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    entity_id: int
    def __init__(self, actor_path: _Optional[str] = ..., entity_id: _Optional[int] = ...) -> None: ...

class GetEntityAllFieldValuesResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "entity_values")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENTITY_VALUES_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    entity_values: EntityFieldValues
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., entity_values: _Optional[_Union[EntityFieldValues, _Mapping]] = ...) -> None: ...

class SetEntityFieldValuesRequest(_message.Message):
    __slots__ = ("actor_path", "writes")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    WRITES_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    writes: _containers.RepeatedCompositeFieldContainer[EntityFieldWrite]
    def __init__(self, actor_path: _Optional[str] = ..., writes: _Optional[_Iterable[_Union[EntityFieldWrite, _Mapping]]] = ...) -> None: ...

class SetEntityFieldValuesResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetEntityAllFieldValuesBatchRequest(_message.Message):
    __slots__ = ("actor_path", "entity_ids")
    ACTOR_PATH_FIELD_NUMBER: _ClassVar[int]
    ENTITY_IDS_FIELD_NUMBER: _ClassVar[int]
    actor_path: str
    entity_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, actor_path: _Optional[str] = ..., entity_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class GetEntityAllFieldValuesBatchResponse(_message.Message):
    __slots__ = ("status_code", "error_message", "entity_values_list")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENTITY_VALUES_LIST_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    entity_values_list: _containers.RepeatedCompositeFieldContainer[EntityFieldValues]
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ..., entity_values_list: _Optional[_Iterable[_Union[EntityFieldValues, _Mapping]]] = ...) -> None: ...

class CustomCommandRequest(_message.Message):
    __slots__ = ("command",)
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    command: str
    def __init__(self, command: _Optional[str] = ...) -> None: ...

class CustomCommandResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class SetVisibilityRequest(_message.Message):
    __slots__ = ("visible", "actor_paths")
    VISIBLE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    visible: bool
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, visible: bool = ..., actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class SetVisibilityResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class SetLockRequest(_message.Message):
    __slots__ = ("locked", "actor_paths")
    LOCKED_FIELD_NUMBER: _ClassVar[int]
    ACTOR_PATHS_FIELD_NUMBER: _ClassVar[int]
    locked: bool
    actor_paths: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, locked: bool = ..., actor_paths: _Optional[_Iterable[str]] = ...) -> None: ...

class SetLockResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class SetMoveRotateSensitivityRequest(_message.Message):
    __slots__ = ("move_sensitivity", "rotate_sensitivity")
    MOVE_SENSITIVITY_FIELD_NUMBER: _ClassVar[int]
    ROTATE_SENSITIVITY_FIELD_NUMBER: _ClassVar[int]
    move_sensitivity: float
    rotate_sensitivity: float
    def __init__(self, move_sensitivity: _Optional[float] = ..., rotate_sensitivity: _Optional[float] = ...) -> None: ...

class SetMoveRotateSensitivityResponse(_message.Message):
    __slots__ = ("status_code", "error_message")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: StatusCode
    error_message: str
    def __init__(self, status_code: _Optional[_Union[StatusCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...
