Core Design Concepts

Use a minimalist 2D design. Start with a flat SVG or React‑based owl made of a few named layers: body, head, eyes, beak, wings and perhaps a small “LED” on its chest. Fewer shapes means easier control and a smaller asset.

Animate according to state. Model the owl’s behavior around the agent’s lifecycle:

Idle/Listening: Eyes blink occasionally and the body does a gentle “breathing” scale animation.

Thinking: Eyes glance up, head tilts slightly, maybe a subtle chest pulse to show activity.

Speaking: Beak opens/closes based on volume or visemes, head bobs to the rhythm of speech, wings do tiny gestures at sentence boundaries.

Gesture cues: Trigger small motions (nods, shrugs, eye squints) for emotions or NLU intents such as affirmation, confusion, or apology.

Synchronisation sources:

Amplitude‑driven (quickest to implement): Use Web Audio’s AnalyserNode on the TTS audio track to get RMS/peak volume. Map that to beak openness, head bob amplitude and chest LED intensity. This works with any TTS engine (including OpenAI’s) and provides a decent lip‑flap illusion.

Viseme/phoneme‑driven (more accurate): Use a TTS engine that exposes timing data (Azure Cognitive TTS, ElevenLabs, Amazon Polly with speech marks). Each viseme ID maps to a mouth shape (closed, wide open, round, smile, neutral). Combine this with volume for head bob and chest pulse.

LiveKit integration:

Audio track: Your server will publish the TTS audio track to the room, just as it already does for the agent’s voice.

Data channel: Send a JSON payload on a LiveKit data track that includes the animation timeline—either viseme events with timestamps or simple “start speaking”/“stop speaking” markers for amplitude‑only mode. Include the exact epoch when the audio will start playing on the client, so the browser can schedule animations precisely.

Backend‑ vs client‑driven: In a multi‑viewer scenario or if you want total control, compute and send all animation events from your backend (alongside the audio). In a single‑viewer or quick prototype, you can let the client measure audio volume directly and animate locally.

Clock sync: To avoid drift, buffer a small pre‑roll (150–250 ms) between receiving the audio stream and playing it. Send your animation events relative to the known audio start time. A periodic “heartbeat” message every second can allow clients to correct minor timing drift.

Fallback strategy: If you can’t extract visemes, keep it simple: do a random blink every few seconds, map volume to beak opening and head movement, and occasionally trigger a wing “tick” on punctuation or when the agent finishes a sentence.

Implementation Steps for the MVP

Create the owl asset. Make a simple SVG with distinct id attributes for each moving part (eyes, beak, head, body, wings, chestLED). Export it once and reuse it.

Build an <OwlAvatar> component. In your front‑end (React/Next.js or plain HTML/JS):

Load the SVG and access the pieces via JavaScript.

Set up the animation loop: use requestAnimationFrame to update head tilt and chest scale based on current amplitude or scheduled events.

Schedule visemes: when you receive a viseme timeline, call setTimeout for each change. When using amplitude only, update beak shape based on a smoothed RMS value.

Blink: use a separate timer to randomly close and reopen the eyes.

Gesture hooks: expose a function (e.g. playGesture('nod')) so that your agent can send custom gestures when the conversation indicates emotion.

Handle audio & viseme events in Python. In your LiveKit agent:

Produce TTS audio via your chosen engine (Azure, ElevenLabs, etc.). If the engine supports visemes, extract a list of {t_ms, viseme_id}.

Publish the audio track.

Publish the viseme/gesture JSON with fields like audio_track_id, audio_start_epoch_ms, and the array of visemes. Use a reliable, ordered data channel.

When your agent finishes talking, send a “stop speaking” cue (so the owl returns to idle state).

Tie it together via LiveKit. Your Python code subscribes to user audio, generates a response with your LLM, then synthesizes speech, extracts animation events, and publishes both the audio and the animation payload before playback begins. Clients subscribe to both the audio and data channels and render accordingly.

Test with the provided demo. I supplied a minimal HTML file (owl_avatar_demo.html) that shows how to drive an owl SVG with amplitude and a mock viseme timeline. You can use this as a template for your React component or refine it further.

In Short

You’re building a real‑time puppet for your agent. The backend generates speech and (optionally) viseme data, publishes audio and animation cues via LiveKit; the frontend renders a cute owl and keeps it synced. Start with volume‑only animation for a quick win, and add viseme support when your TTS pipeline makes it available. Ask questions if this is not clear or if you're stuck.