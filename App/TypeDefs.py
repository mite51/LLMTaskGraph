from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from Serializable import ISerializable

class TaskNodeState(str,Enum):
    Queued = 0
    Ready = 1
    Executing = 2
    Complete = 3
    Error = 4

class ResponseEntryType(str,Enum):
    CHAT = 1
    FILE = 2
    INSTRUCTION = 3

class SessionEntry(ISerializable):
    def __init__(self, sender: str = "NONAME", content: str = "NOT INTENTIONALLY BLANK", entry_type: ResponseEntryType = ResponseEntryType.CHAT, metadata: Optional[Dict] = None):
        self.sender = sender
        self.content = content
        self.entry_type = entry_type
        self.metadata = metadata or {}
        self.time_stamp = datetime.now()
        self.include_in_context = True
        self.include_in_display = True

class TaskContext(ISerializable):
    """
    The "TaskContext" is a container for the current state of the task graph execution
    "node_stack" is a list of indexes that represent the current node in the task graph
    "variable_stack" is a dictionary of variables that in scoped 
    """    
    def __init__(self, project: 'Project'=None, task: 'Task'=None):
        self.project: 'Project' = project
        self.task: 'Task' = task
        self.node_stack: List[int] = []
        self.variable_stack: Dict[str, Any] = {} # node scoped varaible stack

    _exclude_from_properties = ['project', 'task']
    _readonly_properties = ['node_stack', 'variable_stack']
    _exclude_from_usd = ['project', 'task']
    _exclude_from_json = ['project', 'task']

    # because the node stack is a list of indexes, we need to walk the graph to get the current node
    def get_current_node(self):# -> TaskNode:
        result = self.task.task_graph_root
        for node_index in reversed(self.node_stack):
            result = result.children[node_index]
        return result
    
    def get_node(self, node_stack: List[int]):
        result = self.task.task_graph_root
        for node_index in reversed(node_stack):
            result = result.children[node_index]
        return result

    # this function will advance the node stack to the next node
    def advance_node(self) -> bool:
        if len(self.node_stack) >= 0:
            current_node = self.get_current_node()
            if len(current_node.children):
                self.node_stack.append(0)
                return True
            while(len(self.node_stack) > 0):
                current_node = self.get_current_node()
                child_index = self.node_stack.pop()
                parent_node = self.get_current_node()
                if (child_index+1) < len(parent_node.children):
                    child_index += 1
                    self.node_stack.append(child_index)
                    # Ensure scoped_variables is empty
                    new_node = self.get_current_node()
                    new_node.scoped_variables.clear() 
                    return True
                else:
                    # Clear variables owned by this node
                    self.clear_node_variables(current_node)
        return False

    def set_variable(self, name: str, value: Any):
        current_node = self.get_current_node()
        if current_node:
            if name not in self.variable_stack:
                current_node.scoped_variables.append(name)
        self.variable_stack[name] = value

    def get_variable(self, name: str) -> Any:
        if name in self.variable_stack:
            return self.variable_stack[name]
        raise KeyError(f"Variable '{name}' not found")

    def clear_node_variables(self, node):# : TaskNode):
        for var_name in node.scoped_variables:
            if var_name in self.variable_stack:
                del self.variable_stack[var_name]
        node.scoped_variables.clear()            