from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser

from .core.base_agent import BaseAgent
from .core.prompt_loader import load_prompt_parts
from .core.state import SharedState


class SubAgent3(BaseAgent):
    name = "subagent_3"
    result_key = "subagent_3_result"
    
    def build_agent(self, llm) -> Runnable:
        system_prompt = load_prompt_parts(
            "prompts/system_core.md",
            "prompts/subagent3.md",
        )
        human_template = "Analyze the following transcript for callout communications:\n\n{input_data}"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_template),
        ])
        
        return prompt | llm | StrOutputParser()
