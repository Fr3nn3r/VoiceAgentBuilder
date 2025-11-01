# Console Mode Guide - Medical Agent

## What is Console Mode?

Console mode allows you to test the medical agent **with voice input/output** directly in your terminal, without needing to set up a LiveKit room or web interface.

**You speak to the agent through your microphone, and it speaks back through your speakers.**

---

## How to Run Console Mode

```bash
uv run python .\src\medical_agent.py console
```

---

## What Happens

1. **Agent starts up** and connects your microphone/speakers
2. **Camille greets you automatically** with:
   - "Bonjour, cabinet du docteur Fillion, Camille à l'appareil."
   - Then asks: "En quoi puis-je vous aider ?" (or similar)
3. **You can speak** naturally into your microphone
4. **Camille responds** with voice through your speakers
5. **Tools are called** when needed (check_availability, book_appointment, etc.)

---

## Features Available

✅ **Voice Input** - Speak naturally in French
✅ **Voice Output** - Hear Camille's responses (OpenAI Realtime voice)
✅ **Automatic Greeting** - Camille speaks first (Option B1)
✅ **All 3 Tools** - Webhooks work in console mode
✅ **Emergency Detection** - Say "urgence" to trigger redirect
✅ **Interruptions** - You can interrupt Camille while speaking

---

## Requirements

Make sure your `.env` file has:

```bash
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPENAI_API_KEY=...
N8N_WEBHOOK_URL=https://n8n-render-deploy-uycj.onrender.com/webhook
```

---

## Comparison: Console Mode vs Room Mode

| Feature | Console Mode | Room Mode |
|---------|-------------|-----------|
| **Command** | `python medical_agent.py console` | `python medical_agent.py` |
| **Voice I/O** | Your mic/speakers | LiveKit room audio |
| **Use Case** | Quick testing locally | Production/Demo |
| **Setup** | None (just run) | Need LiveKit room + client |
| **Speed** | Instant start | Requires room connection |
| **Best For** | Development/Testing | Production deployment |

---

## Testing Workflow

### 1. Test Basic Conversation
```bash
uv run python .\src\medical_agent.py console
```
- Wait for greeting
- Say: "Je voudrais un rendez-vous"
- Follow the conversation

### 2. Test Tool Calls
- Say a date/time: "Mardi à 10h"
- Camille should call `check_availability` webhook
- Verify in terminal logs: `[Tool Call: check_availability_true_false]`

### 3. Test Emergency
- Say: "J'ai une urgence"
- Should hear: "Je ne peux pas gérer les urgences. Composez le 15."

### 4. Test Interruption
- While Camille is speaking, start talking
- She should stop and listen to you

---

## Troubleshooting

### No Audio Input
- Check microphone permissions
- Verify mic is not muted
- Try different mic in system settings

### No Audio Output
- Check speaker/headphone connection
- Verify volume is up
- Check audio device in system settings

### Greeting Not Playing
- Check logs for `[Greeting] User joined`
- Verify OpenAI Realtime API is working
- Check `OPENAI_API_KEY` is valid

### Tools Not Working
- Check `N8N_WEBHOOK_URL` in `.env`
- Test webhooks manually (see `scripts/test_all_webhooks.py`)
- Check n8n logs

---

## Stopping Console Mode

Press `Ctrl+C` to exit

---

## Logs

Watch the terminal for:
- `[Greeting] Intro delivered via session.say()` - Part 1 of greeting
- `[Greeting] LLM follow-up initiated` - Part 2 of greeting
- `[Tool Call] check_availability called` - When tools are invoked
- `[Webhook] Calling ...` - When webhooks are hit

---

## Next Steps After Testing

Once console mode works well:

1. **Deploy to Production** - Run without `console` argument
2. **Connect Web Client** - Use LiveKit room mode
3. **Add Telephony** - Connect SIP/PSTN for phone calls
4. **Monitor Metrics** - Check LiveKit dashboard for usage

---

## Tips

- **Speak clearly** - OpenAI Realtime works best with clear audio
- **Natural language** - Don't script your words, speak naturally
- **Be patient** - Wait for Camille to finish before interrupting
- **Test edge cases** - Try missing info, wrong dates, etc.
- **Check webhooks** - Make sure n8n workflows are activated

---

Enjoy testing Camille! 🎙️
