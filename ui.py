from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QRect, QPoint, Signal, QByteArray, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel as _QtLabel,
    QLineEdit as _QtLineEdit, QMessageBox, QPushButton, QScrollArea, QSizeGrip, QSlider,
    QSpinBox, QToolButton, QVBoxLayout, QWidget, QStyle, QListWidget, QListWidgetItem,
)

from config import MODE_NAMES, THEMES


class QLabel(_QtLabel):
    """Label with Persian-friendly right alignment by default."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class QLineEdit(_QtLineEdit):
    """Text input with right alignment by default; URL/English fields opt back to LTR."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)


ICON_PATHS: dict[str, str] = {
    "scan": '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M7 9h10v6H7z"/>',
    "play": '<path d="m8 5 11 7-11 7z" fill="currentColor" stroke="none"/>',
    "pause": '<path d="M7 5h3v14H7zM14 5h3v14h-3z" fill="currentColor" stroke="none"/>',
    "eye": '<path d="M2.5 12s3.2-6 9.5-6 9.5 6 9.5 6-3.2 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.8"/>',
    "eye-off": '<path d="m3 3 18 18M10.6 6.2A10.7 10.7 0 0 1 12 6c6.3 0 9.5 6 9.5 6a16 16 0 0 1-3.1 3.7M6.2 6.7C3.8 8.3 2.5 12 2.5 12s3.2 6 9.5 6c1.3 0 2.5-.3 3.5-.7"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "history": '<path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
    "languages": '<path d="m5 8 4 9M1 17l4-9 4 9M2.5 14h5M13 5h8M17 3v2M14 10c1.2 3 3.1 5 6 6M20 10c-1.2 3-3.1 5-6 6M13 19l3-6 3 6M14.5 16h3"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a7.9 7.9 0 0 1-1.7 1l-.3 1.8h-2.8l-.3-1.8a7.9 7.9 0 0 1-1.7-1l-1.7.6-1.4-2.4 1.4-1.1a7.1 7.1 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.6a7.9 7.9 0 0 1 1.7-1l.3-1.8h2.8l.3 1.8a7.9 7.9 0 0 1 1.7 1l1.7-.6 1.4 2.4-1.4 1.1a7.1 7.1 0 0 1 0 2Z" transform="translate(-1 -1) scale(.98)"/>',
    "x": '<path d="m6 6 12 12M18 6 6 18"/>',
    "chevron-up": '<path d="m5 15 7-7 7 7"/>',
    "chevron-down": '<path d="m5 9 7 7 7-7"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
    "bookmark": '<path d="M6 4h12v17l-6-4-6 4z"/>',
    "bookmark-filled": '<path d="M6 4h12v17l-6-4-6 4z" fill="currentColor"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    "minus": '<path d="M5 12h14"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/>',
}


