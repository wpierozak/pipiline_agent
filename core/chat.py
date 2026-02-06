from __future__ import annotations
from pipiline_agent.core.messages import Message
from pipiline_agent.core.tools import Tool
from dataclasses import dataclass
from typing import Mapping, Any
from pipiline_agent.core.json_utils import strip_json_output
from pipiline_agent.embeddings.aligner import Aligner, AlignerPool
import json
import json_repair

@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Mapping[str, Any]

@dataclass(frozen=True)
class ChatResponse:
    role: str | None
    content: str | None
    tool_calls: list[ToolCall] | None

@dataclass
class ToolCall:
    name: str
    args: dict[Any,Any]


class ToolAligner(Aligner):
    def __init__(self, model_name, tool_name_lexical_threshold, tool_name_semantic_threshold, tool_args_lexical_threshold, tool_args_semantic_threshold, threads=1):
        super().__init__(model_name=model_name, threads=threads)
        self.create_pool("tools", tool_name_lexical_threshold, tool_name_semantic_threshold)
        self.__tool_args_lexical_threshold = 100 * tool_args_lexical_threshold
        self.__tool_args_semantic_threshold = tool_args_semantic_threshold

    def add_tool(self, name: str, args: list[str]):
        self.get_pool("tools").add(model=self.model,
                                phrase=name)
        args_pool = self.create_pool(name + "#args",
                                     lexical_threshold=self.__tool_args_lexical_threshold,
                                     semantic_threshold=self.__tool_args_semantic_threshold)
        for arg in args:
            args_pool.add(model=self.model,
                          phrase=arg)

    def align_tool_call(self, toolcall: ToolCall) -> ToolCall | None:
        name = self.get_pool("tools").match(model=self.model, query=toolcall.name)
        if name is None:
            return None
        corrected_args = {}
        tool_args_pool : AlignerPool = self.get_pool(name + "#args") 
        for arg in toolcall.args.keys():
            matched_arg = tool_args_pool.match(self.model, arg)
            if matched_arg is None:
                return None
            corrected_args[matched_arg] = toolcall.args[arg]
        return ToolCall(name, corrected_args)

class BaseChatModel:
    def __init__(self, name: str):
        self.__name = name
        self.__tools : list[Tool] = []

    def call(self, messages: list[Message]) -> ChatResponse:
        return self.invoke(messages)
    
    def invoke(self, messages: list[Message]) -> ChatResponse:
        raise RuntimeError()
    
    def bind_tools(self, tools: list[Tool], induce: bool = False):
        import logging
        logger = logging.getLogger(__name__)
        
        self.__tools.extend(tools)
        logger.info("Tools bound to chat model", extra={
            "model_name": self.__name,
            "tool_count": len(tools),
            "tool_names": [t.meta.name for t in tools]
        })
        for tool in tools:
            logger.debug("Tool schema", extra={
                "model_name": self.__name,
                "tool_name": tool.meta.name,
                "tool_docs": tool.meta.docs,
                "tool_schema": tool.schema()
            })

    def get_tools(self) -> list[Tool]:
        return self.__tools
    
    @staticmethod
    def tool_call_instructon()->str:
        return """
# Tool Invocation Protocol
You have access to the following tools. When the user's request requires using a tool, follow this protocol:

1. **Format:** Output strictly valid JSON
2. **Structure:** {"tool_calls": [{"name": "<class_name>.<tool_name>", "args": <arguments_dict>}]}
3. **Multiple Tools:** Include multiple tool call objects in the tool_calls array
4. **Important:** Do NOT include other fields when calling tools - ONLY the tool_calls field
5. **Tool Name:** Remember that tool name has class prefix

## STRICT FORMATTING EXAMPLES

User: "What is the weather in Tokyo?"
Assistant:
{"tool_calls": [{"name": "Weather.get_weather", "args": {"location": "Tokyo", "unit": "celsius"}}]}

User: "Email John and check the server status."
Assistant:
{"tool_calls": [{"name": "Email.send_email", "args": {"recipient": "john@example.com", "body": "Hello"}}, {"name": "Server.check_server", "args": {"target": "localhost"}}]}

## Available Tools
        """

    @staticmethod
    def tool_call_section_header()->str:
        return "```tool_call"

    @staticmethod
    def get_tool_call_schema() -> dict[str, Any]:
        """
        Returns the JSON schema for tool call output format.
        This can be used to merge with user-defined output schemas.
        """
        return {
            "type": "object",
            "properties": {
                "tool_calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "args": {"type": "object"}
                        },
                        "required": ["name", "args"]
                    }
                }
            },
            "required": ["tool_calls"],
            "description": "Tool invocation request"
        }

    def create_tool_instruction(self):
        import logging
        logger = logging.getLogger(__name__)
        
        instruction : str = BaseChatModel.tool_call_instructon()
        for tool in self.__tools:
            instruction += tool.schema() + "\n"
        
        logger.info("Tool instruction created for model", extra={
            "model_name": self.__name,
            "tool_count": len(self.__tools),
            "instruction": instruction
        })
        
        return instruction
    
    def parse_toolcall_list(self, toolcall: str) -> list[ToolCall]:
        """
        Parse tool calls from JSON format: {"tool_calls": [{"name": "...", "args": {...}}]}
        """
        try:
            parsed_json = json_repair.loads(toolcall)
            
            if "tool_calls" not in parsed_json:
                return []
            
            tool_calls_list = parsed_json["tool_calls"]
            if not isinstance(tool_calls_list, list):
                return []
            
            return [
                ToolCall(name=tc["name"], args=tc["args"]) 
                for tc in tool_calls_list
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []