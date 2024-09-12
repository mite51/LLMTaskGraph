from PyQt5.QtWidgets import QApplication
from Serializable import ISerializable
from TaskNode import TaskNode, TaskNode_Container
from TaskNode_LLM import TaskNode_LLM 
from enum import IntEnum
from typing import Any, Dict, List
from TypeDefs import SessionEntry, ResponseEntryType, TaskContext, TaskNodeState

import Globals

DEBUG = True

class TaskPhase(IntEnum):
    Spec = 0,
    ListSteps = 1,
    BuildGraph = 2,
    CreateBranch = 3,
    ExecuteGraph = 4,
    Verify = 5,
    Refine = 6,
    Commit = 7,
    Complete = 8,
    TEST = 9

phase_prompt_tags = {
    TaskPhase.Spec: ["user instruction","model instruction","task details"],
    TaskPhase.ListSteps: ["task steps"],
    TaskPhase.BuildGraph: ["prompt summaries", "file creation", "build graph", "code generation", 
                           "framework api", "framework documentation", "project manifest", "create graph"],
    TaskPhase.CreateBranch: [""],
    TaskPhase.ExecuteGraph: ["file creation", "code generation", "project manifest"],
    TaskPhase.Verify: [""],
    TaskPhase.Refine: [""],#Fixes, testing, review, performance improvements, edge cases, error handling, logic improvements
    TaskPhase.Commit: [""],
    TaskPhase.Complete: [""],
    TaskPhase.TEST: [""],
}

class Task(ISerializable):
    """
    The "TASK" super class is the base class for automating any software task using LLMs
    It is composed of: tags, session, task graph
    tags are the searchable meta data used to store and retreive this Task from a database
    The session is the ongoing log with the LLM to construct the graph
    The task graph is a node graph of aggregate tasks to complete, more llm sessions and/or more functional/application nodes
    """    
    def __init__(self, name: str = "NO NAME", project = None):
        self.name: str = name
        self.project = project
        self.initial_prompt_tags: List[str] = ["HttpServerTestPrompt"]# ["identity", "conversation style", "User info", "project description", "project manifest"]
        self.task_phase: TaskPhase = TaskPhase.Spec
        self.branch_name: str = "DEFAULT_BRANCH_NAME"
        self.commit_id: str = "INVALID_COMMIT_ID"
        self.tags: List[str] = []
        self.description: str = ""
        self.content_version: str = "" #for when the graph data changes
        self.graph_version: str = "" #for when the code changes
        self.task_graph_root: TaskNode = None
        self.LLM_interface: TaskNode_LLM = TaskNode_LLM()
        self.LLM_interface.name = f"{self.name}_tasksession"
        self.LLM_interface.set_session_callback(self.session_callback)
        self.LLM_interface.set_session_filter_callback(self.session_filter_callback)

        self.task_context: TaskContext = TaskContext(self.project, self)

        self.initialize_phase()
                
    _exclude_from_properties = ['project', 'task_graph_root', 'commit_id', 'LLM_interface']
    _readonly_properties = ['name','task_phase', 'branch_name', 'content_version', 'graph_version']    
    _exclude_from_usd = ['project']
    _exclude_from_json = ['project']

    def get_display_name(self):
        return f"{self.name}[{self.task_phase}]"

    def add_prompts_by_tags(self, tags: List[str]) -> int:
        context_prompts_added = 0
        discovered_prompts = Globals.find_prompts(tags)
        for prompt in discovered_prompts:
            self.LLM_interface.add_session_entry("System", prompt.prompt, 
                                                 prompt.include_in_context, 
                                                 prompt.include_in_display, 
                                                 entry_type=ResponseEntryType.INSTRUCTION,  
                                                 metadata={"task_phase": self.task_phase})
            if prompt.include_in_context:
                context_prompts_added += 1
        return context_prompts_added

    def add_phase_prompt(self) -> int:
        return self.add_prompts_by_tags(phase_prompt_tags[self.task_phase])

    def initialize_phase(self):
        self.add_prompts_by_tags(self.initial_prompt_tags)
        self.task_phase = TaskPhase.Spec   
        self.add_phase_prompt()

    def advance_phase(self):
        if self.task_phase < TaskPhase.Complete:
            self.task_phase = TaskPhase(self.task_phase.value + 1)
            Globals.ProjectManagerWindow.projects_tree.request_refresh_taskgraph(self)
            context_additions = self.add_phase_prompt()

            if DEBUG:
                print(f"[DEBUG] advance_phase {self.task_phase}")  

            if context_additions:
                self._continue_session = True

    def step_tasknode(self):
        current_node : TaskNode = self.task_context.get_current_node()
        if current_node != None and current_node.state == TaskNodeState.Ready:
            current_node.execute(self.task_context)
            self.task_context.advance_node()
            current_node : TaskNode = self.task_context.get_current_node()
            current_node.set_state(TaskNodeState.Ready)
        else:
            print(f"Unexpected error stepping tasknode: {current_node}")

    def play_taskgraph(self):
        current_node : TaskNode = self.task_context.get_current_node()                    
        if current_node and current_node.state == TaskNodeState.Ready:
            while(True):
                self.step_tasknode()
                current_node : TaskNode = self.task_context.get_current_node()
                if current_node == None or current_node != TaskNodeState.Complete:
                    break

    def handle_session_response(self, response_session_entries: List[SessionEntry]) -> bool:
        if self.task_phase < TaskPhase.Complete:
            can_proceed = False
            retry = False
            response_handled = False

            if self.task_phase == TaskPhase.BuildGraph:
                response_handled = True

                # search from the end to the previous session entry, if there is a task graph, use it
                for session_entry in response_session_entries:
                    if session_entry.entry_type == ResponseEntryType.FILE and session_entry.metadata['type'] == "task_graph":
                        retry = False
                        can_proceed = True
                        try:
                            self.task_graph_root = TaskNode_Container.from_json(session_entry.content)
                            self.task_graph_root.set_state(TaskNodeState.Ready)
                            retry = False
                            Globals.ProjectManagerWindow.projects_tree.request_refresh_taskgraph(self)
                            break
                        except Exception as e:
                            can_proceed = False
                            retry = True
                            print(f"Unexpected error serializing task_graph: {e}")
                        break                            

            if can_proceed:
                self.advance_phase()
            elif retry:
                self.LLM_interface.add_session_entry("task_manager", "something went wrong please try again", True, False,  metadata={"task_phase": self.task_phase})
                QApplication.processEvents()  # Force UI redraw
                self._continue_session = True

        return response_handled

    def session_callback(self, response_session_entries: List[SessionEntry]):
        # not all phases auto end with "PHASE_COMPLETE"
        self._continue_session = False
        response_handled = self.handle_session_response(response_session_entries)
        last_response = response_session_entries[-1].content
        if not response_handled and last_response.endswith("PHASE_COMPLETE"):
            self.advance_phase()
        return self._continue_session

    def session_filter_callback(self, entry : SessionEntry) -> bool:
        filter = False
        if "task_phase" in entry.metadata:
            filter = entry.metadata["task_phase"] != self.task_phase
        return filter            
        