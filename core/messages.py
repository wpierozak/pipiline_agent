class Message:
    def __init__(self, content: str, role: str):    
        self.content: str = content
        self.role: str = role

class SystemMessage(Message):
    def __init__(self, content: str):
        super().__init__(role = SystemMessage.role(), content = content)
    @classmethod
    def role(cls) -> str:
        return "system"

    def __str__(self):
        return f"{self.role}: {self.content}"
    
class HumanMessage(Message):
    def __init__(self, content: str):
        super().__init__(role = HumanMessage.role(), content = content)
    @classmethod
    def role(cls) -> str:
        return "user"
    
class AIMessage(Message):
    def __init__(self, content: str, tool_calls: list = None):
        super().__init__(role = AIMessage.role(), content = content)
        self.tool_calls = tool_calls or []

    @classmethod
    def role(cls) -> str:
        return "assistant"
    
class ToolMessage(Message):
    def __init__(self, tool_name: str, content: str):
        super().__init__(role = ToolMessage.role(), content = content)
        self.tool_name = tool_name
    @classmethod
    def role(cls) -> str:
        return "tool"