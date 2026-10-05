# Kindle-style touch navigation for the content views.
#
# Taps on the left/right edge turn pages, horizontal swipes turn pages, a tap
# in the centre shows the navigation bar and a double tap in the centre
# toggles fullscreen. Everything is derived from the mouse events Qt
# synthesises for touch, so it also works with a mouse and needs no touch
# capability flags (which would otherwise disable the hand-drag panning).
#
# Edge taps and swipes act immediately; only the centre tap is delayed by the
# double-tap window so the two can be told apart. Page turns are the common
# case and must not pay that latency on an eInk panel.

import time

from PyQt5 import QtCore


class TouchNavigator(QtCore.QObject):
    TAP_MAX_MOVE_PX = 14       # finger jitter tolerated for a tap
    TAP_MAX_MS = 400           # longer presses are drags / selections
    SWIPE_MIN_PX = 80
    SWIPE_MAX_MS = 700
    DOUBLE_TAP_MS = 350
    LONG_PRESS_MS = 650        # press-and-hold = context menu (touch has no right button)
    EDGE_FRACTION = 0.30       # width of the previous/next tap zones

    def __init__(self, view, on_next, on_previous, on_centre_tap=None,
                 on_double_tap=None, enabled=None, right_to_left=None,
                 on_long_press=None):
        """
        view:            QAbstractScrollArea whose viewport receives the gestures
        on_next/previous: page turn callbacks
        on_centre_tap:   single tap in the middle zone (e.g. show the nav bar)
        on_double_tap:   double tap in the middle zone (e.g. toggle fullscreen)
        enabled:         callable -> bool; gestures are ignored when False
        right_to_left:   callable -> bool; swaps the edge zones (manga mode)
        on_long_press:   callable(pos) for press-and-hold (e.g. open the context menu)
        """
        super().__init__(view)
        self.view = view
        self.on_next = on_next
        self.on_previous = on_previous
        self.on_centre_tap = on_centre_tap
        self.on_double_tap = on_double_tap
        self.enabled = enabled or (lambda: True)
        self.right_to_left = right_to_left or (lambda: False)
        self.on_long_press = on_long_press
        self._long_press_fired = False

        self._press_pos = None
        self._press_time = 0.0
        self._last_tap_pos = None
        self._last_tap_time = 0.0

        self._centre_timer = QtCore.QTimer(self)
        self._centre_timer.setSingleShot(True)
        self._centre_timer.setInterval(self.DOUBLE_TAP_MS)
        self._centre_timer.timeout.connect(self._fire_centre_tap)

        self._long_press_timer = QtCore.QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(self.LONG_PRESS_MS)
        self._long_press_timer.timeout.connect(self._fire_long_press)

        view.viewport().installEventFilter(self)

    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QtCore.QEvent.MouseButtonPress:
            self._long_press_fired = False
            if event.button() == QtCore.Qt.LeftButton and not event.modifiers():
                self._press_pos = event.pos()
                self._press_time = time.monotonic()
                if self.on_long_press and self.enabled():
                    self._long_press_timer.start()
            else:
                self._press_pos = None
        elif etype == QtCore.QEvent.MouseMove:
            # Moving the finger cancels a pending long press
            if self._press_pos is not None and self._long_press_timer.isActive():
                moved = (event.pos() - self._press_pos).manhattanLength()
                if moved > self.TAP_MAX_MOVE_PX:
                    self._long_press_timer.stop()
        elif etype == QtCore.QEvent.MouseButtonRelease:
            self._long_press_timer.stop()
            if (self._press_pos is not None and event.button() == QtCore.Qt.LeftButton
                    and not self._long_press_fired):
                self._on_release(event.pos())
            self._press_pos = None
        return False  # never swallow: panning, selection and context menus keep working

    def _fire_long_press(self):
        if self._press_pos is None:
            return
        self._long_press_fired = True
        pos = self._press_pos
        if self.on_long_press:
            self.on_long_press(pos)

    def _on_release(self, pos):
        if not self.enabled():
            return
        dx = pos.x() - self._press_pos.x()
        dy = pos.y() - self._press_pos.y()
        elapsed_ms = (time.monotonic() - self._press_time) * 1000.0

        # Horizontal swipe: finger moves left -> next page (as on a Kindle)
        if abs(dx) >= self.SWIPE_MIN_PX and abs(dx) > 1.5 * abs(dy) and elapsed_ms <= self.SWIPE_MAX_MS:
            self._centre_timer.stop()
            self._turn(forward=dx < 0)
            return

        if abs(dx) > self.TAP_MAX_MOVE_PX or abs(dy) > self.TAP_MAX_MOVE_PX or elapsed_ms > self.TAP_MAX_MS:
            return  # a drag, a long press or a text selection

        self._on_tap(pos)

    def _on_tap(self, pos):
        width = max(1, self.view.viewport().width())
        x_frac = pos.x() / width
        now = time.monotonic()

        if x_frac < self.EDGE_FRACTION or x_frac > 1.0 - self.EDGE_FRACTION:
            self._centre_timer.stop()
            tapped_right = x_frac > 0.5
            if self.right_to_left():
                tapped_right = not tapped_right
            self._turn(forward=tapped_right)
            self._last_tap_pos = None
            return

        # Centre zone: double tap within the window and close to the first tap
        if (self._last_tap_pos is not None
                and (now - self._last_tap_time) * 1000.0 <= self.DOUBLE_TAP_MS
                and (pos - self._last_tap_pos).manhattanLength() <= 4 * self.TAP_MAX_MOVE_PX):
            self._centre_timer.stop()
            self._last_tap_pos = None
            if self.on_double_tap:
                self.on_double_tap()
            return

        self._last_tap_pos = pos
        self._last_tap_time = now
        self._centre_timer.start()

    def _fire_centre_tap(self):
        self._last_tap_pos = None
        if self.on_centre_tap:
            self.on_centre_tap()

    def _turn(self, forward):
        if forward:
            self.on_next()
        else:
            self.on_previous()
