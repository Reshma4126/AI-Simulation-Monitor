from typing import Any, Dict
from langchain_core.runnables import Runnable
from .state import SharedState


class BaseAgent:
    name: str = "base_agent"
    result_key: str = "result"
    timeout_sec: int = 60

    def build_agent(self, llm) -> Runnable:
        raise NotImplementedError()

    def build_input(self, state: SharedState) -> Dict[str, Any]:
        return {"input_data": state.get("input_data", "")}

    def run(self, llm, state: SharedState) -> Any:
        agent = self.build_agent(llm)
        inputs = self.build_input(state)
        # Using invoke since it's a synchronous graph
        return agent.invoke(inputs)
