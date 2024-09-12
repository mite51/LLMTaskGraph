from pxr import Usd
from Project import *
from Task import *
from TaskNode import *
def Test1():
    task = Task("TEST TASK")
    task.tags = ["tag1", "tag2"]
    task.add_message("user", "Hello")
    task.add_message("assistant", "Hi there!")

    # JSON serialization
    json_str = task.to_json()
    #print(json_str)

    # JSON deserialization
    new_task = Task.from_json(json_str)

    # USD serialization
    stage = Usd.Stage.CreateNew("C:/GitDepots/TaskMaster/App/task.usda")
    task.to_usd(stage, "/MyTask")
    stage.Save()

    # USD deserialization
    loaded_stage = Usd.Stage.Open("C:/GitDepots/TaskMaster/App/task.usda")
    loaded_task = Task.from_usd(loaded_stage.GetPrimAtPath("/MyTask"))

Test1()


def Test2():
    project = Project("TEST PROJECT")
    task = Task("TEST TASK")
    project.add_task(task)

    llm_task_node = TaskNode_LLM("TEST LLM")
    llm_task_node.prompt = "Which large language model is this?"
    task.task_graph_root = llm_task_node

    task.execute(project)
    print(f"prompt_response 1 = {llm_task_node.prompt_response}")

    llm_task_node.llm_name = "GPT-4"
    task.execute(project)
    print(f"prompt_response 2 = {llm_task_node.prompt_response}")

    llm_task_node.llm_name = "GPT-3.5 Turbo"
    task.execute(project)
    print(f"prompt_response 3 = {llm_task_node.prompt_response}")    

Test2()  