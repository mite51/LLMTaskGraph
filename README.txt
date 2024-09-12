Task Master

Description: A node based task aggregation framework driven by LLMs

Scope: write and debug in a profession software development environment

------------------------------
Features 
-Simple node based graphs with data compositing for task specific variation on reusable sub tasks.. USD based
	*builds llm contexts
-Tasks can be constructed, reused, or build variants.. and stored in a central database with meta data for search
-LLMs construct graphs will disaggregate large tasks into progressively smaller sequential tasks
	*Handle planning, decision making and progress on a plan
-when a task encounters a failure, the graph and out evaluated and corrections made
	*to avoid relying llms trying to correct themselves, and focus on creating better inputs
	*node results are cached, but can be dirtied task changes 
	*not all task nodes are LLMs, could be python code, some other AI like diffusion or speech
-Each LLM node can target a model specific to the task or more efficient, balance effectiveness and cost 
-LLM express code changes in git format to reduce context size(?)
-Use git as common project interface, can work in branches, use CI tests, 
	*But be flexible, source control, bug tracking, project management specific to an organization should be able to support existing infrastructures.

Future features/scale up:
***versions/source control for task graphs. usd monogoBD or a custom graph/prompt database
***move to webui, make it cloud based, market place for nodes/graphs

-------------------------------
The framework

Consists of 4 parts, Projects/Tasks/Nodes/Prompts, meant to be simple and flexible

Project: provides context for the work environment
	-product vision and specifications
	-programming language [python, c++, c#, etc]
    -engine interface(s) [python libs/conda env, unreal engine, unity engine, etc]
    -deployment instructions, how to build, run, test
	-project files, hopefully source controlled, ideally git
        -notes on where to find assets
            -source
            -config
            -art
    -style guide/best practices
	-API KEYS for external AI services
	-project specific RAGS?(maybe later)

Tasks: high level description of work item
	-LLM Session
	-Node graph
	-Tags and version data to be searchable/reusable

Nodes:
	-Does the work or provides context(leaf), or aggregates the task further(branch/parent)
	-Flexible to allow any digital work to be performed by LLM. or work routed to custom models, or humans .. for cost, efficiency and privacy

Prompts:
	simple database of very targeted prompt with tag based search
		["code generation","python", "PyQt"] 
		["code generation","python", "pytorch", "charting"] 
		["code generation","c++","Unreal plugin","gameplay ability system"] 
		
============================================
Coding Task Phases:
	Description, details/scope/clarity
		Notes: details about failures from earlier attempts
	List steps
	Build task graph
		-Review, look for additional applicable prompts
	Create branch
	Execute task graph
	Verify and test(build/unit tests)
		Refine.. errors or mistakes are corrected in the Description
		Add notes made about the errors encountered
		Reset branch and start again
	Commit

============================================
Task Execution:
This happens in 5 steps, starting with the main task description. The first node created is a TaskDisaggregator node which will break the task description into 
smaller tasks until it creates a task that is sufficiently simple it will be a leaf TaskNode

1)Look for an existing graph to reuse/repurpose 
	[Not Found] - Build the graph: Aggregation
		The task description will be used along with a prompt to generate:
		a) produce dependencies - given the context of the task, consider if there is additional context required, if so generate nodes to provide the data
		b) aggregated tasks - once dependencies are made, and executed, the context is added and sub-tasks are created. 
			Prompt the LLM to generate a list of sub tasks and context, given the framework documentation and examples

	[Found] - Customize the graph

2)Execution 
	The graph is traversed for execution nodes and those are run in sequence. 

3)Review. Self assessment, Test (unit test, project build/run), then project review (ie swarm, gitlab.. probably a project Task)
	*provide context for refinement, or skip to step 5

4)Refinement
	*use feedback from review to update the graph and restart step 1
	*feedback specific to a node can add to its context
		
5)Completed.

--------------------------------
Types of nodes: (not all are available)

Context Node (super):
	Context Node local file:
	Context Node local file search:
	Context Node web page:
	Context Node screenshot:
	-meta data about the contents
		* style guide for company X
		* style guide for team X
		* language/engine docs
	-task driven, flexible : 
		*use output to create more context nodes if needed, find places where that data might be help more broadly in the graph
		*collocate often, especially newer nodes... often new information can be generalized better after seeing similar failures, or finding missing information 	

