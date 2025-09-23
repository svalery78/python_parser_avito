from __future__ import annotations

from typing import Protocol, Optional


class OutputHandler(Protocol):
    def send(self, payload: str) -> None: ...


class PrintHandler:
    def send(self, payload: str) -> None:
        print(payload)


class OutputDispatcher:
    """Dispatch parsed content either to console or to an external module.

    An external handler can be injected to integrate with other modules later.
    """

    def __init__(self, handler: Optional[OutputHandler] = None) -> None:
        self.handler = handler or PrintHandler()

    def dispatch(self, payload: str) -> None:
        self.handler.send(payload)


__all__ = ["OutputDispatcher", "OutputHandler", "PrintHandler"]


