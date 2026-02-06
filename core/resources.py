from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Annotated, get_type_hints, get_origin, get_args, Protocol, runtime_checkable
from pathlib import Path
import yaml
import copy
import importlib
import logging
import fastembed

from pipiline_agent.chat.chat_ollama import ChatOllama
from pipiline_agent.core.chat import BaseChatModel, ChatResponse


from pipiline_agent.chat.chat_ollama import ChatOllama

logger = logging.getLogger(__name__)
    
from unittest.mock import MagicMock

def throw_if_not_chatmodel(obj):
    if isinstance(obj, BaseChatModel) == False:
        raise RuntimeError(f"Object of class {obj.__class__.__name__} is not a chat model!")

@dataclass(frozen=True)
class ResourceMeta:
    category: str
    rid: str

def resource(category: str, rid: str) -> ResourceMeta:
    return ResourceMeta(category=category, rid=rid)

@runtime_checkable
class ResourceFactory(Protocol):
    def create(self) -> Any:
        ...

class LLMFactory(ResourceFactory):
    def __init__(self, config: dict):
        self.config = config

    def create(self) -> Any:
        config = self.config
        if config['type'] == 'ollama':
            if ChatOllama is None:
                raise ImportError("langchain_ollama is not installed")
            return ChatOllama(
                host = config.get("host"),
                model = config.get('model'),
                connection=config.get("connection"),
                use_induced_toolcalls=eval(str(config.get("induced_tools", "False"))),
                thinking = config.get("thinking") if "thinking" in config.keys() else None
            )
        elif config['type'] == 'mock':
            mock_llm = MagicMock()
            def side_effect(messages):
                content = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                return ChatResponse(role="assistant", content=f"Mock response to: {content[:20]}...", tool_calls=None)
            mock_llm.invoke.side_effect = side_effect
            # Mock bind_tools to return self (or a copy)
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            return mock_llm
        else:
            raise ValueError(f"Unknown LLM type: {config['type']}")

# class EmbeddingsFactory(ResourceFactory):
#     def __init__(self, config: dict):
#         self.config = config

#     def create(self) -> Any:
#         config = self.config
#         if config['type'] == 'localai_embeddings':
#             if LocalAIEmbeddings is None:
#                 raise ImportError("langchain_localai is not installed")
#             return LocalAIEmbeddings(
#                 base_url=config['base_url'],
#                 model=config.get('model_name', 'text-embedding-ada-002')
#             )
#         else:
#              raise ValueError(f"Unknown Embedding type: {config['type']}")

class ToolAlignerFactory(ResourceFactory):
    def __init__(self, config: dict):
        self.config = config
    
    def create(self) -> Any:
        from pipiline_agent.core.chat import ToolAligner
        
        config = self.config
        model_name = config.get('model_name', 'BAAI/bge-small-en-v1.5')
        threads = config.get('threads', 1)
        
        tool_name_lexical = config.get('tool_name_lexical_threshold', 85.0)
        tool_name_semantic = config.get('tool_name_semantic_threshold', 0.7)
        tool_args_lexical = config.get('tool_args_lexical_threshold', 80.0)
        tool_args_semantic = config.get('tool_args_semantic_threshold', 0.65)
        
        logger.info(f"Creating ToolAligner with model={model_name}, threads={threads}")
        
        return ToolAligner(
            model_name=model_name,
            tool_name_lexical_threshold=tool_name_lexical,
            tool_name_semantic_threshold=tool_name_semantic,
            tool_args_lexical_threshold=tool_args_lexical,
            tool_args_semantic_threshold=tool_args_semantic,
            threads=threads
        )

class SysPromptFactory(ResourceFactory):
    def __init__(self, config: dict, config_base_path: str):
        self.config = config
        self.config_base_path = config_base_path

    def create(self) -> str:
        config = self.config
        if 'txt' in config:
            return config['txt']
        elif 'source' in config:
            path = Path(config['source'])
            if not path.is_absolute():
                 # Resolve relative to config file location
                 path = Path(self.config_base_path).parent / path
            if not path.exists():
                 raise ValueError(f"Sysprompt source file not found: {path}")
            return path.read_text()
        else:
            raise ValueError("Sysprompt resource must have 'txt' or 'source' field.")

