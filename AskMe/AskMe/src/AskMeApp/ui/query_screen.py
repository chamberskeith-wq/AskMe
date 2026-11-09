'''
Created on Feb 12, 2026

@author: keith.chambers
'''

# setup logging for this module
import logging
logger = logging.getLogger(__name__)

# -----------------------------
# imports
# -----------------------------
# Kivy imports
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.utils import colormap 
from kivy.clock import Clock

#===============================================================================
# QueryScreen  - linked to entry in kivy file
#===============================================================================
class QueryScreen(Screen):
    """ This is the main screen for entering queries and seeing the responses. screen, linked by kivy magic to UI elements
    
    """

    #class linked through kivi magic to the UI
    #class names are reflected in the .kv file
        
    # called after all the kv rules have been applied
    def on_kv_post(self, base):

        self.ids.prompt_label.bind(
            texture_size=lambda *a:
                Clock.schedule_once(
                    lambda dt: self._scroll_bottom("prompt"), 0
                )
        )

        self.ids.response_label.bind(
            texture_size=lambda *a:
                Clock.schedule_once(
                    lambda dt: self._scroll_bottom("response"), 0
                )
        )
    #scroll to the bottom of the box
    def _scroll_bottom(self, which):

        if which == "prompt":
            self.ids.prompt_scroll.scroll_to(self.ids.prompt_label, padding=0, animate=False)
        elif which == "response":
            self.ids.response_scroll.scroll_to(self.ids.response_label, padding=0, animate=False)

    # called when the submit button is pressed
    def submit_inputs(self):
        
        #use APP instead of globals
        app = App.get_running_app()

        # setup the query and context
        app.my_prompt.query = self.ids.question.text 
        app.my_prompt.context = self.ids.context.text
        
        #display the prompt
        self.ids.prompt_label.color = colormap["black"]    
        self.ids.prompt_label.text = app.my_prompt.prompt

        
        # Schedule scroll to bottom after the next frame, a short delay if needed
        Clock.schedule_once(lambda dt: self._scroll_bottom("prompt"), 0)        
        Clock.schedule_once(lambda dt: self._scroll_bottom("response"), 0)    

        # Call the LLM client with the prompt
        ans = app.llm.call(app.my_prompt)       
        self.ids.response_label.text = ans

