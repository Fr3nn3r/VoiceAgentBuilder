Here’s a detailed instruction set you can hand off to your devs for building the voice agent using LiveKit Agents + OpenAI Realtime API (WebRTC) with webhook-based tools. Feel free to distribute this or turn into a technical PRD.

---

## 🎯 Objective

Build a voice agent (“Camille”) that:

* Joins a LiveKit room as a participant
* Uses OpenAI Realtime (speech-in / speech-out) to converse with a French-speaking user
* Invokes webhooks for scheduling tools (check_availability, book_appointment, send_sms)
* Maintains low latency and clean conversational behaviour

---

## ✅ High-level Architecture

1. **LiveKit Room**: front-end client (web, mobile or telephony) connects to a LiveKit room.
2. **Agent Worker / Backend**: a server process that acts as a LiveKit “AgentSession” (via LiveKit Agents SDK) that listens for audio, passes it to OpenAI Realtime model, and streams back audio.
3. **Webhook Layer**: When the model triggers tool calls (e.g., `book_appointment`), the agent worker calls your HTTP endpoints (Supabase RPCs or n8n workflows) and feeds results back to the session.
4. **Prompt & Tooling**: System prompt (you’ve already prepared) + tools definitions + fallback/guardrail logic (emergency redirection, no medical advice, etc.).
5. **Deployment**: The worker runs in your cloud infra, ideally near your user region (Zurich/EU) for latency.

---

## 🛠️ Detailed Developer Instructions

### A. Setup

* Install the LiveKit Agents SDK with OpenAI plugin:

  ```bash
  # Python example
  pip install livekit-agents[openai]~=1.x
  ```

  ([LiveKit docs][1])