Task Node (super):
	Task Node LLM:
		-write code
	Task Node python code:
		-tools, move files, setup env, build project, etc
		-apply code change
	Task Node command line:
	Task Node image:
	Task Node speech:
	Task Node music:
	Task Node slack/discord:
	Task Node Jira/other project management software

Task Project 
	Task Project Build
		-how to compile the project
	Task Project Test
		-how to configure and run a test
	Task Project Peer review
	Task Project Source control
	Task Project Email
	Task Project IM
	
============================================
Examples of tasks:
-code review
-code exploration: what does this function do
-write function/class/component
-test function/class/component
-create a test case
-generate documentation
-build project manifest

============================================
=project data?
============================================
current working directory
operating System
target platform
file manifest
code manifest 
- class declarations
- function declarations
- method declarations (with namespace scope)
- struct declarations
- union declarations
- typedef declarations
- enum declarations
documentation

============================================
=potential projects
============================================
-Think about a project with tasks that updates over time, like "search for new AI news, summarize and create a weekly collection of AI news"
-Test project LLM explorer
    -visualize confidence at each token
    -run inference in tandem with alternate conversations, show them overlap, cull branches, force specific directions
    -explore vector space, show all vector points and all summations of combinations to build a cloud veiw of spatial realtion ships
        *probably limited to 3x depth for 3d space, unless theres a good visualization for >3 dimensions
        *do points have higher densities in different areas, is so what do they look like? can the shapes be combined? does that mean anything?
        *Sum up token vectors
            -normalized, if they share a similar concept (noun, sport, vegetable).. is that how you get concept vectors?
	https://www.youtube.com/watch?v=9-Jl0dxWQs8&list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi&index=8
	https://transformer-circuits.pub/2023/monosemantic-features
	https://transformer-circuits.pub/2022/toy_model/index.html
-Virtual Lawyer
	-model each step in handling .. something?	

============================================
=scraped prompts
============================================
"""
- When editing files, always provide the complete file content in your response, regardless of the extent of changes. The system handles diff generation automatically.
- When making changes to code, always consider the context in which the code is being used. Ensure that your changes are compatible with the existing codebase and that they follow the project's coding standards and best practices.
- Do not ask for more information than necessary. Use the tools provided to accomplish the user's request efficiently and effectively. When you've completed your task, you must use the attempt_completion tool to present the result to the user. The user may provide feedback, which you can use to make improvements and try again.
- Your goal is to try to accomplish the user's task, NOT engage in a back and forth conversation.
- NEVER start your responses with affirmations like "Certainty", "Okay", "Sure", "Great", etc. You should NOT be conversational in your responses, but rather direct and to the point.
- When presented with images, utilize your vision capabilities to thoroughly examine them and extract meaningful information. Incorporate these insights into your thought process as you accomplish the user's task.

- You are a highly skilled software developer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices.
- You can read and analyze code in various programming languages, and can write clean, efficient, and well-documented code.
===
OBJECTIVE

You accomplish a given task iteratively, breaking it down into clear steps and working through them methodically.

1. Analyze the user's task and set clear, achievable goals to accomplish it. Prioritize these goals in a logical order.
2. Work through these goals sequentially, utilizing available tools as necessary. Each goal should correspond to a distinct step in your problem-solving process. It is okay for certain steps to take multiple iterations, i.e. if you need to create many files but are limited by your max output limitations, it's okay to create a few files at a time as each subsequent iteration will keep you informed on the work completed and what's remaining. 
3. Remember, you have extensive capabilities with access to a wide range of tools that can be used in powerful and clever ways as necessary to accomplish each goal. Before calling a tool, do some analysis within <thinking></thinking> tags. First, think about which of the provided tools is the relevant tool to answer the user's request. Second, go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. If all of the required parameters are present or can be reasonably inferred, close the thinking tag and proceed with the tool call. BUT, if one of the values for a required parameter is missing, DO NOT invoke the function (not even with fillers for the missing params) and instead, ask the user to provide the missing parameters using the ask_followup_question tool. DO NOT ask for more information on optional parameters if it is not provided.
4. Once you've completed the user's task, you must use the attempt_completion tool to present the result of the task to the user. You may also provide a CLI command to showcase the result of your task; this can be particularly useful for web development tasks, where you can run e.g. \`open index.html\` to show the website you've built.
5. The user may provide feedback, which you can use to make improvements and try again. But DO NOT continue in pointless back and forth conversations, i.e. don't end your responses with questions or offers for further assistance.

===

"""



