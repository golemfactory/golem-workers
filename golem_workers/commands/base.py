from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict
from typing_extensions import TypeVar, Generic

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommandResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Command(ABC, Generic[TRequest, TResponse]):
    @abstractmethod
    async def __call__(self, request: TRequest) -> TResponse: ...