def icon(name: str, color: str = "#171717", size: int = 22) -> QIcon:
    paths = ICON_PATHS.get(name, ICON_PATHS["check"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">
      <g fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths}</g>
    </svg>'''
    svg = svg.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def apply_shadow(widget: QWidget, blur: int = 24, y: int = 5) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y)
    shadow.setColor(QColor(0, 0, 0, 48))
    widget.setGraphicsEffect(shadow)


def apply_glass_icon_button(button: "IconButton", theme: dict[str, str]) -> None:
    """Apply a translucent, theme-aware treatment to icon-only controls."""
    panel = QColor(theme.get("panel", "#FFFFFF"))
    border = QColor(theme.get("border", "#777777"))

    def rgba(color: QColor, alpha: int) -> str:
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"

    button.setIcon(icon(button.icon_name, color=theme.get("text", "#171717")))
    button.set_colors(
        rgba(panel, 22),
        rgba(panel, 100),
        rgba(panel, 150),
        rgba(border, 135),
    )


class IconButton(QToolButton):
    def __init__(self, icon_name: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.setIcon(icon(icon_name))
        self.setIconSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(21, 21))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(False)
        self.setFixedSize(38, 38)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_colors("#FFFFFF", "#ECECEB", "#DCDCD8")

    def set_colors(self, background: str, hover: str, pressed: str, border: str = "") -> None:
        border_rule = f"border: 1px solid {border};" if border else "border: 0;"
        self.setStyleSheet(f"""
            QToolButton {{ background: {background}; {border_rule} border-radius: 10px; padding: 5px; }}
            QToolButton:hover {{ background: {hover}; }}
            QToolButton:pressed {{ background: {pressed}; }}
        """)

    def set_named_icon(self, name: str, tooltip: str) -> None:
        self.icon_name = name
        self.setIcon(icon(name))
        self.setToolTip(tooltip)


class FloatingToolbar(QWidget):
    region_requested = Signal()
    capture_toggled = Signal()
    overlay_toggled = Signal()
    history_requested = Signal()
    mode_cycle_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.settings = settings
        self.setObjectName("floatingToolbar")
        self.capture_active = False
        self.overlay_visible = False
        self.icon_color = "#171717"
        self._drag_position: QPoint | None = None
        self.buttons: dict[str, IconButton] = {}
        self._build()
        self.apply_settings(settings)
        self.move(int(settings.get("toolbar_x", 60)), int(settings.get("toolbar_y", 70)))

    def _build(self) -> None:
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(7, 7, 7, 7)
        self.root_layout.setSpacing(3)
        self.button_specs = [
            ("region", "scan", "انتخاب محدوده OCR", self.region_requested),
            ("capture", "play", "شروع خواندن متن", self.capture_toggled),
            ("overlay", "eye", "نمایش پنل ترجمه", self.overlay_toggled),
            ("history", "history", "تاریخچه ترجمه‌ها", self.history_requested),
            ("mode", "languages", "تغییر موتور ترجمه", self.mode_cycle_requested),
            ("settings", "settings", "تنظیمات", self.settings_requested),
            ("quit", "x", "خروج از برنامه", self.quit_requested),
        ]
        for key, icon_name, tooltip, signal in self.button_specs:
            button = IconButton(icon_name, tooltip, self)
            button.clicked.connect(signal.emit)
            self.buttons[key] = button
            self.root_layout.addWidget(button)
        apply_shadow(self, blur=26, y=5)

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        vertical = settings.get("toolbar_orientation") == "vertical"
        self.root_layout.setDirection(QBoxLayout.Direction.LeftToRight if not vertical else QBoxLayout.Direction.TopToBottom)
        style = str(settings.get("toolbar_style", "light")).lower()
        if style == "theme":
            theme = THEMES.get(settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
            color = theme["text"]
            bg = theme["toolbar"]
            button_bg = theme["panel"]
            hover_bg = theme["separator"]
            pressed_bg = theme["border"]
            border = theme["border"]
        elif style == "dark":
            color, bg = "#F5F7FA", "#17191D"
            button_bg, hover_bg, pressed_bg = "#24272D", "#343942", "#454B56"
            border = "#454A53"
        else:  # Light mode is the default and remains compatible with old setting value "white".
            color, bg = "#171717", "#F7F7F4"
            button_bg, hover_bg, pressed_bg = "#FFFFFF", "#E9E9E5", "#D8D8D2"
            border = "#D0D0CB"
        self.icon_color = color
        radius = max(10, min(22, int(settings.get("corner_radius", 18))))
        self.setStyleSheet(
            f"QWidget#floatingToolbar {{ background: {bg}; border: 1px solid {border}; border-radius: {radius}px; }}"
        )
        for button in self.buttons.values():
            button.setIcon(icon(button.icon_name, color=color))
            button.set_colors(button_bg, hover_bg, pressed_bg)
        self._update_tooltips()
        self.adjustSize()

    def _update_tooltips(self) -> None:
        capture_name = "pause" if self.capture_active else "play"
        self.buttons["capture"].setIcon(icon(capture_name, color=self.icon_color))
        self.buttons["capture"].icon_name = capture_name
        self.buttons["capture"].setToolTip("توقف OCR" if self.capture_active else "شروع خواندن متن")
        overlay_name = "eye-off" if self.overlay_visible else "eye"
        self.buttons["overlay"].setIcon(icon(overlay_name, color=self.icon_color))
        self.buttons["overlay"].icon_name = overlay_name
        self.buttons["overlay"].setToolTip("مخفی کردن پنل ترجمه" if self.overlay_visible else "نمایش پنل ترجمه")
        mode = MODE_NAMES.get(self.settings.get("mode", "local"), "Local AI")
        self.buttons["mode"].setToolTip(f"موتور فعلی: {mode} — برای تغییر کلیک کن")

    def set_capture_active(self, active: bool) -> None:
        self.capture_active = active
        self._update_tooltips()

    def set_overlay_visible(self, visible: bool) -> None:
        self.overlay_visible = visible
        self._update_tooltips()

    def apply_settings_and_place(self, settings: dict[str, Any]) -> None:
        self.apply_settings(settings)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.childAt(event.position().toPoint()) is None:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings["toolbar_x"] = self.x()
        self.settings["toolbar_y"] = self.y()
        super().closeEvent(event)


class RegionSelector(QWidget):
    region_selected = Signal(dict)
    cancelled = Signal()

    def __init__(self, screen_geometry: QRect, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(screen_geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setWindowOpacity(1.0)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self._finished = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("با ماوس محدوده متن را بکش؛ برای لغو Esc را بزن.")

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPen, QFont
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Subtle smoky-glass veil: the game remains visible under the selection layer.
        painter.fillRect(self.rect(), QColor(24, 31, 39, 72))
        painter.setFont(QFont("Segoe UI", 10))

        if self._origin is not None and self._current is not None:
            rect = QRect(self._origin, self._current).normalized()
            # Bright translucent highlight separates the selected area from the rest of the screen.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(164, 220, 247, 42))
            painter.drawRoundedRect(rect, 7, 7)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(220, 246, 255, 245), 2, Qt.PenStyle.SolidLine))
            painter.drawRoundedRect(rect, 7, 7)
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1, Qt.PenStyle.DashLine))
            inset = rect.adjusted(4, 4, -4, -4)
            if inset.width() > 0 and inset.height() > 0:
                painter.drawRoundedRect(inset, 4, 4)

            label = f"{rect.width()} × {rect.height()} px"
            label_rect = QRect(rect.left() + 8, rect.top() + 8, 132, 28)
            if rect.width() < 150:
                label_rect.moveLeft(rect.left())
                label_rect.moveTop(max(0, rect.top() - 34))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 28, 34, 210))
            painter.drawRoundedRect(label_rect, 7, 7)
            painter.setPen(QColor("#F6FCFF"))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
        else:
            hint = QRect(20, 20, min(max(390, self.width() - 40), 500), 42)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 28, 34, 185))
            painter.drawRoundedRect(hint, 10, 10)
            painter.setPen(QColor("#F6FCFF"))
            painter.drawText(hint.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             "محدوده متن را با ماوس بکشید   •   Esc برای لغو")
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = event.position().toPoint()
        rect = QRect(self._origin, self._current).normalized()
        if rect.width() >= 40 and rect.height() >= 18:
            # Selector-local coordinates are desktop coordinates on the primary display.
            rect.translate(self.geometry().topLeft())
            self._finished = True
            self.region_selected.emit({"left": rect.x(), "top": rect.y(), "width": rect.width(), "height": rect.height()})
            self.close()
        else:
            self._origin = None
            self._current = None
            self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._finished = True
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()


class DragHeader(QFrame):
    def __init__(self, window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class TranslationOverlay(QWidget):
    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.settings = settings
        self.english_expanded = True
        self.persian_expanded = True
        self.english_text = "در انتظار متن انگلیسی…"
        self.persian_text = "ترجمه پس از شناسایی متن نمایش داده می‌شود."
        self._section_animation: QParallelAnimationGroup | None = None
        self._build()
        self.apply_settings(settings)
        self._place_window()

    def _build(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 5, 5)
        self.panel = QFrame(self)
        self.panel.setObjectName("glassPanel")
        outer.addWidget(self.panel)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(8)

        self.header = DragHeader(self, self.panel)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        self.header_title = QLabel("ترجمه زنده")
        self.header_title.setStyleSheet("font-weight: 600; background: transparent; border: 0;")
        header_layout.addWidget(self.header_title)
        header_layout.addStretch(1)
        self.header_status = QLabel("آماده")
        self.header_status.setStyleSheet("background: transparent; border: 0;")
        header_layout.addWidget(self.header_status)
        self.hide_button = IconButton("x", "مخفی کردن پنل", self.header)
        self.hide_button.setFixedSize(30, 30)
        header_layout.addWidget(self.hide_button)
        layout.addWidget(self.header)

        self.english_header = QWidget(self.panel)
        english_header_layout = QHBoxLayout(self.english_header)
        english_header_layout.setContentsMargins(0, 0, 0, 0)
        self.english_label = QLabel("متن انگلیسی")
        english_header_layout.addWidget(self.english_label)
        english_header_layout.addStretch(1)
        self.english_toggle = IconButton("chevron-up", "بستن متن انگلیسی", self.english_header)
        self.english_toggle.setFixedSize(28, 28)
        english_header_layout.addWidget(self.english_toggle)
        layout.addWidget(self.english_header)

        self.english_body = QLabel(self.english_text)
        self.english_body.setWordWrap(True)
        self.english_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.english_body.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.english_body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.english_body)

        self.separator = QFrame(self.panel)
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFixedHeight(1)
        layout.addWidget(self.separator)

        self.persian_header = QWidget(self.panel)
        persian_header_layout = QHBoxLayout(self.persian_header)
        persian_header_layout.setContentsMargins(0, 0, 0, 0)
        self.persian_label = QLabel("ترجمه فارسی")
        persian_header_layout.addWidget(self.persian_label)
        persian_header_layout.addStretch(1)
        self.persian_toggle = IconButton("chevron-up", "بستن ترجمه فارسی", self.persian_header)
        self.persian_toggle.setFixedSize(28, 28)
        persian_header_layout.addWidget(self.persian_toggle)
        layout.addWidget(self.persian_header)

        self.persian_body = QLabel(self.persian_text)
        self.persian_body.setWordWrap(True)
        self.persian_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.persian_body.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.persian_body.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.persian_body)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.size_grip = QSizeGrip(self.panel)
        self.size_grip.setFixedSize(15, 15)
        bottom.addWidget(self.size_grip)
        layout.addLayout(bottom)

        self.hide_button.clicked.connect(self.hide)
        self.english_toggle.clicked.connect(self.toggle_english)
        self.persian_toggle.clicked.connect(self.toggle_persian)
        apply_shadow(self.panel, blur=26, y=5)

    def _place_window(self) -> None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app else None
        if screen is None:
            self.resize(int(self.settings.get("overlay_width", 650)), int(self.settings.get("overlay_height", 210)))
            return
        geometry = screen.availableGeometry()
        width = int(self.settings.get("overlay_width", 650))
        height = int(self.settings.get("overlay_height", 210))
        x = self.settings.get("overlay_x")
        y = self.settings.get("overlay_y")
        if x is None:
            x = geometry.x() + max(0, (geometry.width() - width) // 2)
        if y is None:
            y = geometry.y() + geometry.height() - height - 80
        self.setGeometry(int(x), int(y), width, height)

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        theme = THEMES.get(settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
        opacity = max(55, min(100, int(settings.get("opacity", 88))))
        radius = max(8, min(28, int(settings.get("corner_radius", 18))))
        font_size = max(12, min(28, int(settings.get("font_size", 17))))
        bg = QColor(theme["panel"])
        alpha = round(255 * opacity / 100)
        self.panel.setStyleSheet(
            f"QFrame#glassPanel {{ background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {alpha}); "
            f"border: 1px solid {theme['border']}; border-radius: {radius}px; }}"
        )
        all_labels = [self.header_title, self.english_label, self.persian_label, self.english_body, self.persian_body]
        for label in all_labels:
            label.setStyleSheet(f"color: {theme['text']}; background: transparent; border: 0;")
        self.header_status.setStyleSheet(f"color: {theme['muted']}; background: transparent; border: 0; font-size: 11px;")
        self.english_body.setStyleSheet(f"color: {theme['muted']}; background: transparent; border: 0; font-size: {max(11, font_size - 2)}px;")
        self.persian_body.setStyleSheet(f"color: {theme['text']}; background: transparent; border: 0; font-size: {font_size}px; font-weight: 500;")
        self.separator.setStyleSheet(f"background: {theme['separator']}; border: 0;")
        self.english_toggle.icon_name = "chevron-up" if self.english_expanded else "chevron-down"
        self.persian_toggle.icon_name = "chevron-up" if self.persian_expanded else "chevron-down"
        # Keep close/collapse controls glass-like and visible in both light and dark themes.
        for button in [self.hide_button, self.english_toggle, self.persian_toggle]:
            apply_glass_icon_button(button, theme)
        self.resize(int(settings.get("overlay_width", self.width())), int(settings.get("overlay_height", self.height())))

    def set_translation(self, original: str, translated: str, status: str = "ترجمه آماده") -> None:
        self.english_text = original
        self.persian_text = translated
        self.english_body.setText(original)
        self.persian_body.setText(translated)
        self.header_status.setText(status)

    def set_status(self, status: str) -> None:
        self.header_status.setText(status)

    def _animate_section_toggle(self, body: QLabel, button: IconButton, expanded: bool, section: str) -> None:
        """Collapse/expand a text section without blocking the UI or abrupt resizing."""
        if self._section_animation is not None:
            self._section_animation.stop()
            self._section_animation.deleteLater()
            self._section_animation = None
            # Normalize interrupted animations before beginning the next one.
            for item, is_open in ((self.english_body, self.english_expanded), (self.persian_body, self.persian_expanded)):
                item.setMinimumHeight(0)
                item.setMaximumHeight(16777215)
                item.setVisible(is_open)
            current_pos = self.pos()
            self.adjustSize()
            self.move(current_pos)

        theme = THEMES.get(self.settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
        name = "chevron-up" if expanded else "chevron-down"
        button.icon_name = name
        button.setIcon(icon(name, theme["text"]))
        button.setToolTip(("بستن " if expanded else "باز کردن ") + ("متن انگلیسی" if section == "english" else "ترجمه فارسی"))

        current = self.geometry()
        body.setMinimumHeight(0)
        if expanded:
            # Measure the natural height at the existing width, then animate from 0.
            body.setMaximumHeight(16777215)
            body.setVisible(True)
            self.panel.layout().activate()
            natural_height = max(1, body.sizeHint().height())
            body.setMaximumHeight(0)
            start_rect = QRect(current)
            end_rect = QRect(current.x(), current.y(), current.width(), current.height() + natural_height + 8)
            start_height, end_height = 0, natural_height
        else:
            natural_height = max(1, body.height(), body.sizeHint().height())
            body.setVisible(True)
            body.setMaximumHeight(natural_height)
            start_rect = QRect(current)
            end_rect = QRect(current.x(), current.y(), current.width(), max(128, current.height() - natural_height - 8))
            start_height, end_height = natural_height, 0

        group = QParallelAnimationGroup(self)
        body_animation = QPropertyAnimation(body, b"maximumHeight", group)
        body_animation.setDuration(155)
        body_animation.setStartValue(start_height)
        body_animation.setEndValue(end_height)
        body_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        window_animation = QPropertyAnimation(self, b"geometry", group)
        window_animation.setDuration(155)
        window_animation.setStartValue(start_rect)
        window_animation.setEndValue(end_rect)
        window_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(body_animation)
        group.addAnimation(window_animation)

        def finish() -> None:
            body.setMinimumHeight(0)
            body.setMaximumHeight(16777215)
            body.setVisible(expanded)
            self.setGeometry(end_rect)
            self._section_animation = None
            group.deleteLater()

        group.finished.connect(finish)
        self._section_animation = group
        group.start()

    def toggle_english(self) -> None:
        self.english_expanded = not self.english_expanded
        self._animate_section_toggle(self.english_body, self.english_toggle, self.english_expanded, "english")

    def toggle_persian(self) -> None:
        self.persian_expanded = not self.persian_expanded
        self._animate_section_toggle(self.persian_body, self.persian_toggle, self.persian_expanded, "persian")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings["overlay_x"] = self.x()
        self.settings["overlay_y"] = self.y()
        self.settings["overlay_width"] = self.width()
        self.settings["overlay_height"] = self.height()
        super().closeEvent(event)


class SettingsDialog(QDialog):
    settings_saved = Signal(dict)
    glossary_changed = Signal(dict)
    test_connection_requested = Signal(dict)

    def __init__(self, settings: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("تنظیمات مترجم")
        self.setObjectName("settingsDialog")
        self.setMinimumSize(560, 680)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build()
        self.theme_combo.currentTextChanged.connect(self._apply_theme_style)
        self.theme_combo.currentTextChanged.connect(self._clear_test_status)
        self.mode_combo.currentIndexChanged.connect(self._clear_test_status)
        self.online_provider_combo.currentIndexChanged.connect(self._clear_test_status)
        self._apply_theme_style()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("settingsContent")
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(18)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.setCurrentText(self.settings.get("theme", "Ivory Glass"))
        form.addRow("تم رنگی", self.theme_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Local AI · LM Studio", "local")
        self.mode_combo.addItem("Online · سرویس اینترنتی", "online")
        self.mode_combo.addItem("Offline · مدل مستقل", "offline")
        idx = self.mode_combo.findData(self.settings.get("mode", "local"))
        self.mode_combo.setCurrentIndex(max(0, idx))
        form.addRow("موتور ترجمه", self.mode_combo)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("افقی", "horizontal")
        self.orientation_combo.addItem("عمودی", "vertical")
        idx = self.orientation_combo.findData(self.settings.get("toolbar_orientation", "horizontal"))
        self.orientation_combo.setCurrentIndex(max(0, idx))
        form.addRow("جهت نوار ابزار", self.orientation_combo)

        self.toolbar_style_combo = QComboBox()
        self.toolbar_style_combo.addItem("روشن · دکمه روشن و آیکون تیره", "light")
        self.toolbar_style_combo.addItem("تاریک · دکمه تیره و آیکون روشن", "dark")
        self.toolbar_style_combo.addItem("هماهنگ با تم برنامه", "theme")
        saved_toolbar_style = self.settings.get("toolbar_style", "light")
        if saved_toolbar_style == "white":  # migrate settings saved by v0.2
            saved_toolbar_style = "light"
        idx = self.toolbar_style_combo.findData(saved_toolbar_style)
        self.toolbar_style_combo.setCurrentIndex(max(0, idx))
        form.addRow("ظاهر نوار ابزار", self.toolbar_style_combo)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(55, 100)
        self.opacity_slider.setValue(int(self.settings.get("opacity", 88)))
        self.opacity_value = QLabel(f"{self.opacity_slider.value()}٪")
        self.opacity_slider.valueChanged.connect(lambda value: self.opacity_value.setText(f"{value}٪"))
        opacity_wrap = QWidget()
        opacity_layout = QHBoxLayout(opacity_wrap)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_value)
        form.addRow("میزان مات‌بودن پنل", opacity_wrap)

        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(8, 28)
        self.radius_spin.setSuffix(" px")
        self.radius_spin.setValue(int(self.settings.get("corner_radius", 18)))
        form.addRow("گردی گوشه‌ها", self.radius_spin)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 28)
        self.font_spin.setSuffix(" px")
        self.font_spin.setValue(int(self.settings.get("font_size", 17)))
        form.addRow("اندازه فونت فارسی", self.font_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(300, 3000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(int(self.settings.get("scan_interval_ms", 700)))
        form.addRow("فاصله بررسی OCR", self.interval_spin)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("سریع · کمترین تأخیر", "fast")
        self.profile_combo.addItem("متعادل · پیشنهاد اولیه", "balanced")
        self.profile_combo.addItem("دقیق · تأیید چندباره متن", "accurate")
        profile_index = self.profile_combo.findData(self.settings.get("quality_profile", "balanced"))
        self.profile_combo.setCurrentIndex(max(0, profile_index))
        form.addRow("پروفایل OCR", self.profile_combo)

        self.stable_spin = QSpinBox()
        self.stable_spin.setRange(1, 5)
        self.stable_spin.setValue(int(self.settings.get("stable_reads", 2)))
        form.addRow("تعداد خواندن پایدار برای تأیید", self.stable_spin)

        self.profile_combo.currentIndexChanged.connect(self._apply_quality_profile)

        glossary_button = QPushButton("مدیریت واژه‌نامه و اصطلاحات…")
        glossary_button.clicked.connect(self._open_glossary)
        form.addRow("واژه‌نامه بازی", glossary_button)

        self.persistent_history = QCheckBox("ذخیره تاریخچه برای اجرای بعدی برنامه")
        self.persistent_history.setChecked(bool(self.settings.get("history_persistent", False)))
        form.addRow("حریم خصوصی", self.persistent_history)

        self.online_provider_combo = QComboBox()
        self.online_provider_combo.addItem("Google Translate · بدون کلید API", "google")
        self.online_provider_combo.addItem("LibreTranslate · سرویس با نشانی API", "libretranslate")
        provider_index = self.online_provider_combo.findData(self.settings.get("online_provider", "google"))
        self.online_provider_combo.setCurrentIndex(max(0, provider_index))
        form.addRow("ارائه‌دهنده آنلاین", self.online_provider_combo)

        self.online_url = QLineEdit(str(self.settings.get("libretranslate_url", "")))
        self.online_url.setPlaceholderText("https://your-libretranslate-server/translate")
        self.online_url.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.online_url.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("نشانی API برای LibreTranslate", self.online_url)

        self.online_key = QLineEdit(str(self.settings.get("libretranslate_api_key", "")))
        self.online_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.online_key.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.online_key.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.online_key.setPlaceholderText("اختیاری")
        form.addRow("کلید API آنلاین", self.online_key)

        self.online_proxy = QLineEdit(str(self.settings.get("online_proxy", "")))
        self.online_proxy.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.online_proxy.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.online_proxy.setPlaceholderText("اختیاری؛ برای نمونه http://127.0.0.1:7890")
        form.addRow("پروکسی HTTP/HTTPS (اختیاری)", self.online_proxy)

        self.lmstudio_url = QLineEdit(str(self.settings.get("lmstudio_base_url", "http://127.0.0.1:1234/v1")))
        self.lmstudio_url.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.lmstudio_url.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("نشانی LM Studio", self.lmstudio_url)

        self.lmstudio_model = QLineEdit(str(self.settings.get("lmstudio_model", "")))
        self.lmstudio_model.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.lmstudio_model.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lmstudio_model.setPlaceholderText("خالی باشد: مدل بارگذاری‌شده خودکار انتخاب می‌شود")
        form.addRow("شناسه مدل (اختیاری)", self.lmstudio_model)

        note = QLabel(
            "Google Translate در این برنامه از رابط وب بدون کلید استفاده می‌کند و ممکن است در برخی شبکه‌ها محدود شود. "
            "در صورت نیاز، پروکسی HTTP/HTTPS را در کادر مربوط وارد کن. LibreTranslate به نشانی سرویس قابل‌دسترسی "
            "(و گاهی کلید API) نیاز دارد. Local AI زمانی کار می‌کند که "
            "مدل در LM Studio بارگذاری و Local Server روشن باشد. Offline به بسته زبان نصب‌شده نیاز دارد."
        )
        note.setWordWrap(True)
        note.setStyleSheet("padding: 6px; background: transparent; border: 0;")
        form.addRow(note)

        self.test_connection_button = QPushButton("آزمایش اتصال موتور انتخاب‌شده")
        self.test_connection_button.clicked.connect(self._request_connection_test)
        form.addRow(self.test_connection_button)
        self.test_status_label = QLabel("آزمایش اتصال، یک عبارت کوتاه را ترجمه می‌کند و چیزی به تاریخچه اضافه نمی‌کند.")
        self.test_status_label.setWordWrap(True)
        self.test_status_label.setObjectName("connectionTestStatus")
        form.addRow(self.test_status_label)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("ذخیره تنظیمات")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("لغو")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _apply_theme_style(self, *_args) -> None:
        theme = THEMES.get(self.theme_combo.currentText(), THEMES["Ivory Glass"])
        self.setStyleSheet(f"""
            QDialog#settingsDialog {{ background: {theme['background']}; color: {theme['text']}; }}
            QWidget {{ color: {theme['text']}; }}
            QWidget#settingsContent {{ background: {theme['background']}; color: {theme['text']}; }}
            QLabel {{ color: {theme['text']}; background: transparent; }}
            QLineEdit, QComboBox, QSpinBox, QAbstractSpinBox {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 7px; padding: 5px; selection-background-color: {theme['separator']}; selection-color: {theme['text']}; }}
            QComboBox QAbstractItemView {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; selection-background-color: {theme['separator']}; selection-color: {theme['text']}; outline: 0; }}
            QCheckBox {{ color: {theme['text']}; spacing: 8px; }}
            QPushButton {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 7px 11px; }}
            QPushButton:hover {{ background: {theme['separator']}; color: {theme['text']}; }}
            QDialogButtonBox {{ color: {theme['text']}; }}
            QScrollArea {{ background: {theme['background']}; border: 0; }}
            QSlider::groove:horizontal {{ height: 4px; background: {theme['separator']}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {theme['accent']}; width: 14px; margin: -5px 0; border-radius: 7px; }}
            QToolTip {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; }}
            QLabel#connectionTestStatus {{ color: {theme['muted']}; padding: 5px; }}
        """)

    def _clear_test_status(self, *_args) -> None:
        """Remove a stale connection/test result when the selected engine changes."""
        theme = THEMES.get(self.theme_combo.currentText(), THEMES["Ivory Glass"])
        self.test_status_label.setText(
            "موتور تغییر کرد؛ برای دیدن وضعیت جدید، «آزمایش اتصال موتور انتخاب‌شده» را بزن."
        )
        self.test_status_label.setStyleSheet(
            f"color: {theme['muted']}; padding: 5px; background: transparent; border: 0;"
        )
        self.test_connection_button.setEnabled(True)

    def _request_connection_test(self) -> None:
        settings = self.current_settings()
        self.test_status_label.setText("در حال آزمایش؛ لطفاً چند لحظه صبر کن…")
        self.test_connection_button.setEnabled(False)
        self.test_connection_requested.emit(settings)

    def show_test_result(self, message: str, success: bool) -> None:
        self.test_status_label.setText(("✓  " if success else "✕  ") + message)
        theme = THEMES.get(self.theme_combo.currentText(), THEMES["Ivory Glass"])
        status_color = "#2E8B57" if success else ("#FF9A9A" if theme["text"].startswith("#F") or theme["text"].startswith("#E") else "#B42318")
        self.test_status_label.setStyleSheet(f"color: {status_color}; padding: 5px; background: transparent; border: 0;")
        self.test_connection_button.setEnabled(True)

    def current_settings(self) -> dict[str, Any]:
        settings = self.settings.copy()
        settings.update({
            "theme": self.theme_combo.currentText(),
            "mode": self.mode_combo.currentData(),
            "toolbar_orientation": self.orientation_combo.currentData(),
            "toolbar_style": self.toolbar_style_combo.currentData(),
            "opacity": self.opacity_slider.value(),
            "corner_radius": self.radius_spin.value(),
            "font_size": self.font_spin.value(),
            "scan_interval_ms": self.interval_spin.value(),
            "stable_reads": self.stable_spin.value(),
            "quality_profile": self.profile_combo.currentData(),
            "history_persistent": self.persistent_history.isChecked(),
            "online_provider": self.online_provider_combo.currentData(),
            "libretranslate_url": self.online_url.text().strip(),
            "libretranslate_api_key": self.online_key.text().strip(),
            "online_proxy": self.online_proxy.text().strip(),
            "lmstudio_base_url": self.lmstudio_url.text().strip().rstrip("/"),
            "lmstudio_model": self.lmstudio_model.text().strip(),
        })
        return settings

    def _apply_quality_profile(self, _index: int) -> None:
        profile = self.profile_combo.currentData()
        presets = {
            "fast": (450, 1),
            "balanced": (700, 2),
            "accurate": (1000, 3),
        }
        if profile in presets:
            interval, stable = presets[profile]
            self.interval_spin.setValue(interval)
            self.stable_spin.setValue(stable)

    def _open_glossary(self) -> None:
        glossary_settings = self.settings.copy()
        glossary_settings["theme"] = self.theme_combo.currentText()
        dialog = GlossaryDialog(self.settings.get("glossary", {}), glossary_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings["glossary"] = dialog.terms.copy()
            self.glossary_changed.emit(dialog.terms.copy())

    def _save(self) -> None:
        settings = self.current_settings()
        self.settings_saved.emit(settings)
        self.accept()


class HistoryDialog(QDialog):
    def __init__(self, history_manager, settings: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history_manager = history_manager
        self.settings = (settings or {}).copy()
        self.setObjectName("historyDialog")
        self.setWindowTitle("تاریخچه ترجمه‌ها")
        self.resize(680, 680)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build()
        self.apply_settings(self.settings)
        self.refresh()

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings.copy()
        theme = THEMES.get(self.settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
        self.setStyleSheet(f"""
            QDialog#historyDialog {{ background: {theme['background']}; color: {theme['text']}; }}
            QLabel {{ color: {theme['text']}; }}
            QLineEdit {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 8px; }}
            QScrollArea {{ background: {theme['background']}; border: 0; }}
            QPushButton {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 6px; }}
        """)
        if hasattr(self, "cards_container"):
            self.cards_container.setStyleSheet(f"background: {theme['background']};")
            apply_glass_icon_button(self.export_button, theme)
            apply_glass_icon_button(self.clear_button, theme)
            apply_glass_icon_button(self.close_button, theme)
            self.search_action.setIcon(icon("search", theme["text"]))
            self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("تاریخچه ترجمه‌ها")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        top.addWidget(title)
        top.addStretch(1)
        self.export_button = IconButton("download", "خروجی گرفتن", self)
        self.export_button.clicked.connect(self.export_history)
        top.addWidget(self.export_button)
        self.clear_button = IconButton("trash", "پاک‌کردن تاریخچه", self)
        self.clear_button.clicked.connect(self.clear_history)
        top.addWidget(self.clear_button)
        self.close_button = IconButton("x", "بستن تاریخچه", self)
        self.close_button.clicked.connect(self.close)
        top.addWidget(self.close_button)
        layout.addLayout(top)

        self.search = QLineEdit()
        self.search.setPlaceholderText("جست‌وجو در متن انگلیسی و ترجمه فارسی…")
        self.search_action = self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(2, 2, 2, 2)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll)

    def refresh(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        query = self.search.text().casefold().strip()
        matched = [entry for entry in self.history_manager.items if not query or query in entry["original"].casefold() or query in entry["translated"].casefold()]
        if not matched:
            empty = QLabel("هنوز ترجمه‌ای ثبت نشده است." if not query else "نتیجه‌ای پیدا نشد.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            theme = THEMES.get(self.settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
            empty.setStyleSheet(f"color: {theme['muted']}; padding: 30px; background: transparent; border: 0;")
            self.cards_layout.addWidget(empty)
        else:
            for entry in matched:
                self.cards_layout.addWidget(self._make_card(entry))
        self.cards_layout.addStretch(1)

    def _make_card(self, entry: dict[str, Any]) -> QWidget:
        card = QFrame()
        card.setObjectName("historyCard")
        theme = THEMES.get(self.settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
        card.setStyleSheet(f"QFrame#historyCard {{ border: 1px solid {theme['border']}; border-radius: 12px; background: {theme['panel']}; color: {theme['text']}; }}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 11, 13, 11)
        top = QHBoxLayout()
        stamp = QLabel(str(entry.get("timestamp", "")).replace("T", " "))
        stamp.setStyleSheet(f"color: {theme['muted']}; font-size: 11px; background: transparent; border: 0;")
        top.addWidget(stamp)
        top.addStretch(1)
        favorite = IconButton("bookmark-filled" if entry.get("favorite") else "bookmark", "حذف از نشان‌شده‌ها" if entry.get("favorite") else "نشان‌کردن", card)
        favorite.setFixedSize(30, 30)
        apply_glass_icon_button(favorite, theme)
        favorite.clicked.connect(lambda _checked=False, item_id=entry["id"], val=not entry.get("favorite", False): self._toggle_favorite(item_id, val))
        top.addWidget(favorite)
        layout.addLayout(top)

        original_header = QLabel("ENGLISH")
        original_header.setStyleSheet(f"color: {theme['muted']}; font-size: 10px; font-weight: 600; background: transparent; border: 0;")
        layout.addWidget(original_header)
        original = QLabel(entry["original"])
        original.setWordWrap(True)
        original.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        original.setAlignment(Qt.AlignmentFlag.AlignLeft)
        original.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        original.setStyleSheet(f"color: {theme['text']}; background: transparent; border: 0;")
        layout.addWidget(original)
        original_copy = IconButton("copy", "کپی متن انگلیسی", card)
        original_copy.setFixedSize(30, 30)
        apply_glass_icon_button(original_copy, theme)
        original_copy.clicked.connect(lambda _checked=False, value=entry["original"]: QApplication.clipboard().setText(value))
        layout.addWidget(original_copy, 0, Qt.AlignmentFlag.AlignLeft)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {theme['separator']};")
        layout.addWidget(divider)

        translated_header = QLabel("ترجمه فارسی")
        translated_header.setStyleSheet(f"color: {theme['muted']}; font-size: 10px; font-weight: 600; background: transparent; border: 0;")
        layout.addWidget(translated_header)
        translated = QLabel(entry["translated"])
        translated.setWordWrap(True)
        translated.setAlignment(Qt.AlignmentFlag.AlignRight)
        translated.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        translated.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        translated.setStyleSheet(f"color: {theme['text']}; background: transparent; border: 0;")
        layout.addWidget(translated)
        translated_copy = IconButton("copy", "کپی ترجمه فارسی", card)
        translated_copy.setFixedSize(30, 30)
        apply_glass_icon_button(translated_copy, theme)
        translated_copy.clicked.connect(lambda _checked=False, value=entry["translated"]: QApplication.clipboard().setText(value))
        layout.addWidget(translated_copy, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _toggle_favorite(self, item_id: str, value: bool) -> None:
        self.history_manager.set_favorite(item_id, value)
        self.refresh()

    def clear_history(self) -> None:
        answer = QMessageBox.question(self, "پاک‌کردن تاریخچه", "تمام ترجمه‌های ثبت‌شده در تاریخچه پاک شوند؟")
        if answer == QMessageBox.StandardButton.Yes:
            self.history_manager.clear()
            self.refresh()

    def export_history(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "ذخیره تاریخچه", "glass_translator_history.json", "JSON (*.json);;CSV (*.csv);;Text (*.txt)"
        )
        if not path:
            return
        entries = self.history_manager.items
        try:
            suffix = Path(path).suffix.lower()
            if suffix == ".csv":
                with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["timestamp", "mode", "original", "translated", "favorite"])
                    writer.writeheader()
                    for entry in entries:
                        writer.writerow({key: entry.get(key) for key in writer.fieldnames})
            elif suffix == ".txt":
                with open(path, "w", encoding="utf-8") as handle:
                    for entry in entries:
                        handle.write(f"[{entry['timestamp']}]\nEN: {entry['original']}\nFA: {entry['translated']}\n\n")
            else:
                if not suffix:
                    path += ".json"
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(entries, handle, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "خروجی تاریخچه", "تاریخچه ذخیره شد.")
        except OSError as exc:
            QMessageBox.warning(self, "خطا", f"ذخیره فایل ناموفق بود: {exc}")


class GlossaryDialog(QDialog):
    """Small local glossary for character names, locations, items and recurring phrases."""

    def __init__(self, terms: dict[str, str] | None = None, settings: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.terms = dict(terms or {})
        self.settings = (settings or {}).copy()
        self.setObjectName("glossaryDialog")
        self.setWindowTitle("واژه‌نامه بازی")
        self.resize(540, 520)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build()
        self._apply_theme_style()
        self._refresh()

    def _apply_theme_style(self) -> None:
        theme = THEMES.get(self.settings.get("theme", "Ivory Glass"), THEMES["Ivory Glass"])
        self.setStyleSheet(f"""
            QDialog#glossaryDialog {{ background: {theme['background']}; color: {theme['text']}; }}
            QLabel {{ color: {theme['text']}; }}
            QLineEdit, QListWidget {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 7px; }}
            QPushButton {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 7px 10px; }}
            QPushButton:hover {{ background: {theme['background']}; }}
        """)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel("برای یکدست‌ماندن ترجمه، معادل ثابت نام‌ها و اصطلاحات را وارد کن.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.english_input = QLineEdit()
        self.english_input.setPlaceholderText("عبارت انگلیسی، مثل: Sites of Grace")
        self.english_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.english_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.english_input)

        self.persian_input = QLineEdit()
        self.persian_input.setPlaceholderText("معادل فارسی، مثل: مکان‌های لطف")
        layout.addWidget(self.persian_input)

        row = QHBoxLayout()
        add_button = QPushButton("افزودن یا به‌روزرسانی")
        add_button.clicked.connect(self._add_term)
        row.addWidget(add_button)
        remove_button = QPushButton("حذف مورد انتخاب‌شده")
        remove_button.clicked.connect(self._remove_selected)
        row.addWidget(remove_button)
        layout.addLayout(row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._load_selected)
        layout.addWidget(self.list_widget, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("ذخیره واژه‌نامه")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("لغو")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh(self) -> None:
        self.list_widget.clear()
        for english, persian in sorted(self.terms.items(), key=lambda item: item[0].casefold()):
            item = QListWidgetItem(f"{english}  →  {persian}")
            item.setData(Qt.ItemDataRole.UserRole, english)
            self.list_widget.addItem(item)

    def _add_term(self) -> None:
        english = self.english_input.text().strip()
        persian = self.persian_input.text().strip()
        if not english or not persian:
            QMessageBox.information(self, "واژه‌نامه", "هر دو فیلد انگلیسی و فارسی باید تکمیل شوند.")
            return
        self.terms[english] = persian
        self.english_input.clear()
        self.persian_input.clear()
        self._refresh()

    def _remove_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            english = item.data(Qt.ItemDataRole.UserRole)
            self.terms.pop(english, None)
            self._refresh()

    def _load_selected(self, item: QListWidgetItem) -> None:
        english = item.data(Qt.ItemDataRole.UserRole)
        self.english_input.setText(english or "")
        self.persian_input.setText(self.terms.get(english, ""))
