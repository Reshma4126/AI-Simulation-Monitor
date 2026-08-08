from typing import Any, NotRequired, TypedDict


class SharedState(TypedDict):
    session_id:        str
    input_data:        str
    subagent_1_result: NotRequired[Any]   # closed-loop analysis
    subagent_2_result: NotRequired[Any]   # protocol compliance
    subagent_3_result: NotRequired[Any]   # callout quality
    subagent_4_result: NotRequired[Any]   # synthesis / error correction
    combined_result:   NotRequired[Any]   # final merged output