class ResourceUser:
    _resource_cache: dict[str, ResourceMeta] | None = None

    def __init__(self) -> None:
        self._resources = {}
        for name in self.resources(only_declared_here=False):
            if hasattr(self.__class__, name):
                storage = getattr(self.__class__, name)
                
                value = None
                if isinstance(storage, ResourceFactory):
                    value = storage.create()
                else:
                   raise RuntimeError(f"Resource {name} is not a factory")

                setattr(self, name, value)
                self._resources[name] = getattr(self, name)
    
    def get_resource(self, name: str):
        return self._resources[name]

    def update_resource(self, name: str, value: Any):
        self._resources[name] = value
        setattr(self, name, value)

    @classmethod
    def setup(cls, resource_name: str, resource_obj: Any) -> None:
        """
        Injects a resource (Factory or Object) into the class.
        """
        setattr(cls, resource_name, resource_obj)

    @classmethod
    def resources(cls, *, only_declared_here: bool = True) -> dict[str, ResourceMeta]:
        hints = get_type_hints(cls, include_extras=True)

        if only_declared_here:
            local_keys = getattr(cls, "__annotations__", {}).keys()
            names = [k for k in local_keys if k in hints]
        else:
            names = hints.keys()

        out: dict[str, ResourceMeta] = {}
        for name in names:
            anno = hints[name]
            if get_origin(anno) is Annotated:
                metadata = get_args(anno)[1:]
                meta = next(
                    (m for m in metadata if isinstance(m, ResourceMeta)),
                    None
                )
                
                if meta is not None:
                    out[name] = meta
        return out

class ResourceProvider:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.resources = {}
        self.config = self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def _get_or_create_resource(self, name: str):
        if name in self.resources:
            return self.resources[name]
        
        resource_config = self.config['resources'].get(name)
        if not resource_config:
             raise ValueError(f"Resource '{name}' not found in configuration.")

        if 'type' not in resource_config:
             raise ValueError(f"Resource '{name}' missing 'type' field.")
        
        category = resource_config.get('category')
        
        factory = None
        # if category == 'embeddings':
        #      factory = EmbeddingsFactory(resource_config)
        if category == 'llm':
             factory = LLMFactory(resource_config)
        elif category == 'sysprompt':
             factory = SysPromptFactory(resource_config, self.config_path)
        elif category == 'tool_aligner':
             factory = ToolAlignerFactory(resource_config)
        else:
             raise ValueError(f"Unknown resource category: {category}")
            
        self.resources[name] = factory
        return factory

    def initialize_users(self):
        """
        Iterates over users defined in YAML and initializes them.
        """
        users_config = self.config.get('users', {})
        for user_name in users_config.keys():
            self.initialize_user(user_name)

    def initialize_user(self, user_name: str):
        """
        Initializes a single user by name, injecting resource factories.
        """
        users_config = self.config.get('users', {})
        if user_name not in users_config:
            logger.error(f"User '{user_name}' not found in configuration.")
            return

        user_conf = users_config[user_name]
        module_name = user_conf.get('module')
        class_name = user_conf.get('class')
        resources_map = user_conf.get('resources', {})

        if not module_name or not class_name:
             logger.error(f"User '{user_name}' missing module or class definition.")
             return

        try:
            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Error loading class '{class_name}' from '{module_name}' for user '{user_name}': {e}")
            return

        if not issubclass(agent_class, ResourceUser):
            logger.warning(f"Warning: {class_name} ({user_name}) does not inherit from ResourceUser.")
            return

        declared_resources = agent_class.resources()

        for field_name, resource_meta in declared_resources.items():
            rid = resource_meta.rid
            expected_category = resource_meta.category
            
            if rid not in resources_map:
                logger.warning(f"User '{user_name}' ({class_name}) requires resource with rid='{rid}' (field '{field_name}'), but it is not mapped in config.")
                continue
            
            global_resource_name = resources_map[rid]
            
            try:
                resource_factory = self._get_or_create_resource(global_resource_name)
                
                global_resource_config = self.config['resources'].get(global_resource_name, {})
                actual_category = global_resource_config.get('category')
                
                if actual_category and expected_category and actual_category != expected_category:
                    logger.warning(f"User '{user_name}' expects category '{expected_category}' for rid='{rid}', but got '{actual_category}' from resource '{global_resource_name}'.")
                
                agent_class.setup(field_name, resource_factory)
                logger.info(f"Injected Factory for '{global_resource_name}' as '{field_name}' (rid='{rid}') into {class_name} (User: {user_name})")
            except Exception as e:
                    logger.error(f"Failed to inject resource '{global_resource_name}' into '{user_name}': {e}")