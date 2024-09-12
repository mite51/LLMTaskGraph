import asyncio
import aiohttp
import json
import re
import Globals
import os
from typing import Optional, AsyncGenerator, List, Dict, Union, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal

from TaskNode import TaskNode
from TypeDefs import SessionEntry, ResponseEntryType, TaskContext, TaskNodeState
from Util import llm_input_context_resolver, ASSET_PREFIX

class LLM_Interface(str,Enum):
    OpenAI = 0
    Anthropic = 1
    OogaBooga = 2  # for deepseek coder

class LLM_Model(str,Enum):
    Claude3_5_Sonnet = 0
    Chat_GPT_3_5_Turbo = 1
    Chat_GPT_4_o = 2
    DeepSeek = 3

model_names = {
    LLM_Model.Claude3_5_Sonnet: "claude-3-5-sonnet-20240620",
    LLM_Model.Chat_GPT_3_5_Turbo: "gpt-3.5-turbo",
    LLM_Model.Chat_GPT_4_o: "gpt-4o-2024-08-06",
    LLM_Model.DeepSeek: "",
}

model_interfaces = {
    LLM_Model.Claude3_5_Sonnet: LLM_Interface.Anthropic,
    LLM_Model.Chat_GPT_3_5_Turbo: LLM_Interface.OpenAI,
    LLM_Model.Chat_GPT_4_o: LLM_Interface.OpenAI,
    LLM_Model.DeepSeek: LLM_Interface.OogaBooga,
}

def Get_Model_Interface(model: LLM_Model):
    return model_interfaces[model]

class LLMError(Exception):
    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

# Global ThreadPoolExecutor
GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=4)  # Adjust max_workers as needed

