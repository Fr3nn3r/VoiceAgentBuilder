# 🚀 Executive Summary

### Problem
Our medical voice agent (built with LiveKit + Azure OpenAI Realtime) works, but we currently **can’t see what happens inside each call**. When the agent is slow or fails to book an appointment, it’s impossible to know whether the cause was network lag, AI response time, or tool errors. This makes debugging difficult and compliance auditing nearly impossible.

### Solution
Implement **LangSmith tracing** to capture end-to-end session data: when each call starts, when the user and agent speak, how long the agent takes to respond (TTFT-A), which tools are used, and any errors.  
Telemetry is fully **asynchronous (<1 ms overhead)** and **privacy-safe** — all personal or medical data is redacted before sending.

### Investment & Risk
- **Duration:** 6 weeks  
- **Ongoing cost:** ≈ $40/month (LangSmith + Azure + LiveKit)  
- **Risk:** Low — telemetry runs off the audio path.  
- **Rollback trigger:** If Week 5 audit finds a PHI leak or latency > 5 ms, telemetry is disabled and launch postponed 2 weeks.

### Go / No-Go Gate
Launch proceeds only if **Week 5 compliance audit passes** and latency overhead remains ≤ 1 ms.

### Decision Log (summary)
- **LangSmith over Langfuse:** better Realtime + OpenAI integration, simpler setup  
- **Two environments only:** dev + prod keep complexity low  
- **No data warehouse:** LangSmith’s 90-day retention sufficient for MVP  
- **Full instrumentation, no sampling:** volume < 10 calls/day  

---

# 🩺 Observability PRD — Medical Voice Agent (MVP)

## 1. Ownership

| Role | Person / System | Responsibility |
|------|-----------------|----------------|
| **Project Owner (DRI)** | **Frédéric Brunner** | Delivery, prioritization, budget |
| **Implementation Lead** | **Claude Code** | Coding, integration, testing |
| **Sign-off** | **Frédéric Brunner** | Product & compliance approval |

---

## 2. Objective
Give full visibility into every call handled by the voice agent — duration, latency, errors, and tool activity — while protecting patient privacy and keeping cost and overhead minimal.

---

## 3. Technical Stack

