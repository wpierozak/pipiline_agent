# Agent Module

## Overview

The `agent` module provides concrete agent implementations built on top of the core framework. These agents combine resource management, tool usage, and specialized behavior to accomplish specific tasks within the pipeline system.

## Classes

### PlainSimpleAgent

Base agent class that orchestrates prompt construction from multiple sources: system prompts, output schema instructions, conversation history, and messages from other agents via sockets.

**Constructor Parameters:**
- `model_name` (str): Name of the LLM model resource to use
- `sys_prompt` (str): System prompt for the agent
- `tool_args` (dict[str, Any], optional): Arguments for tool initialization

**Key Methods:**
- `__execute__(task_context: str)`: Execute the agent with given task context
- `_invoke_model(prompt: str, history_prompt: str, latest_messages_prompt: List[str])`: Invoke the model with constructed prompts

**Example Usage:**
```python
agent = PlainSimpleAgent(
    model_name="llm",
    sys_prompt="You are a helpful assistant"
)
result = agent.execute_agent("Analyze this code...")
```

---

### Simple

Basic agent with LLM resource injection. Inherits from `PlainSimpleAgent` and `ResourceUser`.

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")

**Constructor Parameters:**
- `sys_prompt` (str): System prompt for the agent

**Example Usage:**
```python
from pipiline_agent.agent.simple import Simple

agent = Simple(sys_prompt="You are a code reviewer")
# Resources are injected automatically via ResourceProvider
result = agent.execute_agent("Review this function...")
```

---

### Reviewer

Specialized agent with structured output schema validation for review decisions. Returns JSON output with review explanation and approve/disapprove decision.

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")

**Output Schema:**
```json
{
  "review": "explanation of the decision",
  "decision": "APPROVE or DISAPPROVE"
}
```

**Constructor Parameters:**
- `sys_prompt` (str): System prompt for review criteria

**Example Usage:**
```python
from pipiline_agent.agent.simple import Reviewer

reviewer = Reviewer(sys_prompt="Review code quality and security")
result = reviewer.execute_agent("Code to review...")
# Returns structured JSON with review and decision
```

---

### Verifier

Agent for FSM state transition verification. Returns the name of the next state.

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")

**Output Schema:**
```json
{
  "next_state": "name of the next state"
}
```

**Constructor Parameters:**
- None (uses empty system prompt)

**Example Usage:**
```python
from pipiline_agent.agent.simple import Verifier

verifier = Verifier()
result = verifier.execute_agent("Verify transition conditions...")
```

---

### PythonCoder

Agent specialized for creating Python scripts. Provides tools for script creation, execution, and workspace management through [PythonWorkSpace](../coding/python_tools.py).

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")
- `tool_aligner`: Tool name/argument alignment (category="tool_aligner", rid="tool_aligner")
- `workspace`: Python workspace tools (category="tools", rid="python_workspace")
- `python_coder_prompt` (optional): System prompt resource (category="sysprompt", rid="python_coder_prompt")

**Output Schema:**
```json
{
  "script_path": "relative path to created script",
  "summarization": "summarization of the created script"
}
```

**Constructor Parameters:**
- `sys_prompt` (str, optional): Custom system prompt
- `workspace_path` (str, default="./workspace"): Path to working directory
- `use_venv` (bool, default=False): Whether to create virtual environment

**Available Tools:**
- `create_script(relative_path, content)`: Create a new Python script
- `overwrite_script(relative_path, content)`: Overwrite existing script
- `run_script(script_path, args, run_background)`: Execute a script
- `monitor_process(timeout, min_time)`: Monitor background process
- `write_to_stdin(content)`: Send input to background process

**Example Usage:**
```python
from pipiline_agent.agent.simple import PythonCoder

coder = PythonCoder(
    sys_prompt="Create efficient Python code",
    workspace_path="./my_workspace",
    use_venv=True
)
result = coder.execute_agent("Create a script to process CSV files...")
```

---

### PythonCodeTester

Agent for testing Python scripts. Similar to PythonCoder but specialized for verification and testing.

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")
- `workspace`: Python workspace tools (category="tools", rid="python_workspace")
- `python_tester_prompt` (optional): System prompt resource (category="sysprompt", rid="python_tester_prompt")

**Output Schema:**
```json
{
  "test_result": "result of the test",
  "passed": "indicates if the tested script passed"
}
```

**Constructor Parameters:**
- `sys_prompt` (str, optional): Custom system prompt
- `workspace_path` (str, default="./workspace"): Path to working directory
- `use_venv` (bool, default=False): Whether to create virtual environment

**Example Usage:**
```python
from pipiline_agent.agent.simple import PythonCodeTester

tester = PythonCodeTester(workspace_path="./my_workspace")
result = tester.execute_agent("Test the data processing script...")
```

---

### BuildAnalyzer

> **⚠️ Note**: This agent uses patterns that may be deprecated. It's designed for Jenkins build log analysis using RAG.

Agent for analyzing build logs using retrieval-augmented generation.

**Resource Dependencies:**
- `model`: LLM factory (category="llm", rid="llm")

**Constructor Parameters:**
- `system_prompt` (str): Prompt for build analysis

**Key Methods:**
- `__execute__(task_context: str)`: Generic execution (simplified implementation)
- `analyze_build(build: Build, search_phrase: str)`: Original build analysis method (preserved for reference)

## Architecture Patterns

### Resource Injection

All agents use the `ResourceUser` pattern from [core](../core/README.md) for dependency injection:

```python
class MyAgent(ResourceUser, BaseAgent):
    model: Annotated[LLMFactory, resource(category="llm", rid="llm")]
    
    def __init__(self):
        super().__init__()
        # Resources automatically injected
```

### Output Schema Definition

Agents can define structured output schemas for validation:

```python
self.define_output_schema(
    schema_validator={
        "type": "object",
        "properties": {
            "field_name": {"type": "string"}
        },
        "required": ["field_name"]
    },
    schema={
        "field_name": "description"
    }
)
```

### Tool Integration

Agents integrate tools through the `ToolUser` pattern:

```python
workspace: Annotated[PythonWorkSpaceFactory, 
                     ToolsDefinition(name="workspace", bind_to="model")]
```

## Dependencies

- [core.agents](../core/agents.py) - BaseAgent, ResourceUser
- [core.resources](../core/resources.py) - Resource factories
- [core.chat](../core/chat.py) - ChatResponse
- [coding.python_tools](../coding/python_tools.py) - PythonWorkSpace
