from __future__ import annotations

import sys
import ctypes
from ctypes import byref, sizeof, WinDLL, Structure, POINTER, cast
from ctypes.wintypes import BOOL, DWORD, LONG, LPCVOID, LPRECT, RECT, MSG

# Qt
from PySide6.QtCore import QEvent
# pywin32
import win32con
import win32gui
import win32api 

# Basic Win types
HWND   = getattr(ctypes.wintypes, 'HWND', ctypes.c_void_p)
UINT   = getattr(ctypes.wintypes, 'UINT', ctypes.c_uint)
LPARAM = getattr(ctypes.wintypes, 'LPARAM', ctypes.c_long)


class MARGINS(Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


class APPBARDATA(Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("hWnd", HWND),
        ("uCallbackMessage", UINT),
        ("uEdge", UINT),
        ("rc", RECT),
        ("lParam", LPARAM),
    ]


class PWINDOWPOS(Structure):
    _fields_ = [
        ("hWnd", HWND),
        ("hwndInsertAfter", HWND),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("cx", ctypes.c_int),
        ("cy", ctypes.c_int),
        ("flags", UINT),
    ]


class NCCALCSIZE_PARAMS(Structure):
    _fields_ = [
        ("rgrc", RECT * 3),
        ("lppos", POINTER(PWINDOWPOS)),
    ]


LPNCCALCSIZE_PARAMS = POINTER(NCCALCSIZE_PARAMS)


# DWM attributes / prefs we actually use
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR            = 34  

DWMWCP_DONOTROUND = 1
DWMWCP_ROUND      = 2


# Styles
GWL_STYLE       = -16
WS_MINIMIZEBOX  = 0x00020000
WS_MAXIMIZEBOX  = 0x00010000
WS_CAPTION      = 0x00C00000
WS_THICKFRAME   = 0x00040000
WS_SYSMENU      = 0x00080000  

# System metrics
SM_CXSIZEFRAME   = 32
SM_CYSIZEFRAME   = 33
SM_CXPADDEDBORDER = 92

def _is_win11() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= 22000


def _notify_frame_changed(hwnd: int) -> None:
    win32gui.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER |
        win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED
    )


def _is_dwm_enabled() -> bool:
    try:
        dwmapi = WinDLL("dwmapi", use_last_error=True)
        fn = dwmapi.DwmIsCompositionEnabled
        fn.argtypes = [POINTER(BOOL)]
        fn.restype = ctypes.c_int
        enabled = BOOL()
        if fn(byref(enabled)) < 0:
            return False
        return bool(enabled.value)
    except Exception:
        return False


def _get_resize_border_thickness(hwnd: int, horizontal: bool) -> int:
    try:
        idx = win32con.SM_CXSIZEFRAME if horizontal else win32con.SM_CYSIZEFRAME
        frame = win32api.GetSystemMetrics(idx)
        pad = win32api.GetSystemMetrics(SM_CXPADDEDBORDER)
        return max(5, frame + pad)
    except Exception:
        return 5


def _is_maximized(hwnd: int) -> bool:
    plc = win32gui.GetWindowPlacement(hwnd)
    return plc and plc[1] == win32con.SW_MAXIMIZE


def _is_fullscreen(hwnd: int) -> bool:
    r = win32gui.GetWindowRect(hwnd)
    if not r:
        return False
    mon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTOPRIMARY)
    if not mon:
        return False
    mr = win32api.GetMonitorInfo(mon)["Monitor"]
    return tuple(r) == tuple(mr)

