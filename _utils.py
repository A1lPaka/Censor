from PySide6.QtCore import QObject, QEvent, QPoint, QTimer
import os, sys

class PositionSetting(QObject):
    def __init__(self, dx=-1, dy=1, parent=None):
        super().__init__(parent)
        self._offset = QPoint(dx, dy)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Show, QEvent.ShowToParent) and obj.property("_allow_position_offset"):
            if obj.property("_popup_offset_applied"):
                return False
            obj.setProperty("_popup_offset_applied", True)
            offset = QPoint(self._offset)
            def apply_shift(o=obj, off=offset):
                try:
                    if o is not None and o.isVisible():
                        o.move(o.pos() + off)
                        o.setProperty("_popup_offset_applied", False)
                except RuntimeError:
                    pass
            QTimer.singleShot(0, apply_shift)
        return False
    
def res_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)