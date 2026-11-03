'''
Created on Feb 12, 2026

@author: keith.chambers
'''
# setup logging for this module
import logging
logger = logging.getLogger(__name__)

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button


class MessagePopup(Popup):
    """Reusable message popup dialog.
    Args:
        message (str): Message to display.
        level (str): 'error', 'warning', 'info', or 'question'
        title (str): Optional override for popup title.
        on_confirm (callable): Optional confirm callback.
        on_cancel (callable): Optional cancel callback.
        confirm_text (str): Confirm button text.
        cancel_text (str): Cancel button text.
    """

    LEVEL_STYLES = {
        "error": {
            "title": "Error",
            "log": logging.ERROR,
            "color": (1, 0.3, 0.3, 1),
            "icon": "\u2716"   # ✖
        },
        "warning": {
            "title": "Warning",
            "log": logging.WARNING,
            "color": (1, 0.7, 0.2, 1),
            "icon": "\u26A0"   # ⚠
        },
        "info": {
            "title": "Information",
            "log": logging.INFO,
            "color": (0.3, 0.7, 1, 1),
            "icon": "\u2139"   # ℹ
        },
        "question": {
            "title": "Question",
            "log": logging.INFO,
            "color": (0.3, 0.7, 1, 1),
            "icon": "\u2047"   # ❓
        }
    }

    def __init__(
        self,
        message: str,
        level: str = "error",
        title: str = None,
        on_confirm=None,
        on_cancel=None,
        confirm_text="OK",
        cancel_text="Cancel",
        **kwargs
    ):
        
        super().__init__(**kwargs)

        style = self.LEVEL_STYLES.get(level, self.LEVEL_STYLES["error"])

        self.title = title or style["title"]
        self.size_hint = (0.6, 0.35)
        self.auto_dismiss = False

        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._confirm_text = confirm_text
        self._cancel_text = cancel_text

        logger.log(style["log"], "%s popup opened: %s", level.upper(), message)

        self._build_ui(message, style)

    # --------------------------------------------------
    # Build UI
    # --------------------------------------------------

    def _build_ui(self, message: str, style: dict):

        root_layout = BoxLayout(
            orientation="vertical",
            padding=15,
            spacing=15
        )

        # --- Icon + Message Row ---
        message_row = BoxLayout(
            orientation="horizontal",
            spacing=10
        )

        icon_label = Label(
            text=style["icon"],
            font_name="assets/fonts/DejaVuSans.ttf",
            font_size="32sp",
            size_hint_x=None,
            width=50
        )

        message_label = Label(
            text=message,
            halign="left",
            valign="middle",
            color=style["color"],
             size_hint_x=1,
             size_hint_y=None
        )

        message_label.bind(
            width=lambda instance, value: setattr(instance, "text_size", (value, None))
        )
        
        message_label.bind(
            texture_size=lambda instance, value: setattr(instance, "height", value[1]))
            
        message_row.add_widget(icon_label)
        message_row.add_widget(message_label)

        root_layout.add_widget(message_row)


        # --- Button Row ---
        button_row = BoxLayout(
            size_hint_y=None,
            height=40,
            spacing=10
        )

        # If confirm callback provided → confirmation dialog
        if self._on_confirm:

            confirm_btn = Button(text=self._confirm_text)
            confirm_btn.bind(on_release=self._confirm)

            button_row.add_widget(confirm_btn)

            if self._on_cancel:
                cancel_btn = Button(text=self._cancel_text)
                cancel_btn.bind(on_release=self._cancel)
                button_row.add_widget(cancel_btn)

        else:
            # Standard OK popup
            ok_button = Button(text="OK")
            ok_button.bind(on_release=lambda *_: self.dismiss())
            button_row.add_widget(ok_button)

        root_layout.add_widget(button_row)

        self.content = root_layout

    # --------------------------------------------------
    # Actions
    # --------------------------------------------------

    def _confirm(self, *_):
        if callable(self._on_confirm):
            self._on_confirm()
        self.dismiss()

    def _cancel(self, *_):
        if callable(self._on_cancel):
            self._on_cancel()
        self.dismiss()
