"""
Pipeline Agent - A flexible agent framework for building LLM-powered automation pipelines.

This package provides:
- Resource injection and dependency management
- Tool system for exposing Python methods to LLMs
- State machine orchestration
- Pre-built agents for various tasks
- Robust tool calling with alignment
"""

__version__ = "0.1.0"
__author__ = "wpierozak"
__license__ = "GPL-3.0-or-later"

# Core imports for convenience
from pipiline_agent.core.agents import BaseAgent, AgentExecutionResult
from pipiline_agent.core.resources import ResourceProvider, ResourceUser
from pipiline_agent.core.tools import ToolProvider, toolmethod
from pipiline_agent.core.chat import BaseChatModel, ChatResponse, ToolCall

__all__ = [
    "BaseAgent",
    "AgentExecutionResult",
    "ResourceProvider",
    "ResourceUser",
    "ToolProvider",
    "toolmethod",
    "BaseChatModel",
    "ChatResponse",
    "ToolCall",
]