class _Dwm:
    _user32 = WinDLL("user32", use_last_error=True)
    _dwmapi = WinDLL("dwmapi", use_last_error=True)

    GetWindowLongW = _user32.GetWindowLongW
    SetWindowLongW = _user32.SetWindowLongW
    GetWindowLongW.argtypes = (ctypes.c_int, ctypes.c_int)
    GetWindowLongW.restype = ctypes.c_int
    SetWindowLongW.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
    SetWindowLongW.restype = ctypes.c_int

    DwmExtendFrameIntoClientArea = _dwmapi.DwmExtendFrameIntoClientArea
    DwmExtendFrameIntoClientArea.argtypes = (ctypes.c_int, POINTER(MARGINS))
    DwmExtendFrameIntoClientArea.restype = LONG

    DwmSetWindowAttribute = _dwmapi.DwmSetWindowAttribute
    DwmSetWindowAttribute.argtypes = (ctypes.c_int, DWORD, LPCVOID, DWORD)
    DwmSetWindowAttribute.restype = LONG

    @classmethod
    def ensure_styles_for_animations(cls, hwnd: int) -> None:
        style = cls.GetWindowLongW(hwnd, GWL_STYLE)
        style |= (WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU)
        cls.SetWindowLongW(hwnd, GWL_STYLE, style)

    @classmethod
    def set_extend_enabled(cls, hwnd: int, enabled: bool) -> None:
        EDGE = -1
        margins = MARGINS(EDGE, EDGE, EDGE, EDGE) if enabled else MARGINS(0, 0, 0, 0)
        cls.DwmExtendFrameIntoClientArea(hwnd, byref(margins))

    @classmethod
    def set_corner_pref(cls, hwnd: int, pref: int) -> None:
        if not _is_win11():
            return
        val = ctypes.c_int(pref)
        cls.DwmSetWindowAttribute(hwnd, DWORD(DWMWA_WINDOW_CORNER_PREFERENCE), byref(val), DWORD(sizeof(val)))

    @classmethod
    def set_border_color(cls, hwnd: int, rgb_tuple: tuple[int, int, int] | None) -> None:
        if not _is_win11():
            return
        if rgb_tuple is None:
            val = DWORD(0xFFFFFFFF)
        else:
            r, g, b = rgb_tuple
            val = DWORD(r | (g << 8) | (b << 16))
        cls.DwmSetWindowAttribute(hwnd, DWORD(DWMWA_BORDER_COLOR), byref(val), DWORD(sizeof(val)))


