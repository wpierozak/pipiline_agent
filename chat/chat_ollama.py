from pipiline_agent.core.chat import BaseChatModel, ToolCall, ChatResponse
from pipiline_agent.core.messages import Message, ToolMessage, SystemMessage
from typing import Any, Sequence
import ollama
import copy
import logging

logger = logging.getLogger(__name__)

class ChatOllama(BaseChatModel):
    def __init__(self, host: str, model: str, connection: dict[str,str] | None, thinking: bool = False, use_induced_toolcalls : bool = False ):
        super().__init__(model)
        self.__host = host
        self.__model = model
        self.__thinking = thinking
        if connection is None:
            connection = {}
        self.__client = ollama.Client(host = host, **connection)
        self.__induced_tool = use_induced_toolcalls
        if self.__induced_tool:
            logger.info(f"Induced tool mode is active")

    def invoke(self, messages: list[Message]) -> ChatResponse:
        converted = self.__convert_messages(messages)
        tools = self.get_tools()
        
        logger.debug(f"Invoking model '{self.__model}' with {len(converted)} messages and {len(tools)} tools")
        if self.__induced_tool:
            messages.append(SystemMessage(content=self.create_tool_instruction()))
            response = self.__client.chat(
                model=self.__model,
                messages=converted,
                think=self.__thinking
            )
        else:
            response = self.__client.chat(
                model=self.__model,
                messages=converted,
                tools=tools,
                think=self.__thinking
            )
        
        converted_response = self.__convert_resposne(response)
        
        # Log response details
        has_content = converted_response.content is not None and converted_response.content != ""
        has_tools = converted_response.tool_calls is not None and len(converted_response.tool_calls) > 0
        
        if has_tools:
            logger.info(f"Model response: {len(converted_response.tool_calls)} tool call(s)")
        if has_content:
            logger.info("Model output captured", extra={
                "model_content": converted_response.content,
                "content_length": len(converted_response.content)
            })
        
        return converted_response

    def __convert_tool_calls(self, calls: Sequence[Any] | None) -> list[ToolCall] | None:
        if calls is None:
            return None
        return [ToolCall(name = call.function.name, args = call.function.arguments) for call in calls]
    
    def __convert_resposne(self, response: ollama.ChatResponse) -> ChatResponse:
        tool_calls: list[ToolCall] = []
        if self.__induced_tool:
            tool_calls = self.parse_toolcall_list(response.message.content)
        else: 
            tool_calls = self.__convert_tool_calls(response.message.tool_calls)
        return ChatResponse(role = response.message.role,
                            content = response.message.content,
                            tool_calls = tool_calls)

    def __convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        converted = []
        for message in messages:
            if isinstance(message, ToolMessage):
                converted.append({"role": "tool", "content": message.content, "tool_name": message.tool_name})
            else:
                converted.append({"role": message.role, "content": message.content})
        return converted
    
    def get_host(self):
        return self.__host
