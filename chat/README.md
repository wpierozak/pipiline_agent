# Chat Module

## Overview

The `chat` module provides chat model implementations and utilities for interacting with language models. It includes abstractions for tool calling, response handling, and tool name/argument alignment using embeddings.

## Classes

### ChatOllama

Ollama-based chat model implementation that extends `BaseChatModel`.

**Constructor Parameters:**
- `host` (str): Ollama server host URL
- `model` (str): Model name to use
- `connection` (dict[str,str] | None): Additional connection parameters

- `thinking` (bool, default=False): Enable thinking mode for supported models
- `use_induced_toolcalls` (bool, default=False): Use JSON-formatted tool calls instead of native

**Key Methods:**
- `invoke(messages: list[Message]) -> ChatResponse`: Send messages and get response
- `get_host() -> str`: Get the configured host URL

**Features:**
- Native Ollama tool calling support
- Induced tool calls via JSON format (when `use_induced_toolcalls=True`)
- Thinking mode for reasoning-capable models
- Automatic message format conversion

**Example Usage:**
```python
from pipiline_agent.chat.chat_ollama import ChatOllama

# Basic usage
chat = ChatOllama(
    host="http://localhost:11434",
    model="llama2",
    connection=None
)

# With thinking mode
chat_thinking = ChatOllama(
    host="http://localhost:11434",
    model="deepseek-r1",
    connection=None,
    thinking=True
)

# Invoke the model
response = chat.invoke([
    SystemMessage(content="You are a helpful assistant"),
    HumanMessage(content="Hello!")
])
```

---

### ToolCall

Data class representing a tool invocation request.

**Fields:**
- `name` (str): Name of the tool to call
- `args` (dict[Any, Any]): Arguments dictionary for the tool

---

### ChatResponse

Data class representing a chat model's response.

**Fields:**
- `role` (str | None): Role of the responder (e.g., "assistant")
- `content` (str | None): Text content of the response
- `tool_calls` (list[ToolCall] | None): List of tool calls, if any

---

### ToolAligner

Aligns tool names and arguments using both lexical (fuzzy matching) and semantic (embedding) similarity. Extends the [Aligner](../embeddings/aligner.py) class.

**Constructor Parameters:**
- `model_name` (str): Embedding model name
- `tool_name_lexical_threshold` (float): Lexical threshold for tool names (0-1)
- `tool_name_semantic_threshold` (float): Semantic threshold for tool names (0-1)
- `tool_args_lexical_threshold` (float): Lexical threshold for arguments (0-1)
- `tool_args_semantic_threshold` (float): Semantic threshold for arguments (0-1)
- `threads` (int, default=1): Number of threads for embedding model

**Key Methods:**
- `add_tool(name: str, args: list[str])`: Register a tool with its valid arguments
- `align_tool_call(toolcall: ToolCall) -> ToolCall | None`: Align misspelled tool call to registered tools

**Purpose:**
When an LLM makes a tool call with slightly incorrect spelling (e.g., "create_scrpt" instead of "create_script"), the aligner can correct it using fuzzy matching and embedding similarity.

**Example Usage:**
```python
from pipiline_agent.core.chat import ToolAligner, ToolCall

aligner = ToolAligner(
    model_name="BAAI/bge-small-en-v1.5",
    tool_name_lexical_threshold=0.9,
    tool_name_semantic_threshold=0.75,
    tool_args_lexical_threshold=0.9,
    tool_args_semantic_threshold=0.75
)

# Register tools
aligner.add_tool("create_script", ["relative_path", "content"])
aligner.add_tool("run_script", ["script_path", "args"])

# Align misspelled tool call
misspelled = ToolCall(name="creat_script", args={"rel_path": "test.py"})
corrected = aligner.align_tool_call(misspelled)
# Returns: ToolCall(name="create_script", args={"relative_path": "test.py"})
```

---

### BaseChatModel

Abstract base class for all chat model implementations. Provides common functionality for tool binding, tool call parsing, and message handling.

**Constructor Parameters:**
- `name` (str): Name identifier for the model

**Key Methods:**
- `invoke(messages: list[Message]) -> ChatResponse`: Invoke the model (must be implemented by subclasses)
- `bind_tools(tools: list[Tool], induce: bool = False)`: Bind tools to the model
- `get_tools() -> list[Tool]`: Get bound tools
- `create_tool_instruction() -> str`: Generate tool usage instructions
- `parse_toolcall_list(toolcall: str) -> list[ToolCall]`: Parse JSON-formatted tool calls

**Tool Call Format:**
```json
{
  "tool_calls": [
    {
      "name": "ClassName.tool_name",
      "args": {"arg1": "value1"}
    }
  ]
}
```

**Example Implementation:**
```python
class MyCustomChat(BaseChatModel):
    def __init__(self):
        super().__init__("my_model")
    
    def invoke(self, messages: list[Message]) -> ChatResponse:
        # Custom implementation
        pass
```

## Tool Calling Modes

### Native Tool Calling

The model natively supports tool calling and returns structured tool call objects:

```python
chat = ChatOllama(host="...", model="...", use_induced_toolcalls=False)
response = chat.invoke(messages)
# response.tool_calls contains structured ToolCall objects
```

### Induced Tool Calling

The model doesn't natively support tools, so tool calls are induced via JSON in the content:

```python
chat = ChatOllama(host="...", model="...", use_induced_toolcalls=True)
response = chat.invoke(messages)
# Model returns JSON in content, parsed into tool_calls
```

## Dependencies

- [core.messages](../core/messages.py) - Message types
- [core.tools](../core/tools.py) - Tool definitions
- [embeddings.aligner](../embeddings/aligner.py) - Embedding-based alignment
- `ollama` - Ollama Python client
- `json_repair` - JSON parsing with error correction
