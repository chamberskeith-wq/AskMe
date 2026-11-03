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


class ErrorPopup(Popup):
    """
    Reusable error popup dialog.

    Args:
        message (str): Error message to display.
        title (str): Optional popup title.
    """

    def __init__(self, message: str, title: str = "Error", **kwargs):
        super().__init__(**kwargs)

        self.title = title
        self.size_hint = (0.7, 0.4)
        self.auto_dismiss = False

        logger.warning("ErrorPopup opened: %s", message)

        self._build_ui(message)

    # --------------------------------------------------
    # Build UI
    # --------------------------------------------------

    def _build_ui(self, message: str):

        layout = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=10
        )

        message_label = Label(
            text=message,
            halign="center",
            valign="middle",
            text_size=(400, None)
        )

        layout.add_widget(message_label)

        ok_button = Button(
            text="OK",
            size_hint_y=None,
            height=40
        )

        ok_button.bind(on_release=lambda *_: self.dismiss())

        layout.add_widget(ok_button)

        self.content = layout
