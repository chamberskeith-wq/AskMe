'''
Created on Feb 17, 2026

@author: keith.chambers
'''
# setup logging for this module
import logging
logger = logging.getLogger(__name__)

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

class ConfirmationPopup(Popup):
    """
    Generic confirmation dialog.

    Args:
        message (str)
        on_confirm (callable)
        on_cancel (callable | None)
        title (str)
        confirm_text (str)
        cancel_text (str)
    """



    def __init__(
        self,
        message,
        on_confirm,
        on_cancel=None,
        title="Confirm",
        confirm_text="Yes",
        cancel_text="Cancel",
        **kwargs
    ):
        super().__init__(title=title, size_hint=(0.7, 0.4), **kwargs)

        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        content = BoxLayout(orientation="vertical", spacing=10, padding=10)

        label = Label(text=message, halign="center")
        content.add_widget(label)

        button_row = BoxLayout(size_hint_y=None, height=40, spacing=5)

        confirm_btn = Button(text=confirm_text)
        confirm_btn.bind(on_release=self._confirm)

        cancel_btn = Button(text=cancel_text)
        cancel_btn.bind(on_release=self._cancel)

        button_row.add_widget(confirm_btn)
        button_row.add_widget(cancel_btn)

        content.add_widget(button_row)

        self.content = content

    def _confirm(self, instance):
        if callable(self._on_confirm):
            self._on_confirm()
        self.dismiss()

    def _cancel(self, instance):
        if callable(self._on_cancel):
            self._on_cancel()
        self.dismiss()
