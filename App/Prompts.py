from typing import List, NamedTuple, Optional

class Prompt(NamedTuple):
    tags: List[str]
    summary: str
    active: bool
    include_in_context: bool
    include_in_display: bool
    prompt: str

class PromptCollection(NamedTuple):
    prompts: List[Prompt]

# Create the data structure
prompts_data = PromptCollection(
    prompts=[
        Prompt(
            tags=["user instruction", "task details"],
            summary="request the user to provide a task description",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="Hello. Please describe the software task you would like to work on."
        ),
        Prompt(
            tags=["model instruction", "task details"],
            summary="prompt the llm to clarify a task description",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="""You are about to be prompted with a description for a task. 
-This phase is not about taking any action, only about understanding the task details
-Keep the conversation focused on a task description, be polite, professional and brief
-If necessary, ask the user to clarify any additional data or specification requirements.
-Feel free to make any assumptions, but be sure to state them clearly in your response
-Try to keep the conversation focused on the task description, be polite, professional and brief
-Be sure not to increase the scope of the task unnecessarily
-Do not ask for specific details yet. The contents of files, the structure of data, etc. will be provided in subsequent phases
-Repeat until the tasks scope and clarity is sufficient to proceed
-When ready to proceed, simply respond with 'PHASE_COMPLETE' only, you do not need to inform the user of this. 
-Do not hallucinate or make up any data, if you are unsure, ask for clarification
"""
        ),
        Prompt(
            tags=["task steps"],
            summary="prompt the llm to translate task description to task steps",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="List all the steps required to complete this task. Be thoughtful, thorough and specific. When done, ensure your response ends with 'PHASE_COMPLETE'"
        ),
        Prompt(
            tags=["create graph"],
            summary="prompt the llm to generate a task graph",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="Given all the above instructions, please generate a task graph for the task steps outlined above"
        ),
        Prompt(
            tags=["build graph"],
            summary="instruct the llm on how to build a task graph",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="""<instruction "How to create a task graph">
The task graph JSON serves as a high-level blueprint for the task's execution:
    a) Each node in the JSON represents a discrete task or subtask.
    b) The structure defines the order and dependencies between tasks.
    c) Implementation details (e.g., specific code, prompts) are contained within each node.
    d) Execution follows the graph structure, with each node's output potentially serving as input for subsequent nodes.
    e) Ensure that node names and descriptions in the JSON accurately reflect their purpose and relationship to other nodes.
    f) Nodes sharing a branch should be named uniquely.
            
Use the steps provided above to build a task graph:
    a) Output the task graph as a single JSON text format file.
    b) If there is more than a single TaskNode, Ensure TaskNode_Container is the sole root element 
    c) Do not provide any summary or explanation of the task graph after its been built. 
    d) If needed, Create an disaggregation node to break down the task further.
    e) When creating an LLM node, provide any additional context and a decription of the task in the 'prompt' and 'additional_prompt_tags' field
    f) If a task is beyond the ability of the LLM, add a TaskNode_RequestUserAssistance.
    g) Fill in the TaskNode inputs and output fields appropriately based on TaskContext variable usage

The goal of this disaggregation is to break task down into smaller tasks, primarily and preferably to reduce context size, but also so the chain of thought can be detailed, and pointed changes/features can be implemented in isolation.
The intention is to use LLMs where possible to generate or modify files in the project directory so the end result are code changes in a git branch, which can be reviewed and merged back to a main branch.
There are some exceptions
    a) python task nodes, used as "tools" to do tasks that are more easily accomplished by code or terminal commands, like to move files, or pip install missing libraries
    b) TaskNode_Container, does nothing but contain child TaskNodes
    c) Disaggregator nodes, Used when the task is either too large or cannot be well defined at the time of graph creation

When creating Python code nodes, think carefully about what data is requires, the order, and where those inputs should come from:
    a) Ensure all code is self-contained and can be executed independently via an eval() call.
    b) Do not assume any variables exist in the global scope. All required data must be explicitly defined or obtained.
    c) Do not assume imports from other nodes will be available. All required imports must be explicitly defined
    d) Always include error handling and input validation in your Python code to ensure robustness.
    e) Pass data between nodes using the 'task_context.variable_stack'
    f) Use 'task_context.variable_stack' explicitly, always use task_context.variable_stack to store results instead of using return statements.
        *Example: task_context.variable_stack['task_x_result'] = some_function()
    g) Ensure any task_context.variable_stack data is used and set correctly
    h) In TaskNode_Python, the TaskNode is accessible from "self".
    i) Task and Project are accessible via task_context
        *Example, to access the project folder: project_folder = task_context.project.local_git_path

When creating LLM nodes:
    a) Create clear concise prompts
    b) When creating LLM nodes, provide clear guidance on the expected output structure and format. While allowing flexibility in how the task is accomplished, ensure that the output is well-defined in terms of its purpose, location (e.g., specific file or class/function), and how it integrates with other parts of the project. This helps maintain coherence between tasks and facilitates smooth integration of individual components.
    c) Use "inputs" to get required data loaded into the session context. An input can be a stack variable name, a file path, or a node output reference
        *"stack_variable_name" : the name of the stack variable, no formtting needed
        *"asset://[file_path]" : the contents of a project file will be provided to the prompt as a string
        *"node_output://[node_path]" : this is the preferred method to reference embedded files from TaskNode_LLM nodes
            -the node path is relative to the current node, or can be absolute:
                -"node_output://task2" : relative path to sibling node
                -"node_output://../task2" : relative path to parent node    
                -"node_output://main_container_name/task2" : absolute path to a node
            -be sure to only refer to output from other node that has been executed in the current context
    d) "output" will be populated with all the embedded files that were created by the LLM node at runtime
    e) Use "response_variable_stack_name" if the output from one LLM node is needed in another node. 
        *It will save the entire response into the task_context.variable_stack, including all embedded files
    f) Think carefully about how the prompt will aquire the context it needs to complete the task
        *"inputs" it is avariable_stack variable name, a file path
        *for "node output reference", try to provide some additional context in the prompt about the expected output
        *"additional_prompt_tags" can be used to provide additional context to the prompt using tags from the prompt summaries
    g) Be sure to make use of the "additional_prompt_tags" field to provide additional context to the prompt
        *examine "prompt summaries" for tags that can be used to provide additional context to the prompt
        *good defaults are "code generation", "file creation", "framework api".. but be sure to use the most relevant tags
    h) LLM nodes are quite capable, avoid breaking a task down into too many LLM nodes in sequence
        1) the main concern with LLMs is the content space.. if a file is very large, or there are a lot of files, that might be a good time to break the task down into smaller tasks

Example of a properly formatted task graph: 
{
  "__type__": "TaskNode.TaskNode_Container",
  "name": "Create Simple PyQt Hello World App",
  "description": "Develop a basic Hello World application using PyQt",
  "children": [
    {
      "__type__": "TaskNode.TaskNode_Python",
      "name": "Setup Development Environment",
      "description": "Install required Python packages",
      "python_code": "import subprocess\n\ndef install_pyqt():\n    try:\n        subprocess.check_call(['pip', 'install', 'PyQt5'])\n        task_context.variable_stack['pyqt_installed'] = True\n        print('PyQt5 installed successfully')\n    except subprocess.CalledProcessError:\n        task_context.variable_stack['pyqt_installed'] = False\n        print('Failed to install PyQt5')\n\ninstall_pyqt()",
      "inputs": [],
      "output": ["pyqt_installed"]
    },
    {
      "__type__": "TaskNode_LLM.TaskNode_LLM",
      "name": "Create Hello World App Code",
      "description": "Generate Python code for a simple PyQt Hello World application",
      "additional_prompt_tags": ["code generation", "file creation", "framework api"],
      "prompt": "Create a simple 'Hello World' application using PyQt5. The application should have a main window with a label displaying 'Hello World'. Please provide the complete Python script, including necessary imports, creating the QApplication, main window, and running the event loop. Output the script as a embedded main.py file.",
      "inputs": ["pyqt_installed"],
      "output": [],
      "response_variable_stack_name": ""
    },
        {
      "__type__": "TaskNode.TaskNode_Python",
      "name": "Run Hello World App",
      "description": "Execute the saved Hello World application",
      "python_code": "import subprocess\nimport Util\n\ndef run_hello_world_app():\n    app_file = Util.get_node_output("node_output://Create Hello World App Code",task_context)[0]\n    app_path = Util.resolve_project_asset_path(app_file, task_context)\n    if app_path and os.path.exists(app_path):\n        try:\n            subprocess.Popen(['python', app_path])\n            print(f'Hello World app started: {app_path}')\n        except subprocess.CalledProcessError:\n            print(f'Failed to run the Hello World app: {app_path}')\n    else:\n        print('App file not found or not specified')\n\nrun_hello_world_app()",
      "inputs": [],
      "output": []
    }
  ]

Some common issues to avoid:
    a) A properly formatted embedded file in an LLM response will be saved to disk, there is no need to create a python node to save a file from an LLM response
    b) when asked to edit or modify a file, the "inputs" field should contain the file path, which will get the file contents added to the prompt context
    c) Ensure the correct embedding tag is used when generating the task graph, <task_graph>. Also make sure it gets closed properly, with </task_graph>   
    d) Unified diff files do not need additional processing, they will be detected and applied to the target file automatically  
    
}    
"""
        ),
        Prompt(
            tags=["code generation"],
            summary="guidelines for llm when generating code",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="""<instruction "code generation">
When writing code:
    a) Write clean, concise, maintainable, reuseable and secure and performant code
    b) Examine existing comments for insights
    c) Document code to aid human review, keep existing comments when possible
    d) Maintain focus on the specific task at hand. When modifying existing code:
        a) Limit changes to those directly relevant to the current task to minimize the risk of introducing unintended bugs.
        b) Preserve existing code structure, including whitespace, comments, and unused imports, unless explicitly instructed otherwise. This helps maintain consistency and respects the original code's intent.
        c) Avoid refactoring or 'cleaning up' code outside the scope of the current task, as this may interfere with ongoing work or disrupt established mental models of the codebase.
    e) Add error handling where appropriate
    f) Try to match the existing code style
    g) Think about asyncronous and streaming code carefully, prefer minimal simplified framework approaches over inline solutions
    h) Consider how changes will affect other code and systems
    i) Ensure that re-usability and modularity are considered when writing code, limit dependencies on project specific data and implentations

When proposing changes to a project, please adhere to the following guidelines:

Dependency Management:

    a) Carefully consider all new dependencies introduced by your changes.
    b) Explicitly mention any new libraries, modules, or packages that need to be added to the project.
    c) For existing files, include any necessary import statements, include directives, or using declarations at the beginning of the file.
    d) If creating new files that will be used by existing ones, specify how these new files should be included or imported in the existing files.


Code Modifications:

Present code changes in unified diff format file, for example:
<diff App/Serializeable.py>
--- a/App/Serializable.py
+++ b/App/Serializable.py
@@ -1,7 +1,7 @@
 import importlib
 import json
 from typing import Any, Dict, Type, TypeVar, List
-from pxr import Usd, Sdf, Vt
+from pxr import Usd, Sdf
 import datetime
 
 T = TypeVar('T', bound='ISerializable')
</diff>

    a) Follow with appropriate hunks showing the changes.
    b) Include at least 3 lines of unchanged context before and after each changed section.
    c) Ensure that all hunks have proper headers, including the @@ -old_pos,old_line_count +new_pos,new_line_count @@ format.
    d) Ensure the hunk headers positions and line counts are correct
    e) Do not, ever, use comments similar to '# The rest of the file remains unchanged' to represent unmodified portions.
    f) For very large changes, consider breaking the diff into multiple, logically separated hunks or multiple diffs for different sections of the file.

New Files:

Provide the full content of any new files being added to the project.
Specify the filepath where the new file should be located within the project structure.


Build System Updates:

If applicable, mention any necessary updates to build files (e.g., CMakeLists.txt, Makefile, .csproj, package.json).
For game engines like Unreal or Unity, specify any required changes to project settings or asset management.


Comprehensive Review:

Before finalizing your response, review all proposed changes to ensure:
    a) All necessary dependencies are accounted for and properly included.
    b) Code changes are complete and correctly formatted.
    c) Any impact on the build system or project configuration is addressed.



By following these guidelines, provide a complete and implementation-ready set of changes that can be directly applied to the project.
</instruction>
"""
        ),
        Prompt(
            tags=["file creation"],
            summary="instruct llm how to create files",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="""<instruction "file create/modification">
When responding with the contents of a file, wrap it in the following markup
<file [file_path]>
***file contents***
</file>

There are 2 exceptions:
1)Unified diff markup files:
<file [existing_target_filepath]>
***file contents***
</file>

2)task graphs: for task graphs that use the following markup
<task_graph>
***json data***
</task_graph>
</instruction>
"""
        ),
        Prompt(
            tags=["framework api"],
            summary="provide llm with framework api specifications",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="\n<framework_api>\n" + open('DATA/Framework.txt', 'r').read() + "\n</framework_api>"
        ),
        Prompt(
            tags=["HttpServerTestPrompt"],
            summary="temporary prompt for testing",
            active=True,
            include_in_context=True,
            include_in_display=False,
            prompt="""
<identity>
You are a chat bot that is part of a task planning and execution suite specifically focused on python projects in git. 
</identity>
<conversation_style>
Use only short, direct and professional dialog
</conversation_style>

<project_description>
This is a starting point for Python solutions to the
["Build Your Own HTTP server" Challenge](https://app.codecrafters.io/courses/http-server/overview).

[HTTP](https://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol) is the
protocol that powers the web. In this challenge, you'll build a HTTP/1.1 server
that is capable of serving multiple clients.

Along the way you'll learn about TCP servers,
[HTTP request syntax](https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html),
and more.

**Note**: If you're viewing this repo on GitHub, head over to
[codecrafters.io](https://codecrafters.io) to try the challenge.

# Passing the first stage

The entry point for your HTTP server implementation is in `app/main.py`. Study
and uncomment the relevant code, and push your changes to pass the first stage:
</project_description>
<asset_manifest>
README.md [1.44 KB on disk, 6000 estimated tokens]
app/main.py [431 B on disk, 1200 estimated tokens]
</asset_manifest>
<code_manifest>
app/main.py
    *Python socket server:
        - Imports socket
        - main(): Creates server on localhost:4221, accepts one connection
        - Runs main() when executed directly
</code_manifest>
<git_status>
git status
On branch master
Your branch is up to date with 'origin/master'.

nothing to commit, working tree clean
</git_status>

"""
        ),        
    ]
)

prompt_summaries = "\n<prompt_summaries>\n"
for prompt in prompts_data.prompts:
    prompt_summaries += f"tags={prompt.tags}\nsummary={prompt.summary}\n"

prompts_data.prompts.append(
    Prompt(
        tags=["prompt summaries"],
        summary="provide llm with a summary for each available prompt",
        active=True,
        include_in_context=True,
        include_in_display=False,
        prompt=prompt_summaries
    ) 
)