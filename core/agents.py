from __future__ import annotations
import inspect
from dataclasses import dataclass, asdict
from typing import Any, Callable, Optional, TYPE_CHECKING, Tuple, List
import logging

logger = logging.getLogger(__name__)

from pipiline_agent.core.messages import AIMessage, SystemMessage, ToolMessage
from pipiline_agent.core.chat import ChatResponse, ToolCall
from pipiline_agent.core.enums import StateResult
from pipiline_agent.core.memory import MemoryLedger
from pipiline_agent.core.json_utils import strip_json_output
from pipiline_agent.core.resources import ResourceUser, throw_if_not_chatmodel, resource
from pipiline_agent.core.tools import throw_if_not_toolprovider, ToolUser, Tool, ToolMeta, ToolProvider
import json
from jsonschema import validate
import json_repair
from typing import List, Any, Annotated, get_type_hints, get_origin, get_args

@dataclass
class AgentExecutionResult:
    output: str

    def json_str(self):
        return json.dumps(asdict(self))

class AgentSocket:
    def __init__(self, name: str, description: str, memory: MemoryLedger):
        self.name = name
        self.description = description
        self._memory = memory
        self._cursor = 0  # Renamed for clarity (Standard Terminology)

    @property
    def has_new_messages(self) -> bool:
        """
        Pure check. No side effects.
        Safe to call repeatedly or inspect in debuggers.
        """
        return self._memory.snapshots_number > self._cursor

    @property
    def unread_count(self) -> int:
        """Useful to see HOW MANY messages are pending."""
        return self._memory.snapshots_number - self._cursor

    def peek_latest(self) -> str:
        """
        View the data WITHOUT marking it as read.
        """
        return str(self._memory.get_last_snapshot())

    def read_latest(self) -> str:
        """
        View the data AND mark as read (advances cursor).
        """
        # 1. Update Cursor
        self._cursor = self._memory.snapshots_number
        # 2. Return Data
        return str(self._memory.get_last_snapshot())

    def read_new_history(self) -> List[str]:
        """
        Get ONLY the messages I haven't seen yet.
        """
        full_hist = self._memory.get_history()
        new_items = full_hist[self._cursor:]
        self._cursor = len(full_hist)
        
        return [str(x) for x in new_items]

    def read_entire_history(self) -> List[str]:
        """
        Get ALL the messages.
        """
        self._cursor = self._memory.snapshots_number
        return self._memory.get_history()


@dataclass(frozen=True)
class ToolConnector:
    target: str

