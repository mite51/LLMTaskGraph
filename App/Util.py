import re
import os.path
from TypeDefs import TaskContext
from typing import Any, List

ASSET_PREFIX = "asset://"
NODE_OUTPUT_PREFIX = "node_output://"

def is_project_file_reference(input : str, task_context : TaskContext) -> bool : 
    return input.startswith(ASSET_PREFIX)

def resolve_project_asset_path(input : str, task_context : TaskContext) -> str : 
    project_path = task_context.project.local_git_path
    asset_path = input[len(ASSET_PREFIX):]
    return os.path.join(project_path, asset_path)

def load_project_file(asset_path : str, task_context : TaskContext,) -> str : 
    filepath = resolve_project_asset_path(asset_path, task_context)
    if not os.path.isfile(filepath):
        raise Exception(f"File not found: {filepath}")
    with open(filepath, 'r') as file:
        return file.read()
    
def is_node_output_reference(input : str) -> bool :    
    return input.startswith(NODE_OUTPUT_PREFIX)

def get_node_output(input : str, task_context : TaskContext) -> List[str] :
    node_path = input[len(NODE_OUTPUT_PREFIX):]
    # a node reference can look like this: "node_output://TaskNode1"
    # or this: "node_output://task1/TaskNode1"
    # or this: "node_output://../TaskNode1"
    
    # for each ../ in the path, pop the last node off the stack
    # only allow the leading ../ to pop nodes off the stack, at any other point in the path, is an error
    node_stack = task_context.node_stack
    node_stack.pop()# pop to start at the parent of the current node
    path_parts = node_path.split('/')
    pop_count = 0
    for part in path_parts:
        if part == "..":
            if len(node_stack) > 0:
                node_stack.pop()
                pop_count += 1
            else:
                raise Exception(f"Invalid node path: {node_path}")
        else:
            break
    
    # remove the path parts that were popped off the stack
    path_parts = path_parts[pop_count:]

    # now get the node from the path and find the node that matches by name
    search_node = task_context.get_node(node_stack)
    for search_name in path_parts:
        found = False
        for child in search_node.children:
            if child.name == search_name:
                search_node = child
                found = True
                break
        if not found:
            raise Exception(f"Node not found: {search_name}")
        
    return search_node.output

def resolve_context_input( input: str, task_context : TaskContext) -> Any : 
    # This function should be used by TaskNodes to resolve context input values
    # either for prompts of for embedded code execution
    value = None
    if is_project_file_reference(input, task_context): 
        value = load_project_file(input, task_context)
    elif is_node_output_reference(input):
        node_output_list = get_node_output(input, task_context)
        node_output_dict = {}
        for output in node_output_list:
                value = resolve_context_input(output, task_context)
                node_output_dict[output] = value
        value = node_output_dict
    elif input in task_context.variable_stack:
        value = task_context.variable_stack[input]
    else:
        raise Exception(f"failed to resolve input {input}")
    
    return value

def llm_input_context_resolver( inputs: List[str], task_context : TaskContext) -> List[str] : 
    context = []
    for input in inputs:
        value = resolve_context_input(input, task_context)
        context.append(str(value))
        if is_project_file_reference(input, task_context):
            value = load_project_file(input, task_context)
            value_context = f"<project_file {input}>{value}</project_file>"
            context.append(value_context)            
        elif is_node_output_reference(input):
            node_output_list = get_node_output(input, task_context)
            for output in node_output_list:
                value = llm_input_context_resolver(output, task_context)
                value_context = f"<node_output node={input} output={output}>{value}</node_output>"
                context.append(value_context)
        elif input in task_context.variable_stack:
            # add the input key and value to the input context
            value = task_context.variable_stack[input]
            value_context = f"<input {input}>{value}</input>"
            context.append(value_context)
        else:
            raise Exception(f"failed to resolve input {input}")
    return context

def fix_diff_line_counts(diff_file_content : str):

    # Regular expression to match hunk headers
    hunk_pattern = re.compile(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

    def count_lines(hunk):
        hunk_lines = hunk.split('\n')
        hunk_lines = [item for item in hunk_lines if item != "\\ No newline at end of file"]
        if hunk_lines[-1] == "":
           del hunk_lines[-1]
        old_lines = len([line for line in hunk_lines if not line.startswith('+')])
        new_lines = len([line for line in hunk_lines if not line.startswith('-')])

        """
        print(f"*** HUNK")
        total_lines = 0
        old_lines = 0
        new_lines = 0
        for l in hunk_lines:
            total_lines += 1
            if not l.startswith('+'):
                old_lines += 1
            if not l.startswith('-'):
                new_lines += 1            
            print(f"total_lines={total_lines} old_lines={old_lines} new_lines={new_lines} {repr(l)}  ")
        """
        return old_lines - 1, new_lines - 1  # Subtract 1 to exclude the hunk header

    def fix_hunk(match):
        hunk_start = match.start()
        hunk_end = diff_file_content.find('\n@@', hunk_start + 1)
        if hunk_end == -1:
            hunk_end = len(diff_file_content)
        hunk = diff_file_content[hunk_start:hunk_end]

        old_start, old_count, new_start, new_count = map(int, match.groups())
        actual_old_count, actual_new_count = count_lines(hunk)

        if old_count != actual_old_count or new_count != actual_new_count:
            return f'@@ -{old_start},{actual_old_count} +{new_start},{actual_new_count} @@'
        return match.group()

    fixed_content = hunk_pattern.sub(fix_hunk, diff_file_content)

    return fixed_content