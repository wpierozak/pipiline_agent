from typing import Annotated, Any, List, Tuple
from pipiline_agent.core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from pipiline_agent.core.resources import ResourceUser, resource, LLMFactory, SysPromptFactory, ToolAlignerFactory
from pipiline_agent.core.agents import BaseAgent, AgentExecutionResult
from pipiline_agent.core.tools import ToolsDefinition
from pipiline_agent.core.chat import ChatResponse
from pipiline_agent.coding.python_tools import PythonWorkSpace, PythonWorkSpaceFactory
import logging

logger = logging.getLogger(__name__)


class PlainSimpleAgent(BaseAgent):
    """
    A base agent implementation that orchestrates the construction of prompts from:
    - System prompts
    - Output schema format instructions
    - Conversation history
    - Messages from other agents (sockets)
    - The current task/user prompt

    It simplifies the creation of agents that follow a standard 'context + prompt -> model' pattern.
    """
    def __init__(self, model_name: str, sys_prompt: str, tool_args: dict[str, Any] = None):
        super().__init__(tool_args=tool_args)
        self.__model_name = model_name
        self.add_sysprompt(sys_prompt)

    def __execute__(self, task_context: str) -> AgentExecutionResult:
        prompt = task_context
        
        history_prompt = self.latest_history or ""
        latest_messages = self.get_latest_messages()

        latest_messages_prompt = []
        for name, message in latest_messages.items():
            latest_messages_prompt.append(f"{name}: {message}")
        
        output = self._invoke_model(prompt=prompt, 
                                    history_prompt=history_prompt, 
                                    latest_messages_prompt=latest_messages_prompt)
        
        return AgentExecutionResult(output=output)
    def _invoke_model(self, prompt: str, history_prompt: str, latest_messages_prompt: List[str]) -> str:
        if not hasattr(self, self.__model_name):
             return "Error: No model loaded."
        
        logger.debug(f"History prompt (newest): {history_prompt}")
        logger.debug(f"Subscribed mess (newest): {latest_messages_prompt}")
        
        prompts = []
        self.append_sysprompts(prompts)
        if self.schema_prompt:
            prompts.append(self.schema_prompt)
        prompts.append(AIMessage(content=history_prompt))
        prompts.append(AIMessage(content="\n".join(latest_messages_prompt)))
        prompts.append(HumanMessage(content=prompt))
        
        model = getattr(self, self.__model_name)
        
        iteration = 0
        finished: bool = False
        
        logger.info("Starting model invocation loop")
        
        while finished == False:
            iteration += 1
            logger.debug(f"--- Iteration {iteration} ---")
            
            response = model.invoke(prompts)
            
            logger.debug(f"Response received - content length: {len(response.content) if response.content else 0}, tool_calls: {response.tool_calls}")
            
            # Create AIMessage from ChatResponse
            ai_message = AIMessage(content=response.content, tool_calls=response.tool_calls)
            prompts.append(ai_message)
            tool_responses = None
                
            if response.tool_calls:
                logger.debug(f"Processing {len(response.tool_calls)} tool call(s)")
                tool_responses = self.handle_tool_calls(response)
            else:
                logger.debug("No tool calls to process (response.tool_calls is None or empty)")
                
            if tool_responses is not None:
                logger.debug(f"Iteration {iteration}: Tool(s) called, continuing loop")
                prompts.extend(tool_responses)
            else:
                logger.info(f"Iteration {iteration}: No tool calls, finishing (total iterations: {iteration})")
                finished = True
        

        return response.content

class Simple(PlainSimpleAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]
    def __init__(self, sys_prompt: str) -> None:
        super().__init__(model_name="model", sys_prompt=sys_prompt)


class Reviewer(PlainSimpleAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]

    def __init__(self, sys_prompt: str) -> None:
        super().__init__(model_name="model", sys_prompt=sys_prompt)
        self.define_output_schema(schema_validator={
            "type": "object",
            "properties": {
                "review": {"type": "string"},
                "decision": {"type": "string"}
            },
            "required": ["review", "decision"]
        },
        schema={
            "review": "explanation of the decision",
            "decision": "APPROVE or DISAPPROVE"
        })

class Verifier(PlainSimpleAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]
    def __init__(self):
        super().__init__(model_name="model", sys_prompt="")
        self.define_output_schema(schema_validator={
            "type": "object",
            "properties": {
                "next_state": {"type": "string"}
            },
            "required": ["next_state"]
        },
        schema={
            "next_state": "name of the next state"
        })

class PythonCoder(PlainSimpleAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]
    tool_aligner: Annotated[ToolAlignerFactory, resource(category="tool_aligner", rid="tool_aligner")]
    python_coder_prompt: Annotated[SysPromptFactory, resource(category="sysprompt", rid="python_coder_prompt")]
    python_workspace: Annotated[PythonWorkSpaceFactory, ToolsDefinition(name="python_workspace", bind_to="model")] = PythonWorkSpaceFactory()

    def __init__(self, sys_prompt: str = None, workspace_path: str = "./workspace", use_venv: bool = False):
        tool_args = {
            "python_workspace": {
                "path": workspace_path,
                "create_venv": use_venv
            }
        }
        super().__init__(model_name="model", sys_prompt=sys_prompt or "", tool_args=tool_args)
        self.define_output_schema(schema_validator={
            "type": "object",
            "properties": {
                "script_path" : {"type": "string"},
                "script_args" : {"type": "array", "items": {"type": "string"}},
                "script_output" : {"type": "string"},
                "is_interactive" : {"type": "boolean"},
                "summarization" : {"type": "string"}
            }
        },
        schema={
            "script_path": "path to the created script",
            "script_args": "arguments for the created script",
            "script_output": "output of the created script",
            "is_interactive": "indicates if the created script is interactive",
            "summarization": "summarization of the created script"
        })
        if hasattr(self, "python_coder_prompt") and self.python_coder_prompt:
             self.add_sysprompt(self.python_coder_prompt)

class PythonCodeTester(PlainSimpleAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]
    python_tester_prompt: Annotated[SysPromptFactory, resource(category="sysprompt", rid="python_tester_prompt")]
    python_workspace: Annotated[PythonWorkSpaceFactory, ToolsDefinition(name="python_workspace", bind_to="model")] = PythonWorkSpaceFactory()

    def __init__(self, sys_prompt: str = None, workspace_path: str = "./workspace", use_venv: bool = False):
        tool_args = {
            "python_workspace": {
                "path": workspace_path,
                "create_venv": use_venv,
                "allow_read_only": True
            }
        }
        super().__init__(model_name="model", sys_prompt=sys_prompt or "", tool_args=tool_args)
        self.define_output_schema(schema_validator={
            "type": "object",
            "properties": {
                "tested_script_path" : {"type": "string"},
                "script_result_summary" : {"type": "string"},
                "passed": {"type": "boolean"}
            }
        },
        schema={
            "tested_script_path": "path to the tested script",
            "script_result_summary": "summarization of the tested script result",
            "passed": "indicates if the tested script passed"
        })
        if hasattr(self, "python_tester_prompt") and self.python_tester_prompt:
             self.add_sysprompt(self.python_tester_prompt)
        