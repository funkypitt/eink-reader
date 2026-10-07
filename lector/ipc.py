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


def claim_name():
    """Own org.eink.Reader *before* the (slow) main window is built.

    Returns the BusName, or None if another reader owns it (never queued, so
    a second copy can never silently become the service later).
    """
    if not HAS_DBUS:
        return None
    try:
        return dbus.service.BusName(BUS_NAME, dbus.SessionBus(), do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        return None
    except Exception as e:
        logger.warning('Could not claim %s: %s', BUS_NAME, e)
        return None


def start_service(main_window, bus_name):
    """Export the control interface on a name claimed with claim_name()."""
    if not HAS_DBUS or bus_name is None:
        logger.info('Reader control interface disabled (no D-Bus name)')
        return None
    try:
        return _ReaderService(main_window, bus_name)
    except Exception as e:
        logger.warning('Reader control interface unavailable: %s', e)
        return None


if HAS_DBUS:
    class _ReaderService(dbus.service.Object):
        def __init__(self, main_window, bus_name):
            self.main_window = main_window
            self._owned_name = bus_name  # keep a reference: Object.__init__ overwrites _name
            super().__init__(bus_name, OBJECT_PATH)
            logger.info('Reader control interface at %s', BUS_NAME)

        # -- helpers ------------------------------------------------------

        def _book_tabs(self):
            tw = self.main_window.tabWidget
            return [tw.widget(i) for i in range(1, tw.count())]

        def _book_tab(self):
            tab = self.main_window.tabWidget.currentWidget()
            if tab is not None and not getattr(tab, 'is_library', True):
                return tab
            # Library is current: the most recently used book
            tabs = self._book_tabs()
            if not tabs:
                return None
            return max(tabs, key=lambda t: t.metadata.get('last_accessed') or 0)

        def _leave_all_fullscreen(self):
            """Only one fullscreen top-level at a time; also closes docks that
            would otherwise make exit_fullscreen() a no-op."""
            for t in self._book_tabs():
                if getattr(t, 'is_fullscreen', False):
                    for dock in (t.annotationNoteDock, t.sideDock):
                        dock.setVisible(False)
                    t.exit_fullscreen()

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
                if tab is None or tab.is_fullscreen:
                    return
                self._leave_all_fullscreen()
                self.main_window.tabWidget.setCurrentWidget(tab)
                tab.go_fullscreen()
            self._later(go)

        @dbus.service.method(IFACE)
        def ExitFullscreen(self):
            def leave():
                self._leave_all_fullscreen()
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

        @dbus.service.method(IFACE, in_signature='as')
        def OpenFiles(self, paths):
            """Open (and add to the library) files given as absolute paths."""
            files = [str(p) for p in paths]
            def do_open():
                was_fullscreen = any(getattr(t, 'is_fullscreen', False) for t in self._book_tabs())
                self._leave_all_fullscreen()
                self.main_window.process_post_hoc_files(files, True)
                tab = self._book_tab()
                if was_fullscreen and tab is not None:
                    tab.go_fullscreen()   # keep the tablet posture: the new book takes over the screen
                    return
                self.main_window.show()
                self.main_window.raise_()
                self.main_window.activateWindow()
            self._later(do_open)

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
