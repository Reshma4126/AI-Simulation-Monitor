import json
import logging
from typing import Dict, Any

from .communication_agents.agent import SupervisingAgent

logger = logging.getLogger(__name__)


class NLPEngine:
    """
    Bridge between our diarization output and the LangGraph multi-agent NLP system.
    """
    def __init__(self, llm=None):
        if llm is None:
            # Load environment variables just in case
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            try:
                # Try Ollama (local/WSL)
                from langchain_ollama import ChatOllama
                import urllib.request
                ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

                # Prefer localhost (WSL2 port-forwards it automatically).
                # Only fall back to the WSL bridge IP if localhost doesn't respond.
                base_url = "http://localhost:11434"
                try:
                    urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
                except Exception:
                    # localhost didn't work — try the WSL bridge IP
                    import subprocess
                    try:
                        wsl_ip = subprocess.check_output(
                            ['wsl', 'hostname', '-I'], text=True
                        ).strip().split()[0]
                        base_url = f"http://{wsl_ip}:11434"
                    except Exception:
                        pass  # keep localhost as last resort

                self.llm = ChatOllama(model=ollama_model, temperature=0.2, base_url=base_url)
                logger.info(f"NLPEngine initialized with local Ollama model: {ollama_model} at {base_url}")
            except ImportError:
                try:
                    # Try Groq (cloud)
                    from langchain_groq import ChatGroq
                    self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
                    logger.warning("NLPEngine initialized with Groq cloud model.")
                except Exception as e:
                    # Fallback to Fake LLM so testing passes without keys
                    from langchain_core.language_models import FakeListLLM
                    logger.warning("No LLM key or local model found. Falling back to FakeListLLM for testing.")
                    self.llm = FakeListLLM(responses=[
                        "Mock SubAgent1: Closed-loop communication analyzed.",
                        "Mock SubAgent2: Protocol compliance verified.",
                        "Mock SubAgent3: Callout communications checked.",
                        "Mock SubAgent4: No errors detected in synthesis."
                    ])
        else:
            self.llm = llm
            
        self.agent = SupervisingAgent(llm_instance=self.llm)

    def format_segments_for_nlp(self, segments) -> str:
        """
        Converts the list of TranscriptionResult objects into a structured text format
        that the NLP agents can easily read and analyze.
        """
        formatted = []
        for idx, seg in enumerate(segments, 1):
            time_str = getattr(seg, 'start_time_str', '00:00')
            speaker = getattr(seg, 'speaker', 'UNKNOWN')
            role = getattr(seg, 'actor_role', None)
            role_str = role.name if role else 'UNKNOWN'
            text = getattr(seg, 'text', '')
            
            line = f"[{time_str}] {speaker} ({role_str}): {text}"
            formatted.append(line)
            
        return "\n".join(formatted)

    def process(self, session_id: str, segments: list) -> Dict[str, Any]:
        """
        Process the transcript through the 4-agent NLP pipeline.
        """
        logger.info(f"Formatting {len(segments)} segments for NLP analysis...")
        transcript_text = self.format_segments_for_nlp(segments)
        
        logger.info(f"Running multi-agent NLP analysis for session: {session_id}...")
        result_state = self.agent.run(session_id=session_id, input_data=transcript_text)
        
        # Extract the final combined result from the graph state
        combined = result_state.get("combined_result", {})
        
        # Calculate some top-level metrics to pass back to the rest of the engine
        # For now, just pass the agent outputs directly. The scoring engine can consume these.
        return {
            "nlp_analysis": combined,
            "closed_loop_rate": 0.0, # Placeholder until scoring engine is attached
            "raw_transcript": transcript_text
        }
