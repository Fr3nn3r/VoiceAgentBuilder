# Owl Avatar for Voice Agent

A real-time animated owl avatar that visualizes your LiveKit voice agent's state using amplitude-based animation.

## Architecture

### Frontend (React + LiveKit Client)
- **Location**: `public/index.html` (single-file React app via CDN)
- **Features**:
  - Owl SVG with animated parts (head, beak, wings, eyes, chest LED)
  - Real-time audio amplitude analysis via Web Audio API
  - State-based animations (idle, listening, thinking, speaking)
  - LiveKit room connection with token authentication

### Backend (Python + LiveKit Agent)
- **Location**: `src/agent.py`
- **Features**:
  - Sends animation events via LiveKit data channel
  - Events: `thinking`, `speaking_start`, `speaking_stop`
  - Integrated with AgentSession event hooks

## Setup

### 1. Start the Voice Agent

```bash
python src/agent.py dev
```

This starts the LiveKit agent that will publish audio and animation events.

### 2. Serve the Frontend

In a separate terminal:

```bash
python serve_frontend.py
```

Open http://localhost:8080 in your browser.

### 3. Connect to LiveKit Room

You need:
- **Room URL**: Your LiveKit server WebSocket URL (e.g., `wss://your-server.livekit.cloud`)
- **Access Token**: Generate via LiveKit dashboard or API

Enter both in the frontend UI and click "Connect".

## How It Works

### Animation States

**Idle/Listening**
- Gentle breathing animation (body scale pulse)
- Random eye blinks every 2-5 seconds
- Wings and beak at rest

**Thinking**
- Head tilts side to side
- Chest LED pulses
- Eyes stay open

**Speaking**
- Beak opens/closes based on audio amplitude
- Head bobs to speech rhythm
- Wings move at high amplitude
- Chest LED brightens with volume

### Data Flow

```
Agent (Python)                Frontend (React)
     |                              |
     |-- Audio Track ------------->|-- Web Audio Analyser
     |                              |   (measures amplitude)
     |                              |
     |-- Data Channel ------------->|-- Animation Events
         (JSON events)                  (state changes)
```

### Events Sent by Backend

```json
{
  "type": "animation_event",
  "event": "thinking" | "speaking_start" | "speaking_stop"
}
```

### Amplitude Calculation

Frontend uses Web Audio API `AnalyserNode`:
- FFT size: 256
- Measures average frequency bin values (0-255 range)
- Normalizes to 0-1 for animation parameters
- Updates at ~60 FPS via `requestAnimationFrame`

## File Structure

```
voice-agent/
├── public/
│   ├── index.html          # React app (CDN-based)
│   └── owl.svg             # Owl avatar asset
├── src/
│   └── agent.py            # LiveKit agent with animation events
├── serve_frontend.py       # Simple HTTP server
└── OWL_AVATAR_README.md    # This file
```

## Customization

### Change Owl Appearance
Edit `public/owl.svg` - all parts have IDs for easy targeting:
- `#body`, `#head`, `#beak-top`, `#beak-bottom`
- `#left-eye`, `#right-eye`, `#left-wing`, `#right-wing`
- `#chest-led`

### Adjust Animation Parameters
In `public/index.html`, modify the `updateOwlAnimation()` function:
- Breathing speed: `Math.sin(time * 2)` - change multiplier
- Beak openness: `normalizedAmp * 10` - adjust sensitivity
- Head bob: `normalizedAmp * 3` - adjust movement range

### Add Gestures
In `src/agent.py`, send custom events:
```python
await send_animation_event("gesture_nod")
await send_animation_event("gesture_shrug")
```

Then handle in frontend's `handleDataReceived()`.

## Troubleshooting

**Owl doesn't animate during speech**
- Check browser console for audio track subscription
- Verify agent is publishing audio to the room
- Confirm amplitude monitoring is active (check state in UI)

**Animation events not received**
- Verify agent.py event hooks are firing (check logs)
- Ensure data channel is reliable (`reliable=True`)
- Check browser console for data parsing errors

**Blink timing feels off**
- Adjust random range in `startBlinkLoop()`: `2000 + Math.random() * 3000`

**SVG doesn't load**
- Ensure `serve_frontend.py` is running
- Check browser network tab for 404 on `/owl.svg`
- Verify file exists at `public/owl.svg`

## Future Enhancements

### Viseme Support
To add lip-sync accuracy:
1. Use TTS engine with viseme output (Azure, ElevenLabs, Polly)
2. Extract viseme timeline in `src/agent.py`
3. Send timeline via data channel with audio start timestamp
4. Schedule viseme changes in frontend using `setTimeout`

### Multi-viewer Sync
- Add audio playback timestamp to events
- Use server-side clock sync (heartbeat messages)
- Buffer pre-roll (150-250ms) before animation start

### Emotion Gestures
- Parse LLM response for sentiment
- Trigger custom gestures: nod (agreement), shrug (uncertainty), squint (confusion)
- Add wing "flap" on sentence boundaries

## Development Notes

- Uses React 18 via CDN (no build step)
- LiveKit client library v2.5.8
- Babel standalone for JSX transformation in browser
- Python 3.8+ required for backend
- No npm dependencies for frontend

## License

Same as parent project.