* Ensure environment variables: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENAI_API_KEY` (and any Azure variant if used)
* In your LiveKit dashboard: create room rules if needed, enable SIP/telephony if you’ll use PSTN dialing.

### B. AgentSession Configuration

In your worker code (Python or Node.js):

* Create an `AgentSession` (or equivalent) with plugin configuration for OpenAI Realtime. For example:

  ```python
  from livekit.agents import AgentSession
  from livekit.plugins import openai

  session = AgentSession(
    llm = openai.realtime.RealtimeModel(
      model="gpt-realtime",          # or whichever supported low-latency model
      voice="your_french_voice_id",  # specify voice if supported
      turn_detection = { … },        # configure barge-in / VAD
      modalities=["audio"]
    ),
    # optionally specify stt/tts separately if needed
  )
  ```

  ([LiveKit docs][2])
* Ensure `turn_detection`, `voice`, `model`, `modalities` parameters are set appropriately. ([LiveKit docs][3])
* Pass your system prompt (Camille’s identity, language rules) at session start.

### C. Tool Invocation (Webhooks)

* Define tool metadata in your prompt or in code: e.g. `check_availability(date, time, location?)`, `book_appointment(date, time, patient_name, phone, reason)`, `send_sms(to, text)`.
* In the session logic, capture when the model emits a tool call (openAI function call style or via structured message).
* Map that to an HTTP request to your backend:

  * Validate incoming parameters
  * Call your Supabase RPC or n8n webhook
  * Capture result (success/fail plus payload)
  * Return structured result back into the session so the agent can speak natural responses.

### D. Audio Flow & Latency Optimisation

* Use WebRTC transport (preferred) for audio with the Realtime API to minimise latency. ([Microsoft Learn][4])
* Chunk audio on the client side: send small utterances, avoid long pauses.
* On the agent side: respond in short sentences, avoid long monologues, allow for barge-in.
* Pre-buffer common phrases (greeting, emergency redirect) if possible.
* Monitor round-trip latency and use regional endpoint nearest to Europe/Zurich.

### E. Emergency & Guardrails Logic

* If the caller mentions emergency symptoms (you must define a list), the agent should **immediately**:

  * Speak: “Je ne peux pas gérer les urgences. En cas d’urgence médicale, composez le 15.”
  * End the call or transfer to human.
* The system prompt must forbid giving medical advice.
* Log all sessions (transcript + tool calls) for audit; ensure PHI handling and data storage are in compliance.

### F. Deployment & Monitoring

* Deploy the worker as a service (AWS/EU-region/GCP) with autoscale if needed.
* Use logs/traces for: session start/end, tool calls, model response latency, TTFB.
* Set alert on latency > 2s, or error rate > x%.
* Perform load testing (simulate 10–50 concurrent calls) to validate performance.

### G. Edge cases & Failures

* If schedule lookup fails: agent must say: “Je suis désolée, il semble qu’aucune disponibilité ne convient. Souhaitez-vous que je vérifie une autre journée ?”
* If tool call fails: “Je suis désolée, une erreur est survenue dans la réservation. Puis-je recommencer ?”
* If user goes off script: agent politely redirects: “Désolée, je ne peux gérer que la prise ou annulation de rendez-vous. Souhaitez-vous fixer un rendez-vous ?”

---

## 📋 Deliverables for Developers

* Worker code repo (Python or Node) implementing `AgentSession` + OpenAI Realtime config + webhook calls
* API endpoints spec for your scheduling tools (request/response JSON schema)
* Client sample (web or mobile) connecting to LiveKit room, publishing mic audio, subscribing to agent audio
* Load test plan (simulate N users, measure latency)
* Audit & logging plan (transcript storage, PHI encryption, tool call logs)
* Deployment instructions (region, environment vars, scaling)

---

## 🧪 Next Steps

1. Set up a Proof-of-Concept with 1 room, 1 agent, minimal tools (just `check_availability`) and French greeting.
2. Measure latency, tweak voice/turn detection, adjust chunk size.
3. Expand to full tool set, add `book_appointment`, `send_sms`.
4. Add monitoring, logging, fallback logic.
5. Fly the demo to stakeholders; refine prompt/voice.

---

If you like, I can compile a **developer-ready checklist** (Markdown) you can paste into your internal board (Jira/Asana) with each of these items as tasks.

[1]: https://docs.livekit.io/agents/integrations/?utm_source=chatgpt.com "LiveKit Agents integrations"
[2]: https://docs.livekit.io/agents/integrations/openai/customize/parameters/?utm_source=chatgpt.com "OpenAI Realtime API integration guide - LiveKit Docs"
[3]: https://docs.livekit.io/reference/agents-js/modules/plugins_agents_plugin_openai.realtime.html?utm_source=chatgpt.com "realtime | LiveKit Agents"
[4]: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/realtime-audio-webrtc?utm_source=chatgpt.com "How to use the GPT-4o Realtime API via WebRTC (Preview) - Azure ..."


Great — here’s exactly what you should instruct your development team so that LiveKit Agents has **Camille** speak first immediately when someone else joins the room. These are specification instructions (no code) that you can hand off to the devs.

---

## 🎯 Feature Requirement

When a **user participant** joins the LiveKit room, the voice-agent **Camille** must immediately greet them (in French) *before* expecting any input from the user. This greeting should trigger once upon user join.

---

## 🧩 Developer Instructions

### 1. Identify participant join event

* Use the LiveKit Agents framework (Python/Node) `JobContext`/`AgentSession`.
* Attach an entry point for participant join via `session.add_participant_entrypoint(...)`. The docs show you can run a callback when a participant joins. ([LiveKit docs][1])
* In the callback, detect when the identity is a **user** (not the agent itself) and the participant state becomes `JOINED`.

### 2. Agent greeting logic

* Once the user joins and is active (audio track available or just joined), have Camille speak: e.g., “Bonjour, cabinet du docteur Fillion, Camille à l’appareil. En quoi puis-je vous aider ?”
* Use `session.say(...)` or `session.generate_reply(instructions=…)` depending on your architecture.

  * The docs note `session.say()` lets you play a predefined message. ([LiveKit docs][2])
* Ensure that the greeting runs *only once* per session (per user joining).

### 3. Timing and conditions

* Wait for the agent to connect and subscribe to tracks, then detect the remote user join event.
* You might add a short delay (e.g., 300–500 ms) after join to ensure user track streams are ready before speaking.
* If multiple participants join (e.g., a group call or agent+user+helper), ensure Camille targets the **first user** and doesn’t repeat for every join.

### 4. Distinguish agent vs. user

* The agent identity is known (e.g., “Camille-agent”).
* When participant join event triggers, check `participant.kind` or `participant.identity !== agent_identity`.
* Only trigger greeting when participant is a user and not the agent.

### 5. Maintain session context

* After greeting, transition into regular conversation flow (collect intent, etc.).
* Ensure greeting doesn’t interfere with turn detection or prompt logic.
* If you use `preemptive_generation`, ensure greeting doesn’t get cancelled inadvertently. ([LiveKit docs][2])

### 6. Logging & metric

* Log an event: “Greeting triggered” with timestamp and user identity.
* Monitor TTFB (time from join → first audio from agent) to keep latency low.

---

## ✅ Acceptance Criteria

* When user joins room, Camille speaks first in French within ~1 second.
* The greeting uses the specified wording and tone.
* User can interrupt Camille speaking. (allow_interruption = true)
* The greeting is not repeated if additional participants join later.
* After the greeting, agent waits for user input and proceeds with scheduling flow.

---

Feel free to copy these instructions into your dev-ticket system (Jira/Asana) and assign tasks: *“Implement participant join greeting callback”*, *“Agent greeting voice message”*, *“Latency measurement for greeting”*, etc.

If you like, I can also draft a **small code snippet template** (for Python or Node) that shows *where* in the job entrypoint this greeting should hook in — you can hand that to the developers as a reference.

[1]: https://docs.livekit.io/reference/python/livekit/agents/index.html?utm_source=chatgpt.com "livekit.agents API documentation"
[2]: https://docs.livekit.io/agents/build/audio/?utm_source=chatgpt.com "Agent speech and audio - LiveKit Docs"

