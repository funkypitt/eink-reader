# Session D-Bus control interface for the running reader.
#
# Lets Tinta4PlusU (and scripts) drive the reader without a second process:
# fullscreen on/off when tablet reader mode starts/ends, page turns, raise.
# A second `eink-reader --fullscreen` finds the running instance here and
# asks it to go fullscreen instead of starting another copy.
#
#   gdbus call --session --dest org.eink.Reader --object-path /org/eink/Reader \
#         --method org.eink.Reader.ExitFullscreen
#
# dbus-python dispatches through the GLib main loop, which Qt on Linux uses
# as its event dispatcher, so the service runs on the GUI thread.

import logging

from PyQt5 import QtCore

logger = logging.getLogger(__name__)

BUS_NAME = 'org.eink.Reader'
OBJECT_PATH = '/org/eink/Reader'
IFACE = 'org.eink.Reader'

try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    # Must be declared before the first (shared) bus connection is created,
    # otherwise that connection has no main loop and cannot export objects.
    DBusGMainLoop(set_as_default=True)
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False


def running_instance():
    """Proxy to an already running reader, or None."""
    if not HAS_DBUS:
        return None
    try:
        bus = dbus.SessionBus()
        if not bus.name_has_owner(BUS_NAME):
            return None
        return dbus.Interface(bus.get_object(BUS_NAME, OBJECT_PATH), IFACE)
    except Exception:
        return None


def start_service(main_window):
    """Export the control interface for this window; returns the service or None."""
    if not HAS_DBUS:
        logger.info('dbus-python not available: reader control interface disabled')
        return None
    try:
        bus = dbus.SessionBus()
        if bus.name_has_owner(BUS_NAME):
            logger.info('Another reader owns %s; control interface not started', BUS_NAME)
            return None
        return _ReaderService(main_window, bus)
    except Exception as e:
        logger.warning('Reader control interface unavailable: %s', e)
        return None


if HAS_DBUS:
    class _ReaderService(dbus.service.Object):
        def __init__(self, main_window, bus):
            self.main_window = main_window
            self._owned_name = dbus.service.BusName(BUS_NAME, bus)  # keep a reference
            super().__init__(self._owned_name, OBJECT_PATH)
            logger.info('Reader control interface at %s', BUS_NAME)

        # -- helpers ------------------------------------------------------

        def _book_tab(self):
            tab = self.main_window.tabWidget.currentWidget()
            if tab is None or getattr(tab, 'is_library', True):
                # Prefer the most recently used book tab if the library is current
                for i in range(1, self.main_window.tabWidget.count()):
                    return self.main_window.tabWidget.widget(i)
                return None
            return tab

        def _later(self, fn):
            QtCore.QTimer.singleShot(0, fn)

        # -- methods ------------------------------------------------------

        @dbus.service.method(IFACE, out_signature='a{sv}')
        def GetState(self):
            tab = self._book_tab()
            return {
                'has_book': tab is not None,
                'fullscreen': bool(tab is not None and tab.is_fullscreen),
                'title': str(self.main_window.tabWidget.tabText(self.main_window.tabWidget.currentIndex())),
            }

        @dbus.service.method(IFACE)
        def Fullscreen(self):
            def go():
                tab = self._book_tab()
                if tab is None:
                    return
                self.main_window.tabWidget.setCurrentWidget(tab)
                if not tab.is_fullscreen:
                    tab.go_fullscreen()
            self._later(go)

        @dbus.service.method(IFACE)
        def ExitFullscreen(self):
            def leave():
                tab = self._book_tab()
                if tab is not None and tab.is_fullscreen:
                    tab.exit_fullscreen()
                self.main_window.show()
                self.main_window.activateWindow()
            self._later(leave)

        @dbus.service.method(IFACE)
        def ToggleFullscreen(self):
            def toggle():
                tab = self._book_tab()
                if tab is not None:
                    tab.go_fullscreen()  # toggles
            self._later(toggle)

        @dbus.service.method(IFACE)
        def NextPage(self):
            tab = self._book_tab()
            if tab is not None:
                self._later(tab.contentView.page_forward)

        @dbus.service.method(IFACE)
        def PreviousPage(self):
            tab = self._book_tab()
            if tab is not None:
                self._later(tab.contentView.page_backward)

        @dbus.service.method(IFACE)
        def Show(self):
            def show():
                tab = self._book_tab()
                target = tab.contentView if (tab is not None and tab.is_fullscreen) else self.main_window
                target.show()
                target.raise_()
                target.activateWindow()
            self._later(show)

        @dbus.service.method(IFACE)
        def Quit(self):
            self._later(self.main_window.closeEvent)
