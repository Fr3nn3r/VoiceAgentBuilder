# PROJECT_CONTEXT.md

## Project Overview

This is a **Voice Agent** project built with **LiveKit Agents for Python** - a complete starter project for building voice AI applications. The project provides a foundation for creating conversational AI agents that can handle real-time voice interactions.

## Core Technology Stack

- **Framework**: LiveKit Agents for Python
- **Language**: Python 3.9+
- **Package Manager**: UV (ultra-fast Python package manager)
- **AI Services**:
  - **LLM**: OpenAI (with support for other providers)
  - **STT**: Deepgram (Speech-to-Text)
  - **TTS**: Cartesia (Text-to-Speech)
  - **VAD**: Silero (Voice Activity Detection)
- **Additional Features**:
  - LiveKit Turn Detector for multilingual support
  - LiveKit Cloud enhanced noise cancellation
  - Integrated metrics and logging

## Project Structure

```
voice-agent/
├── src/                    # Main source code
│   ├── agent.py           # Primary voice agent implementation
│   ├── agent_mcp.py       # MCP (Model Context Protocol) integration
│   ├── hotel_agent.py     # Specialized hotel agent
│   └── n8n_agent.py       # N8N workflow integration agent
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── prompts/               # AI agent personality definitions
│   ├── n8n-agent.md       # N8N agent prompt
│   └── shushu.md          # Shushu personality (cynical owl character)
├── docs/                  # Documentation
│   ├── n8n-agent-setup.md # N8N setup guide
│   └── observability-setup.md # Monitoring setup
└── scripts/               # Utility scripts
```

## Key Features

### 1. Voice AI Pipeline
- **Real-time voice processing** with LiveKit
- **Multilingual support** (English, French, Italian, German)
- **Contextual speaker detection** with turn detection
- **Noise cancellation** for improved audio quality

### 2. Agent Personalities
- **Shushu**: A cynical, confident owl character created by Fred Brunner
  - Short, direct communication style
  - Sarcastic and humorous
  - Dreams of going to the moon
  - Multilingual (English/French/Italian/German)

### 3. Integration Capabilities
- **N8N Workflow Integration**: Send data to N8N webhooks for processing
- **MCP Support**: Model Context Protocol integration
- **Hotel Agent**: Specialized agent for hospitality use cases

### 4. Development & Testing
- **Comprehensive test suite** with pytest
- **Evaluation framework** for testing agent performance
- **Docker support** for containerized deployment
- **CI/CD ready** with GitHub Actions

## Development Environment

### Prerequisites
- Python 3.9+
- UV package manager
- LiveKit Cloud account or self-hosted LiveKit instance
- API keys for OpenAI, Deepgram, and Cartesia

### Environment Variables
```bash
LIVEKIT_URL=wss://your-livekit-url
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
CARTESIA_API_KEY=your-cartesia-key
```

## Usage Patterns

### 1. Console Mode
```bash
uv run python src/agent.py console
```
Direct terminal interaction with the voice agent.

### 2. Development Mode
```bash
uv run python src/agent.py dev
```
Run agent for frontend or telephony integration.

### 3. Production Mode
```bash
uv run python src/agent.py start
```
Production deployment with full features.

## Architecture Decisions

### 1. Plugin-Based Design
- Modular architecture with separate plugins for different services
- Easy to swap LLM, STT, and TTS providers
- Support for real-time models like OpenAI Realtime API

### 2. Multilingual Support
- Language detection from transcripts
- Dynamic TTS voice switching based on detected language
- Support for multiple languages with appropriate voice models

### 3. Testing Strategy
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Evaluation framework for agent performance testing

## Deployment Options

### 1. LiveKit Cloud
- Managed service with automatic scaling
- Built-in monitoring and metrics
- Easy integration with frontend applications

### 2. Self-Hosted
- Docker-based deployment
- Full control over infrastructure
- Custom configuration options

### 3. Frontend Integration
- React/Next.js web applications
- Native mobile apps (iOS, Android)
- Cross-platform Flutter applications
- Telephony integration for phone calls

## Current Development Status

- **Core Agent**: Fully functional with OpenAI, Deepgram, and Cartesia integration
- **N8N Integration**: In development for workflow automation
- **Hotel Agent**: Specialized implementation for hospitality use cases
- **Testing**: Comprehensive test suite with evaluation framework
- **Documentation**: Setup guides and observability documentation

## Future Roadmap

- Enhanced N8N workflow integration
- Additional agent personalities
- Extended multilingual support
- Advanced analytics and monitoring
- Custom frontend applications

## Contributing

This project follows SOLID principles and maintains high code quality standards:
- Single Responsibility Principle
- Open/Closed Principle
- Liskov Substitution Principle
- Interface Segregation Principle
- Dependency Inversion Principle

Code quality is maintained through:
- TypeScript for frontend components
- Comprehensive logging and error handling
- Security measures (CORS, rate limiting)
- Environment-based configuration
- Automated testing and CI/CD
