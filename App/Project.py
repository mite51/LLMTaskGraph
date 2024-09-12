import csv
import json

from Task import Task 
from Serializable import ISerializable
from collections import namedtuple
from typing import Any, Dict, List
from TypeDefs import TaskNodeState

class Project(ISerializable):
    """
    In essensce, the Project is a container for the list of tasks, and project specific data
    Currently only focused on any type software development using git
    """    
    def __init__(self, name: str):
        self.name = name
        self.tasks = []
        self.description = ""
        self.status = ""
        self.git_URL = ""
        self.local_git_path = ""
        self.file_name = ""
        self.project_data = {} # api keys, git URL? also project "keyword" data, files, documentation, code_manifest, build_instructions, etc.
        self.project_data['anthropic_api_key'] = []
        self.project_data['openai_api_key'] = []
        self.project_data['files'] = []
        self.project_data['documentation'] = []
        self.project_data['code_manifest'] = {}
        self.project_data['build_instructions'] = ""

    def add_task(self, task: Task):
        self.tasks.append(task)

    def register_new_file(self, filename: str):
        if 'files' not in self.project_data:
            self.project_data['files'] = []
        if filename not in self.project_data['files']:
            self.project_data['files'].append(filename)

    _exclude_from_properties = ['tasks']
    _exclude_from_usd = ['task_graph_root']
    _exclude_from_json = ['task_graph_root']
    
    def save_to_file(self, file_name):
        data = self.to_json()
        with open(file_name, 'w') as f:
            json.dump(data, f, indent=4)
        self.file_name = file_name
    
    @classmethod
    def load_from_file(cls, file_name):
        with open(file_name, 'r') as f:
            data = json.load(f)
        project = cls.from_json(data)
        project.file_name = file_name
        return project
    
    def to_json(self):
        data = {
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'git_URL': self.git_URL,
            'local_git_path': self.local_git_path,
            'project_data': self.project_data,
            'tasks': [task.to_json() for task in self.tasks]
        }
        return data
    
    @classmethod
    def from_json(cls, data):
        project = cls(data['name'])
        for key, value in data.items():
            if key != 'tasks':
                setattr(project, key, value)
        project.tasks = [Task.from_json(task_data) for task_data in data['tasks']]
        project.post_deserialize()
        return project
 
    def post_deserialize(self):
        for task in self.tasks:
            task.project = self
            task.task_context.project = self
            task.task_context.task = task

            current_node = task.task_context.get_current_node()
            if len(task.task_context.node_stack) == 0 and current_node.state == TaskNodeState.Queued:
                current_node.set_state(TaskNodeState.Ready)    
