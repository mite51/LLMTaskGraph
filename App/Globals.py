import os
from typing import List
import Prompts

ProjectManagerWindow = None
loaded_projects = []

def get_session_task():
    if ProjectManagerWindow and ProjectManagerWindow.session_widget.get_task():
        return ProjectManagerWindow.session_widget.get_task()
    return None

def get_working_directory():
    project_path = get_session_task().project.local_git_path
    if len(project_path) == 0:
        project_path = os.path.dirname(os.path.realpath(__file__))
    return project_path

def find_prompts(search_tags : List['str']) -> List['Prompts.Prompt']:
    prompts_found = []
    for prompt_entry in Prompts.prompts_data.prompts:
        ##if any(tag in prompt_entry.tags for tag in search_tags):
        #all prompt tags should exist in prompt search tags
        #so prompts can get specific, like ["code generation","python", "PyQt"] 
        if all(tag in search_tags for tag in prompt_entry.tags):
            prompts_found.append(prompt_entry)
    return prompts_found

def add_project(project):
    if project not in loaded_projects:
        loaded_projects.append(project)

def remove_project(project):
    if project in loaded_projects:
        loaded_projects.remove(project)

def get_loaded_projects():
    return loaded_projects