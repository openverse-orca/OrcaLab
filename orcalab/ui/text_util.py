from typing import List
from PySide6 import QtCore, QtWidgets, QtGui


def split_text_to_lines(
    text: str,
    font: QtGui.QFont,
    max_width: int,
    max_lines: int,
) -> List[str]:
    font_metrics = QtGui.QFontMetrics(font)
    dot_width = font_metrics.horizontalAdvance("...")
    test_width = max_width + dot_width

    lines = []
    while text and len(lines) < max_lines:
        if font_metrics.horizontalAdvance(text) > max_width:
            if len(lines) == max_lines - 1:
                line = font_metrics.elidedText(
                    text, QtCore.Qt.TextElideMode.ElideRight, max_width
                )
                lines.append(line)
            else:
                line = font_metrics.elidedText(
                    text, QtCore.Qt.TextElideMode.ElideRight, test_width
                )
                line = line[:-3]  # Remove "..."
                lines.append(line)

            text = text[len(line) :]
        else:
            lines.append(text)
            break

    return lines
