from __future__ import annotations
from typing import Callable, Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from pipiline_agent.core.memory import MemoryLedger
from pipiline_agent.core.agents import BaseAgent, AgentExecutionResult
from pipiline_agent.core.enums import StateType, StateResult
from pipiline_agent.core.resources import ResourceUser, resource, SysPromptFactory
from typing import Annotated
import logging
import uuid
import time
import json

logger = logging.getLogger(__name__)

@dataclass
class Transition:
    source: str
    target: str
    constraint: str

    def json_str(self) -> str:
        return json.dumps(asdict(self))

@dataclass
class StateExecutionResult:
    next_state: str
    output: str

class VerifierWrapper:
    def __init__(self, callback: Callable[str, str]):
        self.callback = callback

    def execute(self, context: str) -> str:
        return self.callback(context)

    def add_sysprompt(self, prompt: str):
        pass

class AgentVerifierWrapper(VerifierWrapper):
    def __init__(self, agent: BaseAgent):
        def callback(context: str) -> str:
            result: AgentExecutionResult = agent.execute_agent(task_context=context)
            return json.loads(result.output)["next_state"]
        self.agent = agent
        super().__init__(callback)

    def add_sysprompt(self, prompt: str):
        self.agent.add_sysprompt(prompt)

class ForwardVerifierWrapper(VerifierWrapper):
    def __init__(self, next_state: str):
        def callback(context: str) -> str:
            return next_state
        super().__init__(callback)


class State(ResourceUser):
    verification_pre_sysprompt: Annotated[SysPromptFactory, resource(category="sysprompt", rid="verification_pre_sysprompt")]
    def __init__(self, name: str, 
                    type: StateType, 
                    subscriptions: list[str], 
                    agent: BaseAgent | None = None,
                    verifier: VerifierWrapper | None = None,
                    description: str = "",
                    max_retries: int = 3):
        super().__init__()
        self.name = name
        self.type = type
        self.subscriptions = subscriptions
        self.agent = agent
        self.verifier = verifier
        self.description = description
        self.max_retries = max_retries
        self.retries_counter = self.max_retries

    def execute(self, context: str) -> StateExecutionResult:
        if not self.agent:
            raise RuntimeError("Agent not initialized")
            
        result: AgentExecutionResult = self.agent.execute_agent(task_context=context)
        logger.info(f"Calling transition agent", extra={"state": self.name})
        verificationResult = self.verifier.execute(context=result.json_str())
        logger.debug(f"Transition agent result: {verificationResult}", extra={"state": self.name})
        next_state = verificationResult
        logger.info(f"Transition agent decided to go to state {next_state}", extra={"state": self.name})
        
        return StateExecutionResult(next_state=next_state, 
                                    output=result.output)
    
    def reset_retries(self):
        self.retries_counter = self.max_retries

    def retry(self) -> bool:
        if self.retries_counter > 0:
            self.retries_counter -= 1
            return True
        return False
    
    def compile_transitions(self, transitions: List[Transition]):
        if self.verifier is None:
            raise RuntimeError("Verifier not initialized")
        prompt: str = self.verification_pre_sysprompt
        for transition in transitions:
            reduced_transition = {"target": transition.target, "constraint": transition.constraint}
            prompt += f"\n{json.dumps(reduced_transition)}"
        self.verifier.add_sysprompt(prompt)

    def __hash__(self):
        return hash(self.name)

class StartState(State):
    def __init__(self, name: str):
        super().__init__(name=name, type=StateType.STABLE, subscriptions=[], agent=None)
        self.target_state: str | None = None

    def compile_transitions(self, transitions: List[Transition]):
        if len(transitions) != 1:
            raise RuntimeError(f"StartState '{self.name}' must have exactly one transition.")
        self.target_state = transitions[0].target
        
    def execute(self, context: str) -> StateExecutionResult:
        if self.target_state is None:
             raise RuntimeError("StartState not compiled or no transition defined.")

        return StateExecutionResult(next_state=self.target_state, output=context)


