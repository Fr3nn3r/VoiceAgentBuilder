"""
OpenAI function tool schemas for scheduling operations.

Defines the structure and parameters for scheduling tools used by the AI agent.
These schemas conform to OpenAI's function calling specification.
"""

# Tool 1: Check availability
CHECK_AVAILABILITY_SCHEMA = {
    "type": "function",
    "name": "check_availability_true_false",
    "description": "Check if an appointment slot is available. Returns true if slot is free, false if occupied. MUST be called before booking.",
    "parameters": {
        "type": "object",
        "properties": {
            "start_datetime": {
                "type": "string",
                "description": "Start time in ISO 8601 format (e.g., '2025-11-15T10:30:00')",
            },
            "end_datetime": {
                "type": "string",
                "description": "End time in ISO 8601 format. Should be start + 30 minutes.",
            },
        },
        "required": ["start_datetime", "end_datetime"],
    },
}

# Tool 2: Book appointment
BOOK_APPOINTMENT_SCHEMA = {
    "type": "function",
    "name": "book_appointment",
    "description": "Book a confirmed appointment. Call ONLY ONCE after: (1) all patient info collected, (2) availability confirmed, (3) patient confirmed the time.",
    "parameters": {
        "type": "object",
        "properties": {
            "start_datetime": {
                "type": "string",
                "description": "Confirmed appointment start time (ISO 8601)",
            },
            "end_datetime": {
                "type": "string",
                "description": "Confirmed appointment end time (ISO 8601)",
            },
            "patient_name": {
                "type": "string",
                "description": "Full name of the patient",
            },
            "birth_date": {
                "type": "string",
                "description": "Birth date of patient (for new patients only, optional)",
            },
            "phone_number": {
                "type": "string",
                "description": "Patient's phone number",
            },
            "reason": {
                "type": "string",
                "description": "Reason for visit / consultation reason",
            },
            "comments": {
                "type": "string",
                "description": "Additional notes or comments (optional)",
            },
        },
        "required": [
            "start_datetime",
            "end_datetime",
            "patient_name",
            "phone_number",
            "reason",
        ],
    },
}

# Tool 3: Calendar agent query
CALENDAR_AGENT_SCHEMA = {
    "type": "function",
    "name": "calendar_agent",
    "description": "Submit a calendar management request from a manager to a secretary. The query is a concise, military-style instruction describing the desired action.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Military-style natural language request (e.g., 'Schedule weekly sync with product team next Tuesday 1300-1400 UTC').",
            },
        },
        "required": ["query"],
    },
}

# Tool 4: Search agent query
SEARCH_AGENT_SCHEMA = {
    "type": "function",
    "name": "search_agent",
    "description": "Execute a concierge-style search action such as finding hotels, restaurants, or flights. Provide the manager's request verbatim.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search request (e.g., 'Find a boutique hotel in Paris for next weekend').",
            },
        },
        "required": ["query"],
    },
}

# Disabled: Close call tool (was closing before agent finished speaking)
# CLOSE_CALL_SCHEMA = {
#     "type": "function",
#     "name": "close_call",
#     "description": "End the call and hang up. Use this IMMEDIATELY after saying goodbye when the conversation is complete.",
#     "parameters": {
#         "type": "object",
#         "properties": {},
#         "required": [],
#     },
# }
