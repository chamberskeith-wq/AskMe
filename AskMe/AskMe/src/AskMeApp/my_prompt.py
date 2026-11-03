'''
Created on Sep 8, 2025

@author: keith.chambers
'''

# setup logging for this module
import logging
logger = logging.getLogger(__name__)


class MyPrompt(object):
 
    '''Generic prompting class for creating LLM prompts
    
    Properties 
    query (string) : the prompts query. Get and Set
    context (string) : the prompts context. Get and Set
    prompt (string) : the generated prompt. Get
    answer (string) : the last answer. Get and Set
    dirty (boolean) : has the prompt changed since the answer was set. Get only, with a method to clear
    chat (boolean) : true while in a chat with the LLM, setting to false starts a new chat
    
    Methods
    None
    
    
    Instruction (first), Question, Input data, examples
    <|endofprompt|> allow you to add a completion task 
    <begin> and <end> mark an opinion on GPT models
    '''

    # --------------------------------------------------------------------------------------
    #constructor
    
    def __init__(self, q, c):
        '''
        Constructor : Initialize with the supplied query and context
        '''
        self._query = q
        self._context = c
        self._chat = False
        self._chat_session = None
        self._prompt = ""
        self._answer = ""

    # --------------------------------------------------------------------------------------
    #setters and getter
    
    # getter and setter for query 
    @property
    def query(self):
        '''The entered query'''
        
        return self._query

    @query.setter   
    def query(self,value):
        
        if not (self._query == value): 
            self._query = value
            self._prompt = self._build_prompt()
         
    # getter and setter for context 
    @property
    def context(self):
        
        '''The entered context'''
        
        return self._context
    
    @context.setter
    def context(self, value):
        
        if not (self._context == value): 
            self._context = value
            self._prompt = self._build_prompt()
        
    # getter for prompt 
    @property
    def prompt(self):
        
        '''The generated prompt'''
        
        return self._prompt
    
    # getter and setter for answer 
    @property
    def answer(self):
        
        '''The current answer to the prompt''' 
        
        return self._answer
    
    @answer.setter
    def answer(self, value):
        
        self._answer = value
        
    # getter and setter for dirty 
    @property
    def dirty(self) -> bool:
        
        '''The current answer to the prompt''' 
        
        return self._answer == ""
    
    # dirty is read only, and cannot be set directly
    def make_dirty(self) -> bool:
        
        self._answer = ""
    
    # getter and setter for _chat 
    @property
    def chat(self):
        
        '''True if prompt is in chat mode''' 
        
        return self._chat
    
    @chat.setter
    def chat(self, value):
        
        self._chat = value
        self._answer = ""
        logger.info(f"Chat is {self._chat}")
        
        if not value:
            self._chat_session = None

    @property
    def chat_session(self):
        """Provider-specific chat session (LLM client owns lifecycle)"""
        return self._chat_session

    @chat_session.setter
    def chat_session(self, session) -> None:
        self._chat_session = session
    
    
    # --------------------------------------------------------------------------------------
    # private methods
    
    #build the prompt string
    def _build_prompt(self):
        
        if self._context == "":
            p = f"[Query: {self._query}]"
        else:
            p = f"[Query: {self._query}]\n[Context: {self._context}]"
        
        self._answer = ""
        
        return p 
        
        