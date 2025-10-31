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
            "summary": {
                "type": "string",
                "description": "Appointment summary in format: 'Medical Appointment | {patient_name}'",
            },
        },
        "required": ["start_datetime", "end_datetime", "summary"],
    },
}

# Tool 3: Log appointment details
LOG_APPOINTMENT_SCHEMA = {
    "type": "function",
    "name": "log_appointment_details",
    "description": "Log all appointment details. Call IMMEDIATELY after booking, ONLY ONCE per appointment.",
    "parameters": {
        "type": "object",
        "properties": {
            "event": {
                "type": "string",
                "description": "Event type: 'Booked', 'Cancelled', etc.",
            },
            "date": {"type": "string", "description": "Appointment date"},
            "start_time": {"type": "string", "description": "Start time"},
            "end_time": {"type": "string", "description": "End time"},
            "patient_name": {"type": "string", "description": "Full name"},
            "birth_date": {
                "type": "string",
                "description": "Birth date (for new patients)",
            },
            "phone_number": {"type": "string", "description": "Phone number"},
            "reason": {"type": "string", "description": "Reason for visit"},
        },
        "required": [
            "event",
            "date",
            "start_time",
            "end_time",
            "patient_name",
            "phone_number",
            "reason",
        ],
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