class EndState(State):
    def __init__(self, name: str):
        super().__init__(name=name, type=StateType.END, subscriptions=[], agent=None)

    def execute(self, context: str) -> StateExecutionResult:
        return StateExecutionResult(next_state="END", output=context)

class FSM:
    def __init__(self, error_state: State):
        self.error_state = error_state
        self.memory = MemoryLedger()
        self.transitions: Dict[str, List[Transition]] = {} # One normal transition per state
        # Tracking for recovery
        
        # We need to track retries for non-transient states
        self.retry_counters: Dict[str, int] = {}
        self.captured_contexts: Dict[str, Any] = {} # Capture context when entering a stable state
        self.states: Dict[str, State] = {}
        self.initial_state: str | None = None
        self.initial_context_ledger: MemoryLedger = MemoryLedger()

    @staticmethod
    def initial_context_socket_name() -> str:
        return "__initial_context__"

    def add_state(self, state: State):
        self.states[state.name] = state
        
    def add_transition(self, transition: Transition):
        # Strict: One transition per state (plus implicit error transition)
        if transition.source not in self.states.keys():
            raise RuntimeError(f"Source state {transition.source} does not exist!")
        if transition.target not in self.states.keys():
            raise RuntimeError(f"Target state {transition.target} does not exist!")
        
        if transition.source not in self.transitions:
            self.transitions[transition.source] = []
        self.transitions[transition.source].append(transition)

    def update_listeners(self, src: str, listeners: list[str], mess: str):
        # Deprecated: usage of sockets replaced push model
        pass

    def compile(self):
        start_states = [s for s in self.states.values() if isinstance(s, StartState)]
        end_states = [s for s in self.states.values() if isinstance(s, EndState)]
        
        if len(start_states) != 1:
            raise RuntimeError(f"FSM must have exactly one StartState, found {len(start_states)}")
        
        if len(end_states) == 0:
            raise RuntimeError("FSM must have at least one EndState")
            
        self.initial_state = start_states[0].name
        
        # Validate transition from Start
        if self.initial_state not in self.transitions:
            raise RuntimeError(f"StartState '{self.initial_state}' must have an outgoing transition")
            
        # Validate transition to End (simple check if any transition points to an EndState)
        end_state_names = {s.name for s in end_states}
        reachable_end = False
        for transitions in self.transitions.values():
            for t in transitions:
                if t.target in end_state_names:
                    reachable_end = True
                    break
            if reachable_end:
                break
        
        if not reachable_end:
             raise RuntimeError("No transition points to an EndState")

        for state in self.states.values():
            #Compile transition sysprompt
            if state.name in self.transitions:
                 state.compile_transitions(self.transitions[state.name])
                 logger.info("State transitions compiled", extra={
                     "state_name": state.name,
                     "transitions": [{"target": t.target, "constraint": t.constraint} for t in self.transitions[state.name]]
                 })
            #Prepare agent
            if state.agent is None:
                continue
            for sub in state.subscriptions:
                if sub == self.initial_context_socket_name():
                    state.agent.add_socket(self.initial_context_socket_name(), "Initial Request", self.initial_context_ledger)
                    continue

                if sub not in self.states:
                    raise RuntimeError(f"State {state.name} subscribes to unknown state {sub}")
                target_state = self.states[sub]
                if target_state.agent is None:
                     logger.warning(f"State {state.name} subscribes to {sub}, which has no agent. Skipping socket.")
                     continue
                
                state.agent.add_socket(sub, target_state.description, target_state.agent._history)
                
    def transition(self, current_state: State, current_state_result: StateExecutionResult):
        transitions = self.transitions.get(current_state.name)
        transition_found = False
        current_input = current_state_result.output
        current_state_result.next_state = current_state_result.next_state.strip()

        if transitions:
            for transition in transitions:
                if transition.target == current_state_result.next_state:
                    transition_found = True    
                    logger.info(f"Transitioning: {current_state.name} -> {transition.target}", 
                                extra={"state_name": current_state.name, "target_state": transition.target, "event": "transition"})
                    current_state = self.states[transition.target]
                    break
        
        if not transition_found:
            logger.info("No transition defined or matched. Using next_state as target if exists, else match failure.", 
                        extra={"state_name": current_state.name, "event": "transition_check"})
            logger.warning(f"No transition matched decision '{current_state_result.next_state}' from {current_state.name}. Moving to ERROR.",
                           extra={"state_name": current_state.name, "decision": current_state_result.next_state, "event": "transition_error"})
            current_state = self.error_state
            
        return current_state, current_input

    def run(self, initial_request: str, max_steps: int = 1000) -> str:
        """
        Main Loop of the FSM Agent Framework.
        """
        self.initial_context_ledger = MemoryLedger()
        self.initial_context_ledger.commit(initial_request)
        
        self.compile()
        
        if self.initial_state is None:
             raise RuntimeError("Initial state could not be determined during compilation.")
        
        # Set correlation ID
        run_id = str(uuid.uuid4())
   
        current_input = initial_request
        current_context_template = "{}" # Default
        current_state = self.states[self.initial_state]
        last_stable_state_name = current_state.name

        final_output = ""

        for _ in range(max_steps):
            logger.info(f"--- Step: {current_state.name} ({current_state.type.name}) ---", 
                        extra={"state_name": current_state.name, "state_type": current_state.type.name, "step": "start"})
            logger.debug(f"--- Last stable state: {last_stable_state_name} ---")
            
            if current_state.type == StateType.END:
                logger.info("End State reached. Terminating.", 
                            extra={"state_name": current_state.name, "event": "termination_end_state"})
                final_output = output
                break
        
            if current_state.type == StateType.ERROR:
                logger.warning("In ERROR State. Attempting recovery...", extra={"state_name": current_state.name, "event": "error_recovery_start"})
                
                target_state = self.states[last_stable_state_name]
                
                if target_state.retry() > 0:
                    logger.info(f"Recovering to {target_state.name}. Retries left: {target_state.retries_counter}", 
                                extra={"state_name": current_state.name, "target_state": target_state.name, "retries_left": target_state.retries_counter, "event": "recovery_retry"})
                    current_state = self.states[last_stable_state_name]
                    continue
                else:
                    logger.error(f"Recovery failed. Max retries exceeded for {target_state.name}.", 
                                    extra={"state_name": current_state.name, "target_state": target_state.name, "event": "recovery_failed"})
                    
                    final_output = "FAILED"
                    break

            # --- 2. PREPARE CONTEXT ---
            if current_state.type == StateType.STABLE:
                if current_state.name != last_stable_state_name:
                    current_state.reset_retries()
                last_stable_state_name = current_state.name
            
            # --- 3. EXECUTE STATE ---
            start_time = time.time()
            try:
                logger.info(f"Executing Agent...", extra={"state_name": current_state.name, "event": "execution_start"})
                result = current_state.execute(current_input)
                output = result.output
                duration = (time.time() - start_time) * 1000
                logger.debug(f"State: {current_state.name} | Result: {result.next_state}", 
                                extra={"state_name": current_state.name, "result": result.next_state, "duration_ms": duration, "event": "execution_complete"})
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.exception(f"Execution Exception: {e}", 
                                    extra={"state_name": current_state.name, "event": "execution_exception", "duration_ms": duration})
                result = StateExecutionResult(next_state="ERROR", output=str(e))
                output = str(e)

            logger.info("State output captured", extra={
                "state_name": current_state.name,
                "output": output,
                "output_length": len(output) if output else 0
            })
            # Transition
            current_state, current_input = self.transition(current_state, result)
           
        return final_output
