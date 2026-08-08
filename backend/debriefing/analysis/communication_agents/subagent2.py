from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser

from .core.base_agent import BaseAgent
from .core.prompt_loader import load_prompt_parts
from .core.state import SharedState


class SubAgent2(BaseAgent):
    name = "subagent_2"
    result_key = "subagent_2_result"
    
    def build_agent(self, llm) -> Runnable:
        system_prompt = load_prompt_parts(
            "prompts/system_core.md",
            "prompts/subagent2.md",
        )
        human_template = "Analyze the following transcript for protocol compliance:\n\n{input_data}\n\nContext from previous step:\n{phi_1}"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_template),
        ])
        
        return prompt | llm | StrOutputParser()

    def build_input(self, state: SharedState) -> dict:
        return {
            "input_data": state.get("input_data", ""),
            "phi_1": state.get("subagent_1_result", "None"),
        }
