from enum import Enum

class StateType(Enum):
    STABLE = "STABLE"
    TRANSIENT = "TRANSIENT"
    ERROR = "ERROR"
    END = "END"
    START = "START"

class StateResult(Enum):
    NEXT = "NEXT"
    ERROR = "ERROR"
    END = "END"
