import os
import sys
import re
import json
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import AgentTool
from google.adk.workflow import Workflow, START, node, Edge
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput

# MCP Server integration imports
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.config import config

# Initialize Gemini Model using config settings
model = Gemini(
    model=config.model,
    retry_options=types.HttpRetryOptions(attempts=config.max_iterations),
)

# Dynamically resolve absolute path to mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[mcp_server_path],
        )
    )
)

# -----------------------------------------------------------------------------
# Specialist Agents
# -----------------------------------------------------------------------------

HEALTH_INSTRUCTION = """You are GramMitra's Health Companion, designed for rural users.
Provide friendly, simple, and empathetic health guidance.
For any symptoms described:
1. Suggest possible common causes (clearly state this is informational, not a professional medical diagnosis).
2. Give basic first-aid or home care advice.
3. Highlight emergency warning signs (red flags) where they must seek immediate medical attention.
4. Suggest finding nearby clinics or doctors.
Use your get_nearby_clinics tool when the user asks about clinics or medical centers near a specific location.
Speak in the language chosen by the user (e.g., Kannada, Hindi, English). Keep sentences short and clear."""

health_agent = LlmAgent(
    name="health_agent",
    model=model,
    instruction=HEALTH_INSTRUCTION,
    description="Resolves health issues, symptoms, first-aid advice, and medical questions.",
    tools=[mcp_toolset],
)

AGRI_INSTRUCTION = """You are GramMitra's Agriculture Advisor, helping rural farmers.
Analyze crop issues, yellowing leaves, pests, and plant diseases.
Provide clear:
1. Identification of the potential crop disease or pest.
2. Confidence level of your analysis.
3. Organic and chemical treatment recommendations.
4. Fertilizer and irrigation suggestions.
5. Preventive measures to protect other crops.
Use your get_disease_info tool to look up treatment/prevention recommendations for specific crops and diseases.
Use search_crop_database to find optimal soil, fertilizer, and irrigation conditions for specific crops.
Respond in the language of the user. Keep it highly practical and actionable for farmers. Supporting image analysis is enabled."""

agri_agent = LlmAgent(
    name="agri_agent",
    model=model,
    instruction=AGRI_INSTRUCTION,
    description="Resolves agriculture questions, crop diseases, yellowing leaves, soil, and farming issues.",
    tools=[mcp_toolset],
)


# -----------------------------------------------------------------------------
# Orchestrator Agent
# -----------------------------------------------------------------------------

ORCHESTRATOR_INSTRUCTION = """You are the lead coordinator of GramMitra AI, a rural health and agriculture assistant.
Your job is to direct the user's request to the correct specialist agent using the tools provided:
- If the user asks about human health, symptoms, first aid, or medical care, delegate to health_agent.
- If the user asks about crop issues, plant diseases, soil, pests, or farming advice, delegate to agri_agent.
Do not answer these queries yourself; always delegate to the respective specialist agent using their tool.
Return the specialist's analysis directly."""

orchestrator = LlmAgent(
    name="orchestrator",
    model=model,
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[AgentTool(health_agent), AgentTool(agri_agent)],
    description="Orchestrator that routes user inputs to health_agent or agri_agent.",
)

# -----------------------------------------------------------------------------
# Workflow Nodes
# -----------------------------------------------------------------------------

