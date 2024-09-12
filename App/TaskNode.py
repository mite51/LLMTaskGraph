from Serializable import ISerializable
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List
from PyQt5.QtWidgets import QPushButton
from TypeDefs import TaskContext, TaskNodeState
from io import StringIO
import sys
#============================================================================
class TaskNode(ABC, ISerializable):
    """
    TaskNode's are the aggregated tasks executed when completing a task
    Conceptually these will be collection point for context data to help LLMs break a task down further
    At the lowest level it should be LLMs doing the work, being asked to write code, etc
    'children' : aggregated subtasks, or execution task nodes
    'inputs' and 'outputs' should reflect the data required and produced by the node, 
        -used to validate the graph 
        -allow for context reduction, a future feature to reference subtask trees, in those cases only the top level input/outputs are needed
        -allow LLM nodes to use these for format specifiers in prompts
    """
    def __init__(self):
        self.type: str = self.__class__.__name__
        self.name: str = ""
        self.description: str = ""
        self.version: str = ""
        self.state: TaskNodeState = TaskNodeState.Queued
        # tags will be used for search, to be implemented
        self.tags: List[str] = []        

        self.children: List[TaskNode] = []
        # scoped_variables is for the task graph execution track variable scope
        self.scoped_variables: List[str] = []
        # inputs specifiy the data expected by the node, to be specified during graph construction
        self.inputs: List[str] = []
        # inputs specifiy the data produced by the node, to be specified during graph construction
        self.output: List[str] = []

        self._rewind_button: QPushButton = None
        self._step_button: QPushButton = None
        self._play_button: QPushButton = None
    
    def add_child(self, child: 'TaskNode'): 
        self.children.append(child)

    @abstractmethod
    def execute(self, task_context : TaskContext):
        pass

    def set_state(self, new_state: TaskNodeState):
        self.state = new_state
        self.update_button_state(new_state)

    def set_buttons(self, rewind_button, step_button, play_button):
        self._rewind_button = rewind_button
        self._step_button = step_button
        self._play_button = play_button
        self.update_button_state(self.state)

    def update_button_state(self, new_state: TaskNodeState):
        if self._rewind_button is None or self._step_button is None or self._play_button is None:
            return
                
        if new_state == TaskNodeState.Complete:
            self._rewind_button.setHidden(False)
            self._step_button.setHidden(True)
            self._play_button.setHidden(True)
        elif new_state == TaskNodeState.Ready:
            self._rewind_button.setHidden(True)
            self._step_button.setHidden(False)
            self._play_button.setHidden(False)               
        else:
            self._rewind_button.setHidden(True)
            self._step_button.setHidden(True)
            self._play_button.setHidden(True)

    _exclude_from_properties = ['children', 'scoped_variables'],
    _readonly_properties = ['name', 'type','inputs', 'output']
    _exclude_from_usd = ['type', 'scoped_variables']
    _exclude_from_json = ['type', 'scoped_variables']

#============================================================================
class TaskNode_Container(TaskNode):
    """
    A simple container node
    """
    def __init__(self):
        super().__init__()

    def execute(self, task_context : TaskContext):
        self.set_state(TaskNodeState.Complete)

#============================================================================
class TaskNode_ProjectFile(TaskNode):
    """
    Read a file from the project manifest into a global variable
    """
    def __init__(self):
        super().__init__()
        self.variable_name = ""
        self.file_name = ""
        #self.start_offset = ""
        #self.end_offset = ""

    def execute(self, task_context : TaskContext):
        # TODO
        pass

#============================================================================
class TaskNode_Python(TaskNode):
    """
    TaskNode are the aggregated tasks executed when completing a task
    Predominately these will be collection point for LLMs used to break a task down further
    At the lowest level it should be LLMs doing the work, being asked to write code
    The leaf ouput will ultimately be anything generated/modified files

    task_context will contain additional data needed composed by other node used to execute the task
    like the target LLM, a python function to run, or the command line tool to run
    """
    def __init__(self):
        super().__init__()
        self.python_code = ""

    def execute(self, task_context : TaskContext):
        self.set_state(TaskNodeState.Executing)
        print(f"calling exec() with self.python_code:\n{self.python_code}")
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        try:
            # https://stackoverflow.com/questions/2904274/globals-and-locals-in-python-exec
            d = dict(locals(), **globals())
            exec(self.python_code, d, d)
            output = mystdout.getvalue()
            # the output should go into a chat session entry or something eventually
            print(output)
        except Exception as e:
            sys.stdout = old_stdout
            self.set_state(TaskNodeState.Error)
            
            print(f"Error executing python code: {e}")
            return            
        self.set_state(TaskNodeState.Complete)
        sys.stdout = old_stdout

#============================================================================
class TaskNode_RequestUserAssistance(TaskNode):
    """
    For tasks that the LLM models is struggling with or otherwise cannot handle, request user assistance
    The node should only contain user created nodes, or the user can manually do the task and mark it complete
    """    
    def __init__(self):
        super().__init__()

    def execute(self, task_context : TaskContext):
        # TODO
        #pop up a dialog asking for the information
        #This may take the form of an LLM session and or a user making manual modifications to the task graph
        pass

#============================================================================
class TaskNode_SearchProjectData(TaskNode_Python):
    def __init__(self):
        super().__init__()
        # python code used to search
        self.python_code = ""

#============================================================================
    
        
