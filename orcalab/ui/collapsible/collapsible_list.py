from __future__ import annotations

import asyncio
from typing import List

from PySide6 import QtCore, QtWidgets

from orcalab.perf_log import perf_timer, perf_log
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection


class CollapsibleList(QtWidgets.QWidget):

    _DEFAULT_BATCH_SIZE = 5

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self._sections: List[CollapsibleSection] = []
        self._pending_task: asyncio.Task | None = None
        self._active_key: object | None = None
        self._batch_size = self._DEFAULT_BATCH_SIZE

        self._container = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch()

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._container)

    @property
    def sections(self) -> List[CollapsibleSection]:
        return list(self._sections)

    def set_sections(self, sections: List[CollapsibleSection]):
        self.cancel_render()
        self._clear_layout()
        self._sections = sections
        for section in sections:
            self._layout.insertWidget(self._layout.count() - 1, section)

    async def render_sections_batched(
        self,
        sections: List[CollapsibleSection],
        cache_key: object | None = None,
    ):
        self.cancel_render()
        self._clear_layout()
        self._sections = []
        self._active_key = cache_key

        async def _render():
            batch: List[CollapsibleSection] = []
            for i, section in enumerate(sections):
                if self._active_key != cache_key:
                    for s in batch:
                        s.setParent(None)
                        s.deleteLater()
                    return

                self._sections.append(section)
                batch.append(section)
                self._layout.insertWidget(self._layout.count() - 1, section)

                if len(batch) >= self._batch_size:
                    batch.clear()
                    await asyncio.sleep(0)

            perf_log(f"CollapsibleList.render_sections_batched: {len(self._sections)} sections rendered", feature="SECTION")

        self._pending_task = asyncio.create_task(_render())
        try:
            await self._pending_task
        except asyncio.CancelledError:
            pass
        finally:
            self._pending_task = None

    def cancel_render(self):
        if self._pending_task is not None:
            self._pending_task.cancel()
            self._pending_task = None
        self._active_key = None

    def _clear_layout(self):
        for section in self._sections:
            section.setParent(None)
            section.deleteLater()
        self._sections.clear()

        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def clear(self):
        self.cancel_render()
        self._clear_layout()