class TaskNode_LLM(TaskNode):
    """
    TaskNode_LLM wraps requests to a collection of supported REST apis to major llm inference providers
    Supports streaming for responsive AI and will parse for supported embedded data
    
    "input" will provide the keys from this list and the associated values from task_context variable_stack to the prompt
    "response_variable_stack_name" will save the request response to the task_context variable_stack using this string value as the key
    """

    _supported_embedded_types = ['file', 'diff','task_graph']
    _session_callback : Callable = None
    _session_filter_callback : Callable = None

    class _TaskNodeLLMQObject(QObject):
        streaming_update = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._composed_prompt = ""
        self._qobject = self._TaskNodeLLMQObject()
        self._stop_response = False
        self._stream_complete = True
        self._response_session_entries: List[SessionEntry] = []
        self._full_response = ""
        self._lock = asyncio.Lock()
        self._running_task = None

        self.llm_model: LLM_Model = LLM_Model.Claude3_5_Sonnet
        self.llm_model_name_override = ""
        self.additional_prompt_tags: List[str] = [] # additional tags to be added to the prompt
        self.prompt: str = ""
        self.session: List[SessionEntry] = []
        self.response_variable_stack_name: str = "most_recent_llm_response"
        self.streaming: bool = True
        self.state: TaskNodeState = TaskNodeState.Queued
        self.error_message: Optional[str] = None
        self.timeout: float = 60.0

    def set_session_callback(self, callback: Callable[[str], None]):
        self._session_callback = callback

    def set_session_filter_callback(self, callback: Callable[[str], None]):
        self._session_filter_callback = callback        

    def connect_streaming_update(self, slot):
        self._qobject.streaming_update.connect(slot)

    def disconnect_streaming_update(self, slot):
        self._qobject.streaming_update.disconnect(slot)

    def notify_streaming_update(self):
        self._qobject.streaming_update.emit()

    def add_session_entry(self, sender: str, content: str, include_in_context: bool = True, include_in_display: bool = True, entry_type: ResponseEntryType = ResponseEntryType.CHAT, metadata: Optional[Dict] = None):
        entry = SessionEntry(sender, content, entry_type, metadata)
        entry.include_in_context = include_in_context
        entry.include_in_display = include_in_display
        self.session.append(entry)
        self.notify_streaming_update()

    async def make_request(self) -> AsyncGenerator[str, None]:
        headers = {}
        data = {}
        url = ""
        model_name = model_names[self.llm_model]
        if len(self.llm_model_name_override) > 0:
            model_name = self.llm_model_name_override
        
        model_interface = Get_Model_Interface(self.llm_model)

        assert self._composed_prompt, "Prompt is empty"

        if model_interface == LLM_Interface.OpenAI:
            url = "https://api.openai.com/v1/chat/completions"
            api_key = "YOUR_API_KEY"
            headers = {
                        "Content-Type": "application/json", 
                        "Authorization": f"Bearer {api_key}"
                    }
            data = {
                        "model": model_name, 
                        "messages": [{"role": "user", "content": self._composed_prompt}],
                        "stream" : self.streaming
                    }
        elif model_interface == LLM_Interface.Anthropic:
            url = "https://api.anthropic.com/v1/messages"
            api_key = "YOUR_API_KEY"
            headers = {
                        'Content-Type': 'application/json',
                        'X-API-Key': api_key,
                        'anthropic-version': '2023-06-01',
                    }
            data = {
                        "model": model_name, 
                        "max_tokens": 2048, 
                        "messages": [{"role": "user", "content": self._composed_prompt}],
                        "stream" : self.streaming
                    }
        else:
            raise LLMError(f"make_request unhandled interface")                

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=self.timeout) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if self._stop_response:
                            break                        
                        if line:
                            yield line.decode('utf-8')

        except asyncio.TimeoutError:
            raise LLMError(f"[make_request]Request timed out after {self.timeout} seconds")
        except aiohttp.ClientError as e:
            raise LLMError(f"[make_request]Network error: {str(e)}", details=str(e))
        except Exception as e:
            raise LLMError(f"[make_request]Unexpected error: {str(e)}", details=str(e))

    async def process_stream(self, stream: AsyncGenerator[str, None]) -> None:
        current_entry = None
        self._stream_complete = False
        self._response_session_entries = []
        identifying_markup = False
        markup_buffer = ""
        current_embedded_type = None
        embedded_buffer = ""

        def create_new_entry(entry_type: ResponseEntryType, metadata: Optional[Dict] = None):
            nonlocal current_entry
            self.add_session_entry("System", "", entry_type=entry_type, metadata=metadata)
            current_entry = self.session[-1]
            self._response_session_entries.append(current_entry)

        # start the first reponse entry in chat mode
        create_new_entry(ResponseEntryType.CHAT)

        try:
            async for raw_data in stream:
                chunk = self.parse_chunk(raw_data)
                if chunk:
                    self._full_response += chunk
                    chunk_list = [chunk]                    
                    while chunk_list:
                        current_chunk = chunk_list.pop(0)

                        if identifying_markup:
                            markup_buffer += current_chunk
                            split_index = markup_buffer.find(">\n")
                            if split_index != -1:
                                identifying_markup = False
                                markup, remaining = markup_buffer[:split_index+1], markup_buffer[split_index+1:]
                                markup_buffer = ""
                                embedded_type = self._get_embedded_type(markup)
                                if embedded_type:
                                    # if there is an empty session context when embedded content is detected, delete it
                                    if len(self.session) > 0 and (str.isspace(self.session[-1].content) or len(self.session[-1].content) == 0):
                                        del self.session[-1]
                                        self.notify_streaming_update()
                                    current_embedded_type = embedded_type
                                    filename = self._extract_filename_from_markup(markup)
                                    if filename:
                                        create_new_entry(ResponseEntryType.FILE, {"filename": filename, "type": current_embedded_type})
                                    embedded_buffer = ""
                                else:
                                    if not current_entry or current_entry.entry_type != ResponseEntryType.CHAT:
                                        create_new_entry(ResponseEntryType.CHAT)
                                    remaining = markup_buffer
                                if not str.isspace(remaining):
                                    chunk_list = [remaining]

                        elif current_entry.entry_type == ResponseEntryType.CHAT:
                            split_index = current_chunk.find('<')
                            if split_index != -1:
                                session_content, remaining = current_chunk[:split_index], current_chunk[split_index:]
                                current_entry.content += session_content
                                identifying_markup = True
                                if not str.isspace(remaining):
                                    chunk_list = [remaining]
                            else:
                                if len(current_entry.content) == 0:
                                    current_chunk = current_chunk.lstrip('\n')
                                current_entry.content += current_chunk
                                if not str.isspace(current_entry.content):
                                    self.notify_streaming_update()

                        elif current_entry.entry_type == ResponseEntryType.FILE:
                            embedded_buffer += current_chunk
                            end_tag = f"</{current_embedded_type}>"
                            split_index = embedded_buffer.find(end_tag)
                            if split_index != -1:
                                content, remaining = embedded_buffer[:split_index], embedded_buffer[split_index + len(end_tag):]
                                current_entry.content = content
                                self.notify_streaming_update()
                                create_new_entry(ResponseEntryType.CHAT)
                                current_embedded_type = None
                                embedded_buffer = ""
                                if not str.isspace(remaining):
                                    chunk_list.append(remaining)
                            else:
                                current_entry.content = embedded_buffer
                                self.notify_streaming_update()

                if self._stream_complete:
                    break

            # if there is an empty session context at the end, delete it
            if len(self.session) > 0 and (str.isspace(self.session[-1].content) or len(self.session[-1].content) == 0):
                del self.session[-1]
                self.notify_streaming_update()

        except Exception as e:
            raise LLMError(f"[process_stream]Error processing stream: {str(e)}", details=str(e))
        
        #print(f"***{self._full_response}")

    def _get_embedded_type(self, markup: str) -> Optional[str]:
        for embedded_type in self._supported_embedded_types:
            if markup.startswith(f'<{embedded_type}'):
                return embedded_type
        return None

    def _write_embedded_content(self, embedded_type: str, filename: str, content: str, task_context : TaskContext):
        filepath = os.path.join(task_context.project.local_git_path, filename)
        if embedded_type == 'file':
            # if the first character is new_line, remove it
            if content and content[0] == "\n":
                content = content[1:]
            with open(filepath, 'w') as f: 
                f.write(content)
        elif embedded_type == 'diff':
            # 
            pass

    def _extract_filename_from_markup(self, content: str) -> str:
        pattern = r'<(file|diff|task_graph)(?:\s+([^\s>]+))?>'
        match = re.search(pattern, content)
        
        if not match:
            print(f"extract_filename_from_markup failed to find a valid tag in the markup: {content}")
            raise LLMError(f"[process_stream] extract_filename_from_markup failed: {content}")
        
        tag = match.group(1)
        filename = match.group(2)
        
        if tag in ['file', 'diff']:
            if filename is None:
                print(f"extract_filename_from_markup expected to find a filename for {tag} tag: {content}")
                raise LLMError(f"[process_stream] extract_filename_from_markup failed: {content}")
            return filename
        elif tag == 'task_graph':
            return 'task_graph'
        else:
            # This should never happen due to the regex pattern, but including for completeness
            print(f"extract_filename_from_markup found an unexpected tag: {tag}")
            raise LLMError(f"[process_stream] extract_filename_from_markup failed: {content}")
    
    def parse_chunk(self, chunk: str) -> str:
        if Get_Model_Interface(self.llm_model) == LLM_Interface.OpenAI:
            return self.parse_openai_chunk(chunk)
        elif Get_Model_Interface(self.llm_model) == LLM_Interface.Anthropic:
            return self.parse_anthropic_chunk(chunk)
        else:
            self.state = TaskNodeState.Error
            self.error_message = f"[parse_chunk] unhandled interface"
            print(self.error_message)
            raise LLMError(self.error_message)

    def parse_openai_chunk(self, chunk: str) -> str:
        if chunk.strip() == "data: [DONE]":
            self._stream_complete = True
            return ""
        if chunk.startswith("data: "):
            json_str = chunk[6:]
            try:
                data = json.loads(json_str)
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    return delta.get('content', '')
            except json.JSONDecodeError:
                self.state = TaskNodeState.Error
                self.error_message = f"[parse_openai_chunk]Error decoding JSON: {json_str}"
                print(self.error_message)
                raise LLMError(self.error_message)
        return ""

    def parse_anthropic_chunk(self, chunk: str) -> str:
        try:
            event = json.loads(chunk.strip('data: '))
            if event['type'] == 'content_block_stop':
                self._stream_complete = True
                return ""
            elif event['type'] == 'content_block_delta':
                return event['delta']['text']
            elif event['type'] == 'error':
                print(event['error'])
                self._stream_complete = True
                return ""
            return ""
        except json.JSONDecodeError:
            pass  # Ignore non-JSON lines

    def _compose_final_prompt(self, task_context : TaskContext = None):
        self._composed_prompt = self.get_session_context()
        if len(self.inputs) > 0:
            self._composed_prompt += "/n"
            self._composed_prompt += self.get_inputs_context(task_context)
        if len(self.prompt) > 0:
            self._composed_prompt += "/n"
            self._composed_prompt += self.prompt

    def _handle_response_ebedded_files(self, task_context : TaskContext):
        # deal with any files that were embedded in the response
        for entry in self._response_session_entries:
            if entry.metadata and entry.metadata.get("type") == "file":
                filename = entry.metadata.get("filename")
                embedded_type = entry.metadata.get("type")
                # write the file to the project directory
                self._write_embedded_content(embedded_type, filename, entry.content, task_context)
                # register the file with the project
                task_context.project.register_new_file(filename)
                # add the asset path to the output
                asset_path = os.path.join(ASSET_PREFIX, filename)
                self.output.append(asset_path)  

    def execute(self, task_context : TaskContext):
        self.set_state(TaskNodeState.Executing)
        self.error_message = None

        # clear the session
        self.session = []

        # add the additional prompt tags
        if len(self.additional_prompt_tags) > 0:
            prompts = Globals.find_prompts(self.additional_prompt_tags)
            for prompt in prompts:
                self.add_session_entry("System", prompt.prompt, entry_type=ResponseEntryType.INSTRUCTION)

        # TODO: try to just call request_llm_response_async

        # build the promp to submit with all the required data
        self._compose_final_prompt(task_context)

        try:
            asyncio.run(self._async_execute())
            if len(self.response_variable_stack_name) > 0:
                task_context.variable_stack[self.response_variable_stack_name] = self._full_response
                
            self._handle_response_ebedded_files(task_context)

            self.set_state(TaskNodeState.Complete)
        except LLMError as e:
            self.set_state(TaskNodeState.Error)
            self.error_message = str(e)
            if e.details:
                print(f"Error details: {e.details}")
        except Exception as e:
            self.set_state(TaskNodeState.Error)
            self.error_message = f"[execute]Unexpected error: {str(e)}"
            print(self.error_message)
            raise LLMError(self.error_message) 

    def get_error_info(self) -> Optional[str]:
        if self.state == TaskNodeState.Error and self.error_message:
            return f"Error in {self.llm_model} request: {self.error_message}"
        return None

    async def _async_execute(self):
        stream = self.make_request()
        await self.process_stream(stream)

    async def request_llm_response_async(self, task_context : TaskContext = None):
        async with self._lock:

            while(True):
                self._compose_final_prompt(task_context)

                await self._async_execute()

                if self._session_callback:
                    continue_session = await asyncio.to_thread(self._session_callback, self._response_session_entries)
                if not continue_session:
                    break

            self._handle_response_ebedded_files(task_context)

    def request_llm_response(self, task_context : TaskContext = None):
        if self._running_task and not self._running_task.done():
            print("A request is already in progress. Please wait for it to complete.")
            #raise LLMError("A request is already in progress. Please wait for it to complete.")
            return

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.request_llm_response_async(task_context))
            except Exception as e:
                self.set_state(TaskNodeState.Error)
                self.error_message = f"[request_llm_response] Unexpected error: {str(e)}"
                print(self.error_message)
                raise LLMError(self.error_message)
            finally:
                loop.close()

        self._running_task = GLOBAL_EXECUTOR.submit(run_in_thread)

    def get_session_context(self) -> str:
        #return "\n".join([f"{entry.sender}: {entry.content}" for entry in self.session if entry.include_in_context])
        session_context = ""
        for entry in self.session:
            filter = False
            if self._session_filter_callback:
                filter = self._session_filter_callback(entry)
            if entry.include_in_context and not filter:
                session_context += f"{entry.sender}: {entry.content}\n"
        return session_context
    
    def get_inputs_context(self, task_context : TaskContext = None) -> str:
        input_context = ""
        if task_context != None:
            input_context = "=================================="
            input_context += "input key values from task_context"
            input_context += "=================================="
            resolved_inputs = llm_input_context_resolver(self.inputs, task_context)
            for resolved_input in resolved_inputs:              
                input_context += resolved_input 
        return input_context                            
    
class TaskNode_Disaggregator(TaskNode_LLM):
    """
    Used when the task is either too large or cannot be well defined at the time of graph creation
    A sub graph will be generated when execute is called
    """
    def __init__(self):
        TaskNode_LLM.__init__()

    def execute(self, task_context : TaskContext):
        # TODO build graph then execute it
        pass         