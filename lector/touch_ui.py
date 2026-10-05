# Touch-sized chrome for the eInk tablet posture.
#
# Lector's widgets are sized for a mouse (22 px toolbar icons, 30 px nav
# bar). On a 2560x1600 panel held like a tablet they need finger-sized
# targets. Everything here is additive: a stylesheet for sizes, bigger
# icons, finger scrolling on the lists, and single tap to open a book.
#
# Disable with EINK_READER_TOUCH_UI=0 (e.g. when using a mouse on a desk).

import os

from PyQt5 import QtWidgets, QtCore

# Minimum comfortable finger target (Material/HIG agree on ~44-48 px)
TARGET = 48
ICON = 36

TOUCH_QSS = f"""
QToolBar {{ spacing: 6px; padding: 4px; }}
QToolBar QToolButton {{ min-width: {TARGET}px; min-height: {TARGET}px; padding: 4px; }}
QToolBar QComboBox, QToolBar QLineEdit, QToolBar QFontComboBox {{ min-height: {TARGET - 6}px; }}
QTabBar::tab {{ min-height: {TARGET}px; padding: 6px 14px; }}
QTabBar::close-button {{ width: 24px; height: 24px; subcontrol-position: right; }}
QPushButton {{ min-height: {TARGET - 8}px; padding: 6px 14px; }}
QComboBox {{ min-height: {TARGET - 8}px; padding: 2px 10px; }}
QComboBox::drop-down {{ width: {TARGET - 8}px; }}
QComboBox QAbstractItemView::item, QTreeView::item, QListView::item, QTableView::item {{ min-height: {TARGET - 4}px; padding: 4px; }}
QLineEdit {{ min-height: {TARGET - 8}px; padding: 2px 8px; }}
QMenu::item {{ min-height: {TARGET - 4}px; padding: 8px 32px 8px 16px; }}
QMenu::separator {{ height: 2px; margin: 6px 10px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 26px; height: 26px; }}
QScrollBar:vertical {{ width: 22px; }}
QScrollBar:horizontal {{ height: 22px; }}
QScrollBar::handle {{ min-height: 60px; min-width: 60px; border-radius: 6px; }}
QHeaderView::section {{ min-height: {TARGET - 8}px; padding: 4px 8px; }}
QDockWidget::title {{ min-height: {TARGET - 12}px; }}
QSpinBox, QDoubleSpinBox {{ min-height: {TARGET - 8}px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 32px; }}
"""


def touch_ui_enabled():
    return os.environ.get('EINK_READER_TOUCH_UI', '1') not in ('0', 'false', 'no')


def enable_finger_scroll(view):
    """Drag-to-scroll with inertia on an item view (a finger has no wheel)."""
    try:
        QtWidgets.QScroller.grabGesture(
            view.viewport(), QtWidgets.QScroller.LeftMouseButtonGesture)
        props = QtWidgets.QScroller.scroller(view.viewport()).scrollerProperties()
        props.setScrollMetric(QtWidgets.QScrollerProperties.DragStartDistance, 0.004)
        props.setScrollMetric(QtWidgets.QScrollerProperties.OvershootDragResistanceFactor, 0.3)
        QtWidgets.QScroller.scroller(view.viewport()).setScrollerProperties(props)
    except Exception:
        pass


def apply_touch_ui(main_window):
    """Apply touch sizing to the main window (call once after the UI is built)."""
    if not touch_ui_enabled():
        return False

    app = QtWidgets.QApplication.instance()
    app.setStyleSheet((app.styleSheet() or '') + TOUCH_QSS)

    # The floating navigation bar is the only touch access to the table of
    # contents, bookmarks, fullscreen and the library while reading, so it
    # must exist (it only shows on a centre tap and hides by itself).
    if not main_window.settings.get('nav_bar', True):
        main_window.settings['nav_bar'] = True

    # A slightly larger base font helps every label and menu
    font = app.font()
    if font.pointSize() > 0 and font.pointSize() < 11:
        font.setPointSize(11)
        app.setFont(font)

    for toolbar in (main_window.libraryToolBar, main_window.bookToolBar):
        toolbar.setIconSize(QtCore.QSize(ICON, ICON))

    # Library: one tap opens a book; finger scrolling; more breathing room
    for view in (main_window.listView, main_window.tableView):
        try:
            view.doubleClicked.disconnect(main_window.library_doubleclick)
        except TypeError:
            pass
        view.clicked.connect(main_window.library_doubleclick)
        enable_finger_scroll(view)
    main_window.listView.setGridSize(QtCore.QSize(200, 270))
    main_window.listView.setSpacing(6)

    # Table of contents trees inside the combo boxes
    try:
        enable_finger_scroll(main_window.bookToolBar.tocTreeView)
    except Exception:
        pass

    return True