| Component | Purpose |
|------------|----------|
| **LiveKit Cloud** | Real-time voice transport (WebRTC SFU) |
| **Azure OpenAI Realtime API** | Speech → AI → Speech (ASR + LLM + TTS) |
| **LangSmith Cloud** | Tracing + metrics + dashboards + alerts |
| **Slack (#agent-ops)** | Incident notifications |
| **Python 3.11+ / LiveKit Agents SDK** | Core implementation language |

---

## 4. Scope

**Included**
- Session start/end tracing  
- Turn-level metrics (user_turn / agent_turn)  
- Five instrumented tools  
- Inline PHI redaction  
- Minimal WebRTC metrics (RTT, jitter, loss)  
- Slack alerts for key issues  
- Compliance audit & rollback plan  

**Excluded**
- Long-term trend analytics  
- Staging environment  
- Sampling or data warehouse  

---

## 5. Cost Breakdown

| Item | Estimate / Month | Notes |
|------|------------------|-------|
| **LangSmith** | $0 | Free tier (≤ 1 M traces) |
| **Azure OpenAI Realtime** | ≈ $25 | 10 calls / day |
| **LiveKit Cloud** | ≈ $15 | Audio streaming |
| **Total ≈** | **$40 / month** | Target < $50 ✅ |

---

## 6. Key Terms
*(for new team members)*  

- **Trace:** all telemetry for one call  
- **Span:** one event inside a trace (e.g., “tool call”)  
- **Turn:** user → agent → user interaction  
- **TTFT-A:** time from user stop → first agent audio  
- **Telemetry:** metrics sent to LangSmith  
- **Redaction:** masking private info before sending  
- **PHI / PII:** protected or personally identifiable data  

---

## 7. Success Criteria

**Functional**
- One trace per call  
- Trace includes: `session.start`, ≥ 1 `agent_turn`, `session.end`, and tool spans  
- Errors logged with `error_type` + `error_message`

**Performance**
- Overhead ≤ 1 ms per op (target) / 5 ms (max)  
- Span drop < 1 %  
- Agent never crashes from telemetry errors  

**Compliance**
- 0 PHI leaks (auto + manual tests)  
- Redaction unit tests pass  
- Audit record (`policy.guardrail`) per session  

**Cost**
- LangSmith free tier only  
- Total ≤ $50/month  

---

## 8. Instrumentation Design

### Trace Structure
```
voice_session
├─ session.start
├─ user_turn
│   └─ metadata: audio_ms, timestamp
├─ agent_turn
│   ├─ metadata: ttft_ms, input_tokens, output_tokens, cost_usd
│   └─ tool.*
└─ session.end
```

### TTFT-A Measurement
Calculated from Azure Realtime events:  
`TTFT-A = response.audio.delta.timestamp − input_audio_buffer.speech_stopped.timestamp`

### Latency Budget
| Stage | Expected ms |
|--------|-------------|
| Span creation | 0.5 |
| Async send | 0 |
| **Total** | **< 1 ms** ✅ |

### Correlation & Metadata
Each trace has `trace_id`, `room_id`, `participant_id`, `env`, and timestamps.

### Error Handling
Telemetry never stops the agent:
```python
try:
    with run.create_child(...): ...
except Exception as e:
    logger.error(f"Telemetry failed: {e}")
```

---

## 9. Tools to Instrument

| Tool | Purpose |
|-------|----------|
| `tool.check_availability` | Check availabilty of a single slot |
| `tool.book_appointment` | Create a new appointment |
| `tool.cancel_appointment` | Cancel an appointment |
| `tool.reschedule_appointment` | Move appointment time |
| `tool.get_opening_hours` | Retrieve doctor/clinic schedule |
| `tool.get_medical_guidelines` | Fetch medical guidance text |

Post-MVP: new tools require redaction review.

---

## 10. Redaction Policy

| Field | Treatment | Example |
|--------|-----------|----------|
| patient_name, phone, email, dob, mrn, address | REDACT | `<REDACTED>` |
| reason_for_visit, notes, symptoms | TRUNCATE 50 chars | “Mild fever…” |
| appointment_datetime | KEEP (if no patient ID) | `2025-11-15T14:00Z` |
| confirmation_id, doctor_name, clinic_location | KEEP | Safe metadata |

Validation: automated regex tests + manual audit (10 traces).

---

## 11. Privacy & Compliance

- No audio/transcripts sent to LangSmith.  
- Recording URLs excluded.  
- Each session includes `policy.guardrail` span with consent info.  
- PHI redaction verified before deployment.  

---

## 12. Media Quality Metrics
- **Sample every 10 s:** RTT, jitter, packet loss %  
- Collected via `getStats()` on client  
- Stored as session metadata (not spans)  
- Overhead < 0.1 ms  

---

## 13. Implementation Approach & Week-by-Week Gates

| Week | Focus | Deliverable | Exit Criteria |
|------|--------|-------------|----------------|
| 1 | Setup | LangSmith project + test trace | ✅ “Hello-world” trace visible |
| 2 | Session tracing | Add `session.start/end` | ✅ 10 test calls show complete traces |
| 3 | Tool tracing | Wrap 5 tools + redaction | ✅ Zero PII in 20 sample spans |
| 4 | Metrics & alerts | Compute TTFT-A + 3 Slack alerts | ✅ Alerts trigger correctly |
| 5 | Validation | Load test + compliance audit | ✅ < 1 ms overhead, no PHI found |
| 6 | Production | Deploy + 48 h monitoring | ✅ Stable, alerts clean |

---

## 14. Reference Code Patterns

### Non-Blocking Telemetry
```python
agent.on("user_speech_committed",
         lambda e: asyncio.create_task(log_user_turn(e, session_run)))

async def log_user_turn(event, parent_run):
    try:
        with parent_run.create_child(name="user_turn") as turn_run:
            turn_run.end()
    except Exception as e:
        logger.error(f"Telemetry failed: {e}")
```

### Tool Redaction
```python
async def book_appointment(patient_name, phone, datetime):
    with langsmith.get_current_run_tree().create_child(
        name="tool.book_appointment",
        inputs={"patient_name":"<REDACTED>","phone":"<REDACTED>","datetime":datetime}
    ) as tool_run:
        result = await booking_system.create(...)
        tool_run.end(outputs={"confirmation_id": result.id})
```

---

## 15. Dashboards & Alerts

**Built-in LangSmith Dashboard**
- Session list  
- Latency histogram (p50/p95/p99)  
- Error rate, cost per session  

**Slack Alerts**
1. Error rate > 5 % (1 h)  
2. TTFT-A p95 > 3 s (15 m)  
3. Tool failure > 10 % (30 m)  
Prefix messages with `[ENV][OBS]`.

---

## 16. Data Retention & Environments

| Item | Policy |
|------|--------|
| **Retention** | LangSmith 90 days |
| **Long-term** | Manual CSV/API export if needed |
| **Sampling** | Add after > 100 calls/day |
| **Environments** | `medical-voice-agent-dev` and `medical-voice-agent-prod` only |

---

## 17. Testing & Validation

- **Unit:** trace ID propagation, redaction, error handling  
- **Integration:** full call → trace appears in LangSmith  
- **Load:** 10 calls × 5 min, < 1 ms overhead, < 1 % drop  
- **Audit:** 10 trace manual review → 0 PHI  

---

## 18. Risks & Rollback Plan

| Risk | Impact | Mitigation |
|-------|---------|------------|
| Telemetry adds latency | Medium | Async tasks < 1 ms; monitor |
| PHI leak | Critical | Inline redaction + audit |
| SDK error crashes agent | High | Try/except wrapping |
| Alert noise | Low | Start with 3 alerts, tune |
| Network issues misread | Medium | Include RTT/jitter/loss metrics |

**Rollback Trigger:**  
If **compliance audit fails** (any PHI leak) or **latency > 5 ms**, disable telemetry immediately and delay launch 2 weeks to fix + re-audit.

---

## 19. Post-MVP Considerations
- Add sampling > 100 calls/day  
- Automate data exports  
- Add compliance dashboard  
- Expand tool library  

---

## 20. Decision Log (Appendix)

| Decision | Reason |
|-----------|---------|
| **LangSmith chosen** | Native OpenAI support, easy setup |
| **No data warehouse** | Low volume; LangSmith 90 d enough |
| **Two envs (dev/prod)** | Simple, avoids staging overhead |
| **Full instrumentation (no sampling)** | < 10 calls/day; need complete data |
| **Azure OpenAI Realtime** | Low latency & per-turn token tracking |
| **Async telemetry pattern** | Non-blocking by design |
| **Slack alerts only** | Built-in LangSmith integration sufficient |

---

✅ **Document Status:** Final MVP PRD — approved for implementation.  
**Owner:** Frédéric Brunner  |  **Implementation:** Claude Code  |  **Sign-off:** Frédéric Brunner (Product & Compliance)
