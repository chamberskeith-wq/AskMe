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

    # ---------------------------------------------------------
    # Submit button
    # ---------------------------------------------------------
    # called when the submit button is pressed
    def submit_inputs(self):
    
        app = App.get_running_app()
        question = self.ids.question.text.strip()
    
        if not question:
            self.ids.response_label.text = "Please enter a question."
            return
    
        try:
            # 1. Retrieve records from ChromaDB
            retrieval_results = app.retrieval.search_combined(
                query_text=question,
                top_k_per_type=10,
                deduplicate_labs=False
            )
    
            logger.info(
                "Retrieval counts: %s",
                retrieval_results["counts"]
            )
    
            # 2. Assemble context
            assembly = app.context_assembler.assemble(
                retrieval_results
            )
    
            context = assembly["context"]
    
            logger.info(
                "Context assembly statistics: %s",
                assembly["stats"]
            )
    
            # 3. Update prompt
            app.my_prompt.query = question
            app.my_prompt.context = context
            app.my_prompt.make_dirty()
    
            # 4. Display what will actually be sent
            self.ids.context.text = context
            self.ids.prompt_label.color = colormap["black"]
            self.ids.prompt_label.text = app.my_prompt.prompt
    
            # 5. Call Gemini
            if not context.strip():
                self.ids.response_label.text = (
                    "No relevant documents were retrieved. "
                    "Please check the database and ingestion."
                )
                return
    
            answer = app.llm.call(app.my_prompt)
            self.ids.response_label.text = answer
    
        except Exception as exc:
            logger.exception("Question submission failed")
            self.ids.response_label.text = (
                f"An error occurred while processing your question:\n{exc}"
            )
    
        finally:
            Clock.schedule_once(
                lambda dt: self._scroll_bottom("prompt"), 0
            )
            Clock.schedule_once(
                lambda dt: self._scroll_bottom("response"), 0
            )