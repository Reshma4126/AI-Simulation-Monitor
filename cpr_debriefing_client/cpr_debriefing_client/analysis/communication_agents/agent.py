import os
from pathlib import Path
from typing import Any, Dict

from langgraph.graph import StateGraph, START, END
from langchain_core.language_models.chat_models import BaseChatModel

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    def _create_checkpointer(path: str):
        return SqliteSaver(path)
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver
    def _create_checkpointer(path: str):
        return MemorySaver()

from .subagent1 import SubAgent1
from .subagent2 import SubAgent2
from .subagent3 import SubAgent3
from .subagent4 import SubAgent4
from .core.state import SharedState


CHECKPOINT_PATH = str(Path(__file__).with_name("state.db"))


class SupervisingAgent:
    def __init__(self, llm_instance: BaseChatModel) -> None:
        self.llm = llm_instance
        # Branch 1: φ₁ → α₁
        self.agent1 = SubAgent1()
        self.agent2 = SubAgent2()
        # Branch 2: φ₂ → α₂
        self.agent3 = SubAgent3()
        self.agent4 = SubAgent4()
        self.checkpointer = _create_checkpointer(CHECKPOINT_PATH)

    def _run_agent(self, agent, state: SharedState) -> Dict[str, Any]:
        result = agent.run(self.llm, state)
        return {agent.result_key: result}

    def _node_agent1(self, state: SharedState) -> Dict[str, Any]:
        return self._run_agent(self.agent1, state)

    def _node_agent2(self, state: SharedState) -> Dict[str, Any]:
        return self._run_agent(self.agent2, state)

    def _node_agent3(self, state: SharedState) -> Dict[str, Any]:
        return self._run_agent(self.agent3, state)

    def _node_agent4(self, state: SharedState) -> Dict[str, Any]:
        return self._run_agent(self.agent4, state)

    def _combine_results(self, state: SharedState) -> Dict[str, Any]:
        combined = {
            "branch_1": {
                "closed_loop_analysis": state.get("subagent_1_result"),
                "protocol_compliance": state.get("subagent_2_result"),
            },
            "branch_2": {
                "callout_validation": state.get("subagent_3_result"),
                "error_correction": state.get("subagent_4_result"),
            },
        }
        return {"combined_result": combined}

    def build_graph(self):
        graph = StateGraph(SharedState)

        graph.add_node("agent1", self._node_agent1)
        graph.add_node("agent2", self._node_agent2)
        graph.add_node("agent3", self._node_agent3)
        graph.add_node("agent4", self._node_agent4)
        graph.add_node("supervisor_combine", self._combine_results)

        graph.add_edge(START, "agent1")
        graph.add_edge(START, "agent3")

        graph.add_edge("agent1", "agent2")
        graph.add_edge("agent3", "agent4")

        graph.add_edge("agent2", "supervisor_combine")
        graph.add_edge("agent4", "supervisor_combine")

        graph.add_edge("supervisor_combine", END)

        return graph.compile(checkpointer=self.checkpointer)

    def run(self, session_id: str, input_data: str) -> Dict[str, Any]:
        graph = self.build_graph()
        initial_state: SharedState = {
            "session_id": session_id,
            "input_data": input_data,
        }
        config = {"configurable": {"thread_id": session_id}}
        return graph.invoke(initial_state, config=config)