class BaseAgent(ResourceUser, ToolUser):
    def __init__(self, tool_args: dict[str,dict[str, Any]]):
        if tool_args is None:
            tool_args = {}
        # Explicitly initialize both parent classes
        ResourceUser.__init__(self)
        ToolUser.__init__(self, tool_args)
        if hasattr(self, "tool_aligner") is False:
            self.tool_aligner = None

        self._sockets: dict[str, AgentSocket] = {}
        self._history: MemoryLedger = MemoryLedger()
        self._schema: dict[str, Any] | None = None
        self._schema_validator: dict[str, Any] | None = None
        self._original_schema_validator: dict[str, Any] | None = None
        self._schema_prompt: SystemMessage | None = None
        
        logger.info("Agent initialized", extra={
            "agent_class": self.__class__.__name__,
            "tool_args_keys": list(tool_args.keys()) if tool_args else []
        })
        self._sysprompts: List[SystemMessage] = []

        self._tool_registry: dict[str, Tool] = {}
        
        self._connect_tools()
        

    def _connect_tools(self):
        """
        Iterates over all tool sources (Providers) injected via ToolUser,
        extracts individual tools, registers them, and binds them to the target model.
        """
        logger.info("Starting tool connection and registration")
        
        # Log tool_aligner availability
        if self.tool_aligner is not None:
            logger.info("Tool aligner available - will populate during registration")
        
        for target, providers in self.get_tool_providers_by_target().items():
            logger.debug(f"Processing target model: {target}")
            
            # Extract tools from ALL providers bound to this target
            tools_to_bind: list[Tool] = []
            
            for provider in providers:
                if isinstance(provider, ToolProvider):
                    provider_tools = provider.get_tools()
                    tools_to_bind.extend(provider_tools)
                    
                    logger.debug(f"Provider {type(provider).__name__} provided {len(provider_tools)} tools")
                    
                    # Register each tool by name in the registry AND populate aligner
                    for tool in provider_tools:
                        self._tool_registry[tool.meta.name] = tool
                        logger.debug(f"  Registered tool: {tool.meta.name}")
                        
                        # Populate tool_aligner in the same loop
                        if self.tool_aligner is not None:
                            self.tool_aligner.add_tool(tool.meta.name, tool.arg_names)
                            logger.debug(f"  Added to aligner with args: {tool.arg_names}")
                else:
                    logger.warning(f"Object bound to {target} is not ToolProvider: {type(provider)}")
                    continue
                
            model = self.get_chat_model(target)
            model.bind_tools(tools_to_bind)
            logger.info(f"Bound {len(tools_to_bind)} tools to model '{target}'")



    def get_chat_model(self, name: str):
        model = self.get_resource(name)
        throw_if_not_chatmodel(model)
        return model

    def __execute__(self, task_context: str) -> AgentExecutionResult:
        raise RuntimeError("AgentProvider.__execute__ not implemented")

    def execute_agent(self, task_context: str) -> AgentExecutionResult:
        """
        Dispatches execution to the __execute__ method.
        
        :param task_context: List of context strings for the current task/transition.
        :return: (StateResult, OutputString)
        """
        result = self.__execute__(task_context=task_context)
        try:
            if self._schema is not None:
                result.output = json_repair.repair_json(result.output)
                parsed_json = json.loads(result.output)
                
                validate(instance=parsed_json, schema=self._schema_validator)
                if "tool_calls" in parsed_json:
                    logger.debug("Output with tool_calls validated")
                elif "content" in parsed_json:
                    logger.debug("Output with content validated")
                else:
                    logger.debug("Output validated")
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse JSON output: {result.output}")
        except Exception as e:
            raise RuntimeError(f"Error processing output: {str(e)}")

        self._history.commit(result)
        return result

    def add_socket(self, socket_name: str, description: str, memory: MemoryLedger):
        self._sockets[socket_name] = AgentSocket(
            name=socket_name,
            description=description,
            memory=memory
        )
        logger.info("Socket added to agent", extra={
            "agent_class": self.__class__.__name__,
            "socket_name": socket_name,
            "description": description
        })

    @property
    def history(self) -> List[str]:
        return self._history.get_history()

    @property
    def latest_history(self) -> str:
        return self._history.get_last_snapshot()
    
    def get_latest_messages(self) -> Dict[str, str]:
        result = {}
        for name, socket in self._sockets.items():
            result[name] = socket.read_latest()
        return result

    def get_latest_message(self, socket_name: str) -> str:
        return self._sockets[socket_name].read_latest()

    def get_new_socket_messages(self, socket_name: str) -> List[str]:
        return self._sockets[socket_name].read_new_history()

    def get_new_messages(self) -> dict[str, List[str]]:
        result = {}
        for name, socket in self._sockets.items():
            if socket.has_new_messages:
                result[name] = socket.read_new_history()
        return result

    def _create_default_output_schema(self, user_schema_validator: dict[str, Any]) -> dict[str, Any]:
        """
        Creates a default output schema with 'content' field (containing user schema) 
        and optional 'tool_calls' field.
        """
        return {
            "type": "object",
            "properties": {
                "content": user_schema_validator,
                "tool_calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "args": {"type": "object"}
                        },
                        "required": ["name", "args"]
                    },
                    "minItems": 1
                }
            },
            "anyOf": [
                {"required": ["content"]},
                {"required": ["tool_calls"]}
            ],
            "additionalProperties": False
        }

    def define_output_schema(self, schema: dict[str, Any], schema_validator: dict[str, Any]):
        """
        Define the expected output schema for this agent.
        If tools are bound to the model, this will create a unified schema that allows
        either tool calls OR the expected output format.
        """
        from pipiline_agent.core.chat import BaseChatModel
        
        self._schema = schema
        self._original_schema_validator = schema_validator
        
        has_tools = False
        try:
            for resource_name in self._resources:
                resource = self._resources[resource_name]
                if isinstance(resource, BaseChatModel) and len(resource.get_tools()) > 0:
                    has_tools = True
                    break
        except Exception:
            pass
        
        if has_tools:
            self._schema_validator = self._create_default_output_schema(schema_validator)
            
            self._schema_prompt = SystemMessage(
                content=f"""Output must be in JSON format.
When you need to call tools: {{"tool_calls": [{{"name": "tool_name", "args": {{...}}}}]}}
When providing final answer: {{"content": {schema}}}
Note: Output only 'tool_calls' when calling tools, then 'content' with the final result after tools execute."""
            )
        else:
            self._schema_validator = schema_validator
            self._schema_prompt = SystemMessage(content=f"Output must be in JSON format with the following fields: {schema}")
        
        logger.info("Output schema defined", extra={
            "agent_class": self.__class__.__name__,
            "schema": self._schema,
            "schema_validator": self._schema_validator,
            "has_tools": has_tools
        })
        if self._schema_prompt:
            logger.info("Schema prompt configured", extra={
                "agent_class": self.__class__.__name__,
                "schema_prompt": self._schema_prompt.content
            })

    @property
    def schema_prompt(self) -> SystemMessage | None:
        return self._schema_prompt

    def add_sysprompt(self, prompt: str):
        self._sysprompts.append(SystemMessage(content=prompt))
        logger.info("System prompt added", extra={
            "agent_class": self.__class__.__name__,
            "sysprompt": prompt
        })

    @property
    def sysprompts(self) -> List[SystemMessage]:
        return self._sysprompts

    def append_sysprompts(self, prompts: List[Any]):
        prompts.extend(self._sysprompts)
    
    def _execute_single_tool(self, tool_name: str, tool_args: dict[str, Any]) -> ToolMessage:
        """
        Execute a single tool with timing and logging.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool
            
        Returns:
            ToolMessage with the tool execution result
            
        Raises:
            KeyError: If tool not found in registry
            Exception: If tool execution fails
        """
        import time
        start_time = time.time()
        
        tool_result = self.get_tool_from_registry(tool_name)(**tool_args)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"  Tool '{tool_name}' completed in {duration_ms:.2f}ms")
        logger.debug(f"  Result preview: {str(tool_result)[:100]}...")
        
        return ToolMessage(tool_name=tool_name, content=str(tool_result))
    
    def _attempt_tool_alignment(self, tool_name: str, tool_args: dict[str, Any]) -> ToolMessage | None:
        """
        Attempt to align and execute a malformed tool call.
        Handles both tool name and argument name misalignment.
        
        Args:
            tool_name: Original (potentially misspelled) tool name
            tool_args: Original (potentially with misspelled keys) tool arguments
            
        Returns:
            ToolMessage if alignment and execution succeeded, None otherwise
        """
        if self.tool_aligner is None:
            return None
        
        logger.warning(f"  Tool '{tool_name}' not found, attempting alignment...")
        from pipiline_agent.core.chat import ToolCall
        
        # Attempt to align both tool name and argument names
        aligned_call = self.tool_aligner.align_tool_call(
            ToolCall(name=tool_name, args=tool_args)
        )
        
        if aligned_call is None:
            logger.error(f"  Tool alignment failed for '{tool_name}'")
            return None
        
        logger.info(f"  Aligned '{tool_name}' -> '{aligned_call.name}'")
        if tool_args != aligned_call.args:
            logger.debug(f"  Aligned args: {tool_args} -> {aligned_call.args}")
        
        try:
            # Execute the aligned tool call
            return self._execute_single_tool(aligned_call.name, aligned_call.args)
        except Exception as e:
            logger.error(f"  Aligned tool '{aligned_call.name}' execution failed: {e}")
            raise

    def handle_tool_calls(self, message: ChatResponse) -> list[ToolMessage] | None:
        """
        Handle tool calls from the model response.
        Supports both native tool_calls and JSON-formatted tool calls.
        Includes intelligent alignment for misspelled tool names and arguments.
        """
        results: list[ToolMessage] = []
        
        tool_calls_to_process = message.tool_calls
        
        logger.info(f"Model requested {len(tool_calls_to_process)} tool call(s)")
        
        # Process each tool call
        for idx, tool_call in enumerate(tool_calls_to_process, 1):
            tool_name = tool_call.name
            tool_args = tool_call.args
            
            logger.info(f"Tool call {idx}/{len(tool_calls_to_process)}: {tool_name}")
            logger.debug(f"  Arguments: {tool_args}")
            
            try:
                # Attempt to execute the tool as specified
                result = self._execute_single_tool(tool_name, tool_args)
                results.append(result)
                
            except KeyError as e:
                # Tool not found - attempt alignment if available
                aligned_result = self._attempt_tool_alignment(tool_name, tool_args)
                
                if aligned_result is not None:
                    results.append(aligned_result)
                else:
                    # Alignment failed or unavailable
                    error_msg = f"Tool '{tool_name}' not found in registry"
                    if self.tool_aligner is None:
                        error_msg += " (no aligner available)"
                    else:
                        error_msg += " and alignment failed"
                    logger.error(f"  {error_msg}")
                    raise RuntimeError(error_msg) from e
                    
            except Exception as e:
                logger.error(f"  Tool '{tool_name}' execution failed: {e}")
                raise
        
        logger.debug(f"All tools completed. Returning {len(results)} result(s)")
        return results

    def get_tool_from_registry(self, name: str) -> Tool:
        if name not in self._tool_registry:
            raise KeyError(f"Tool '{name}' not found in registry.")
        return self._tool_registry[name]