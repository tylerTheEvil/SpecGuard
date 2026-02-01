import os
import json
from textwrap import dedent
from typing import List, Dict

import pandas as pd
from openai import OpenAI

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


DEFAULT_REQUIREMENTS: List[Dict[str, str]] = [
    {"id": "R1", "text": "The module must transition to SAFE_STATE when an error occurs."},
    {"id": "R2", "text": "After reset, the system must enter SAFE_STATE."},
    {"id": "R3", "text": "The counter must not overflow."},
]

DEFAULT_HDL_CODE = """\
module watchdog (
    input  wire clk,
    input  wire reset_n,
    input  wire error_flag,
    output reg  [1:0] state
);

localparam SAFE_STATE  = 2'b00;
localparam RUN_STATE   = 2'b01;
localparam ERROR_STATE = 2'b10;

always @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
        state <= SAFE_STATE;
    end else begin
        case (state)
            SAFE_STATE:  if (!error_flag) state <= RUN_STATE;
            RUN_STATE:   if (error_flag)  state <= ERROR_STATE;
            ERROR_STATE: if (!error_flag) state <= SAFE_STATE;
            default:     state <= SAFE_STATE;
        endcase
    end
end

endmodule
"""


def load_requirements() -> List[Dict[str, str]]:
    """Return the default requirements list."""
    return DEFAULT_REQUIREMENTS


def load_hdl_code() -> str:
    """Return the demo HDL code."""
    return DEFAULT_HDL_CODE


def analyze_requirements_with_llm(
    requirements: List[Dict[str, str]], hdl_code: str
) -> List[Dict[str, str]]:
    system_prompt = dedent(
        """
        You are an HDL (Verilog/VHDL) verification assistant.
        You receive:
        - A list of requirements
        - HDL code

        For EACH requirement:
        - Determine whether it is satisfied by the HDL code ("yes", "partial", "no", "uncertain")
        - Provide a relevant code snippet or approximate lines
        - Add a short explanation

        Return the answer STRICTLY as a JSON list:
        [
          {
            "id": "R1",
            "status": "yes/partial/no/uncertain",
            "code_snippet": "...",
            "comment": "..."
          }
        ]
        """
    )

    user_prompt = {
        "role": "user",
        "content": f"Requirements:\\n{requirements}\\n\\nHDL code:\\n{hdl_code}",
    }

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "system", "content": system_prompt}, user_prompt],
    )

    # Responses API returns a structured object; pull the raw text and parse JSON.
    content = (
        getattr(response, "output_text", None)
        or (response.output[0].content[0].text if getattr(response, "output", None) else "")
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse LLM output: {content}") from exc


def normalize_requirements_with_llm(freeform_requirements: List[str]) -> List[Dict[str, str]]:
    """Turn free-form requirement text into structured id/text pairs via LLM."""
    system_prompt = dedent(
        """
        You turn free-form requirements into a structured list.
        For each requirement, produce:
        - id: sequential labels R1, R2, ...
        - text: concise, explicit requirement text

        Return ONLY a JSON list like:
        [
          {"id": "R1", "text": "..."},
          {"id": "R2", "text": "..."}
        ]
        """
    )

    user_prompt = {
        "role": "user",
        "content": f"Free-form requirements:\\n{freeform_requirements}",
    }

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "system", "content": system_prompt}, user_prompt],
    )

    content = (
        getattr(response, "output_text", None)
        or (response.output[0].content[0].text if getattr(response, "output", None) else "")
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse LLM output: {content}") from exc


def build_traceability_table(llm_result: List[Dict[str, str]]) -> pd.DataFrame:
    """Convert the LLM output into a tabular view."""
    return pd.DataFrame(llm_result)