@node
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    """Checks input query safety, scrubs PII, detects injection and logs decisions."""
    # Extract text from incoming user content
    text = ""
    if hasattr(node_input, "parts") and node_input.parts:
        text = "".join([p.text for p in node_input.parts if p.text])
    elif isinstance(node_input, str):
        text = node_input

    original_text = text
    severity = "INFO"
    decision = "pass"
    flagged_reason = ""

    # 1. PII Scrubbing
    # Phone numbers (Indian format/generic 10 digits)
    phone_pattern = re.compile(r"\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b")
    # Aadhaar cards (12 digits)
    aadhaar_pattern = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
    # Emails
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    scrubbed_text = original_text
    if phone_pattern.search(scrubbed_text):
        scrubbed_text = phone_pattern.sub("[PHONE_REDACTED]", scrubbed_text)
        flagged_reason += "PII_PHONE "
    if aadhaar_pattern.search(scrubbed_text):
        scrubbed_text = aadhaar_pattern.sub("[AADHAAR_REDACTED]", scrubbed_text)
        flagged_reason += "PII_AADHAAR "
    if email_pattern.search(scrubbed_text):
        scrubbed_text = email_pattern.sub("[EMAIL_REDACTED]", scrubbed_text)
        flagged_reason += "PII_EMAIL "

    # 2. Prompt Injection Detection
    injection_keywords = ["system prompt", "ignore previous instructions", "bypass security", "jailbreak", "override instructions", "developer mode"]
    lower_text = original_text.lower()
    for kw in injection_keywords:
        if kw in lower_text:
            severity = "CRITICAL"
            decision = "block"
            flagged_reason += f"PROMPT_INJECTION_DETECTED ({kw}) "
            break

    # 3. Domain Specific Filter (Prescription check / Restricted Agro-Chemicals)
    restricted_keywords = ["prescribe me", "dosage of", "antibiotic dosage", "paraquat", "monocrotophos"]
    for kw in restricted_keywords:
        if kw in lower_text:
            severity = "WARNING"
            decision = "block"
            flagged_reason += f"RESTRICTED_SUBSTANCE_OR_PRESCRIPTION_QUERY ({kw}) "
            break

    # If blocked, we override scrubbed_text with an explanation
    if decision == "block":
        output_text = flagged_reason.strip()
    else:
        output_text = scrubbed_text

    # Write Structured JSON Audit Log
    log_entry = {
        "timestamp": ctx.session.id,
        "severity": severity,
        "input_length": len(original_text),
        "decision": decision,
        "flagged_reason": flagged_reason.strip() if flagged_reason else "none",
        "pii_redacted": scrubbed_text != original_text
    }
    print(f"[AUDIT_LOG] {json.dumps(log_entry)}")

    # Route to correct node
    return Event(output=output_text, route=decision)

@node
def security_block(node_input: str) -> Event:
    """Triggers if query is flagged as unsafe."""
    msg = f"Access Denied: Security Checkpoint blocked this query. Reason: {node_input}"
    return Event(
        output=msg,
        content=types.Content(role='model', parts=[types.Part.from_text(text=msg)])
    )


@node(rerun_on_resume=True)
async def disclaimer_gate(ctx: Context, node_input: Any):
    """Enforces disclaimer approval (Human-in-the-Loop) before showing output."""
    # Extract string response from Orchestrator
    text_content = ""
    if isinstance(node_input, str):
        text_content = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        text_content = "".join([p.text for p in node_input.parts if p.text])
    else:
        text_content = str(node_input)

    # Store pending response in session state
    ctx.state["pending_response"] = text_content

    # Skip gate if already agreed in this session
    if ctx.state.get("disclaimer_agreed"):
        yield Event(output=text_content, route="approved")
        return

    # Check for HITL response
    if ctx.resume_inputs and "disclaimer_accept" in ctx.resume_inputs:
        user_response = ctx.resume_inputs["disclaimer_accept"].strip().lower()
        if user_response in ["agree", "yes", "y", "agree to continue"]:
            ctx.state["disclaimer_agreed"] = True
            pending = ctx.state.get("pending_response", "")
            yield Event(output=pending, route="approved")
            return
        else:
            msg = "You must agree to the disclaimer to see the guidance. Please type 'agree' to continue."
            yield Event(output=msg, route="denied")
            return

    # Request consent
    disclaimer_msg = (
        "⚠️ DISCLAIMER: GramMitra AI provides informational guidance only. "
        "It does not replace professional medical or agricultural advice. "
        "Please type 'agree' to proceed and view your response."
    )
    yield RequestInput(interrupt_id="disclaimer_accept", message=disclaimer_msg)

@node
def final_output(node_input: str) -> Event:
    """Renders final output to the user interface."""
    return Event(
        output=node_input,
        content=types.Content(role='model', parts=[types.Part.from_text(text=node_input)])
    )

# -----------------------------------------------------------------------------
# Workflow Definition
# -----------------------------------------------------------------------------

grammitra_workflow = Workflow(
    name="grammitra_workflow",
    edges=[
        (START, security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=security_block, route="block"),
        Edge(from_node=security_checkpoint, to_node=orchestrator, route="pass"),
        (orchestrator, disclaimer_gate),
        (disclaimer_gate, final_output),
    ],
    description="Orchestrates health and agriculture routing, security checks, and human disclaimer confirmation."
)

root_agent = grammitra_workflow

app = App(
    root_agent=grammitra_workflow,
    name="app",
)