class Win11FramelessMixin:
    """
    Frameless top-level mixin with:
      • WS_CAPTION kept (system animations & snap work)
      • Delayed DWM extend after first paint (prevents startup flash)
      • Extend-frame disabled during live resize (prevents underlay window visibility)
      • NC painting suppressed (no system titlebar draw over custom UI)
    """

    _fx_inited = False
    _dwm_applied = False
    _defer_apply = True
    _is_sizing = False

    def _window_maximize_restore(self):
        maximized = self.isMaximized()
        fullscreen = self.isFullScreen()

        if sys.platform != "win32":
            if maximized or fullscreen:
                self.showNormal()
            else:
                self.showMaximized()
            return
        
        hwnd = int(self.winId())
        if maximized:
            win32api.SendMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_RESTORE, 0)
        elif fullscreen:
            self.showNormal()
        else:
            win32api.SendMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_MAXIMIZE, 0)

    def show_system_menu(self, global_pos=None):
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        win32gui.SetForegroundWindow(hwnd)
        hmenu = win32gui.GetSystemMenu(hwnd, False)

        is_max = _is_maximized(hwnd)

        def _enable_menu_item(cmd, enable: bool):
            state = win32con.MF_ENABLED if enable else (win32con.MF_GRAYED | win32con.MF_DISABLED)
            win32gui.EnableMenuItem(hmenu, cmd, win32con.MF_BYCOMMAND | state)

        _enable_menu_item(win32con.SC_RESTORE, is_max)
        _enable_menu_item(win32con.SC_MOVE, not is_max)
        _enable_menu_item(win32con.SC_SIZE, not is_max)
        _enable_menu_item(win32con.SC_MAXIMIZE, not is_max)
        _enable_menu_item(win32con.SC_MINIMIZE, True)
        _enable_menu_item(win32con.SC_CLOSE, True)

        if global_pos is None:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            x, y = left + 8, top + 8
        else:
            x, y = win32gui.GetCursorPos()

        flags = (win32con.TPM_RETURNCMD | 
                 win32con.TPM_RIGHTBUTTON | 
                 win32con.TPM_LEFTALIGN | 
                 win32con.TPM_TOPALIGN)
        cmd = win32gui.TrackPopupMenu(hmenu, flags, x, y, 0, hwnd, None)

        if cmd:
            win32api.PostMessage(hwnd, win32con.WM_SYSCOMMAND, cmd, 0)

    # ---- Qt events ----
    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform != "win32":
            return
        if int(self.winId()) == 0:
            return

        if not self._fx_inited:
            self._fx_inited = True
            hwnd = int(self.winId())
            _Dwm.ensure_styles_for_animations(hwnd)
            # Defer DWM extend until first paint
            self._defer_apply = True
            self._dwm_applied = False
            self._sync_dwm_on_state()

    def paintEvent(self, event):
        super().paintEvent(event)
        if sys.platform != "win32":
            return
        if self._defer_apply and not self._dwm_applied and not self.isMaximized() and not self.isFullScreen():
            # First stable paint arrived -> enable extend-frame now
            hwnd = int(self.winId())
            if _is_dwm_enabled():
                _Dwm.set_extend_enabled(hwnd, True)
                _Dwm.set_corner_pref(hwnd, DWMWCP_ROUND)
            _notify_frame_changed(hwnd)
            self._dwm_applied = True
            self._defer_apply = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._sync_dwm_on_state()

    # ---- DWM sync ----
    def _sync_dwm_on_state(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())

        maximized = self.isMaximized()
        fullscreen = self.isFullScreen()

        if maximized or fullscreen:
            # No extend-frame and square corners
            _Dwm.set_extend_enabled(hwnd, False)
            if _is_dwm_enabled():
                _Dwm.set_corner_pref(hwnd, DWMWCP_DONOTROUND)
            _notify_frame_changed(hwnd)
            self._dwm_applied = False
            return

        if self._is_sizing:
            # During live resize we keep extend-frame disabled to avoid underlay
            _Dwm.set_extend_enabled(hwnd, False)
            if _is_dwm_enabled():
                _Dwm.set_corner_pref(hwnd, 0)
            _notify_frame_changed(hwnd)
            self._dwm_applied = False
            return

        # Normal/snapped
        if _is_dwm_enabled():
            _Dwm.set_extend_enabled(hwnd, True)
            _Dwm.set_corner_pref(hwnd, DWMWCP_ROUND)
            self._dwm_applied = True
        else:
            self._dwm_applied = False
        _notify_frame_changed(hwnd)

    # ---- Native hook ----
    def nativeEvent(self, eventType, message):
        try:
            msg = MSG.from_address(int(message))
            if not msg.hWnd:
                return False, 0

            # Live-resize start/stop
            if msg.message == win32con.WM_ENTERSIZEMOVE:
                self._is_sizing = True
                self._sync_dwm_on_state()
                return False, 0

            if msg.message == win32con.WM_EXITSIZEMOVE:
                self._is_sizing = False
                self._sync_dwm_on_state()
                return False, 0

            # Resize hit-test (only when we actually have a resizable state)
            if msg.message == win32con.WM_NCHITTEST and getattr(self, "_resizeEnabled", True):
                if self.isMaximized() or self.isFullScreen():
                    return False, 0

                xPos, yPos = win32gui.ScreenToClient(msg.hWnd, win32api.GetCursorPos())
                cl = win32gui.GetClientRect(msg.hWnd)
                w, h = cl[2] - cl[0], cl[3] - cl[1]

                bw = 0 if _is_maximized(msg.hWnd) or _is_fullscreen(msg.hWnd) else _get_resize_border_thickness(msg.hWnd, True)

                lx = xPos < bw
                rx = xPos > w - bw
                ty = yPos < bw
                by = yPos > h - bw

                if lx and ty:  return True, win32con.HTTOPLEFT
                if rx and by:  return True, win32con.HTBOTTOMRIGHT
                if rx and ty:  return True, win32con.HTTOPRIGHT
                if lx and by:  return True, win32con.HTBOTTOMLEFT
                if ty:         return True, win32con.HTTOP
                if by:         return True, win32con.HTBOTTOM
                if lx:         return True, win32con.HTLEFT
                if rx:         return True, win32con.HTRIGHT
                return False, 0

            # NC calc: adjust for maximized (and auto-hide taskbar nudge)
            if msg.message == win32con.WM_NCCALCSIZE:
                if msg.wParam:
                    rect = cast(msg.lParam, LPNCCALCSIZE_PARAMS).contents.rgrc[0]
                else:
                    rect = cast(msg.lParam, LPRECT).contents

                isMax = _is_maximized(msg.hWnd)
                isFull = _is_fullscreen(msg.hWnd)

                if isMax and not isFull:
                    ty = _get_resize_border_thickness(msg.hWnd, False)
                    tx = _get_resize_border_thickness(msg.hWnd, True)
                    rect.top    += ty
                    rect.left   += tx
                    rect.right  -= tx
                    rect.bottom -= ty

                # keep auto-hide taskbar visible
                try:
                    ABM_GETSTATE = 4 
                    ABS_AUTOHIDE = 1
                    ABM_GETTASKBARPOS = 5
                    abd = APPBARDATA(sizeof(APPBARDATA), 0, 0, 0, RECT(0, 0, 0, 0), 0)
                    shell = ctypes.windll.shell32
                    if shell.SHAppBarMessage(ABM_GETSTATE, byref(abd)) == ABS_AUTOHIDE:
                        if shell.SHAppBarMessage(ABM_GETTASKBARPOS, byref(abd)):
                            if abd.uEdge == 0:   rect.left   += 2  # left
                            elif abd.uEdge == 1: rect.top    += 2  # top
                            elif abd.uEdge == 2: rect.right  -= 2  # right
                            elif abd.uEdge == 3: rect.bottom -= 2  # bottom
                except Exception:
                    pass

                return True, 0

            # State changes
            if msg.message == win32con.WM_SIZE:
                self._sync_dwm_on_state()
                return False, 0

            return False, 0

        except Exception:
            return False, 0
