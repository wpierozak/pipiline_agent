from __future__ import annotations
import inspect
import functools
import rapidfuzz
import fastembed
from dataclasses import dataclass, asdict
from typing import Any, Callable, Optional, Annotated, get_type_hints, get_origin, get_args
from function_schema import get_function_schema
from jsonschema import validate, ValidationError
import json

@dataclass(frozen=True)
class ToolMeta:
    name: str
    docs: str
    def __str__(self):
        return json.dumps(asdict(self))

def toolmethod(*, name: str):
    """Decorator to mark an *instance method* as a tool."""
    def deco(fn: Callable[..., str]) -> Callable[..., str]:
        if not inspect.isfunction(fn):
            raise TypeError("@toolmethod must decorate a normal instance method (def ...)")
        setattr(fn, "__toolmeta__", ToolMeta(name=name, docs=fn.__doc__))
        return fn
    return deco

from typing import Any, get_origin, get_args, Union, Literal

NoneType = type(None)

class Tool:
    def __init__(self, meta, binded_method):
        self.__name__ = meta.name
        self.__doc__ = meta.docs
        self.__signature__ = inspect.signature(binded_method)

        self.meta = meta
        self.binded_method = binded_method
        
        # Extract and cache argument names for tool aligner
        self._arg_names = self._extract_arg_names()
    
    def _extract_arg_names(self) -> list[str]:
        """Extract parameter names from the method signature."""
        arg_names = []
        for name, param in self.__signature__.parameters.items():
            if name == "self":
                continue
            # Skip *args / **kwargs
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD
            ):
                continue
            arg_names.append(name)
        return arg_names
    
    @property
    def arg_names(self) -> list[str]:
        """Return cached argument names."""
        return self._arg_names

    def __call__(self, **kwargs) -> str:
        return self.binded_method(**kwargs)

    def __type_to_schema(self, py_type: Any) -> dict:
        """Convert Python typing annotation to JSON Schema dict."""

        # 1) No annotation
        if py_type is inspect._empty or py_type is Any:
            return {"type": "string"}  # or {} or {"type":"object"}

        origin = get_origin(py_type)
        args = get_args(py_type)

        # 2) Optional / Union
        if origin is Union:
            # Optional[T] == Union[T, NoneType]
            non_none = [a for a in args if a is not NoneType]
            has_none = len(non_none) != len(args)

            # If it's exactly Optional[T]
            if has_none and len(non_none) == 1:
                inner_schema = self.__type_to_schema(non_none[0])
                return {"anyOf": [inner_schema, {"type": "null"}]}

            # General union
            return {"anyOf": [self.__type_to_schema(a) for a in args]}

        # 3) Literal
        if origin is Literal:
            return {"enum": list(args)}

        # 4) List / array
        if origin in (list,):
            item_schema = {"type": "string"}
            if args:
                item_schema = self.__type_to_schema(args[0])
            return {"type": "array", "items": item_schema}

        # 5) Dict / object
        if origin in (dict,):
            # Dict[K, V]
            value_schema = {"type": "string"}
            if len(args) == 2:
                value_schema = self.__type_to_schema(args[1])
            return {"type": "object", "additionalProperties": value_schema}

        # 6) Basic types
        basic_map = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            NoneType: {"type": "null"},
        }
        if py_type in basic_map:
            return basic_map[py_type]

        # 7) Fallback for unknown types/classes
        return {"type": "string"}

    def schema(self) -> str:
        signature = inspect.signature(self.binded_method)

        properties = {}
        required = []

        for name, param in signature.parameters.items():
            if name == "self":
                continue

            # Skip *args / **kwargs (optional design choice)
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD
            ):
                continue

            prop_schema = self.__type_to_schema(param.annotation)

            # include default if present (nice-to-have)
            if param.default is not inspect.Parameter.empty:
                prop_schema["default"] = param.default
            else:
                required.append(name)

            properties[name] = prop_schema

        return json.dumps({
            "type": "function",
            "function": {
                "name": self.meta.name,
                "description": self.meta.docs or "",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }, indent=2)


class ToolProvider:
    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        
        # Get the class name for prefixing
        class_name = self.__class__.__name__

        # Only plain functions defined on the class => instance methods when bound.
        for method_name, func in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            meta: ToolMeta | None = getattr(func, "__toolmeta__", None)
            if meta is None:
                continue

            bound_method = getattr(self, method_name)  # bound => `self` is not in the tool signature
            
            # Create a new ToolMeta with class name prefix
            prefixed_meta = ToolMeta(
                name=f"{class_name}.{meta.name}",
                docs=meta.docs
            )

            tools.append(
                Tool(
                    meta=prefixed_meta,
                    binded_method=bound_method
                )
            )

        return tools

    
def throw_if_not_toolprovider(obj):
    if not isinstance(obj, ToolProvider):
        raise RuntimeError(f"Object of class {obj.__class__.__name__} is not a ToolProvider!")

def throw_if_not_tool(obj):
    if not isinstance(obj, Tool):
        raise RuntimeError(f"Object of class {obj.__class__.__name__} is not a Tool!")

class ToolFactory:
    def __init__(self, result_type: type):
        self.result_type = result_type
    
    def create(self, args: dict):
        """Unrolls the dict and creates the instance."""
        try:
            return self.result_type(**args)
        except TypeError as e:
            raise TypeError(f"Failed to create {self.result_type.__name__}: {e}")

@dataclass(frozen=True)
class ToolsDefinition:
    name: str
    bind_to: str

class ToolUser:
    def __init__(self, args: dict[str,dict[str, Any]]):
        hints = get_type_hints(self.__class__, include_extras=True)
        names = hints.keys()
        self.__tools_by_target: dict[str, Any] = {}

        for name in names:
            anno = hints[name]
            if get_origin(anno) is not Annotated:
                continue
            
            metadata = get_args(anno)[1:]
            meta = next(
                (m for m in metadata if isinstance(m, ToolsDefinition)),
                None
            )
                
            if meta is None:
                continue
            
            tools = getattr(self.__class__, name)
            if not isinstance(tools, ToolFactory):
                raise RuntimeError(f"Object of class {tools.__class__.__name__} is not a ToolFactory!")
            
            if name not in args.keys():
                raise RuntimeError(f"No arguments provided for {name}")
            
            setattr(self, name, tools.create(args[name]))
            target = meta.bind_to
            if target not in self.__tools_by_target:
                self.__tools_by_target[target] = []
            self.__tools_by_target[target].append(getattr(self, name))

    def get_tool_providers(self, name: str) -> ToolProvider:
        attr = getattr(self, name)
        throw_if_not_tool(attr)
        return attr
    
    def get_tool_providers_by_target(self) -> dict[str, list[ToolProvider]]:
        return self.__tools_by_target