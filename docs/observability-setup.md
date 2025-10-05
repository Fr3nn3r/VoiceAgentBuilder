# Observability Setup Guide

This guide explains how to set up enhanced observability for your LiveKit voice agent, including LangSmith integration and structured logging.

## Overview

The enhanced observability system provides:
- **LangSmith Integration**: Detailed tracing of LLM calls and interactions
- **Structured Logging**: JSON-formatted logs for better analysis
- **Session Metrics**: Comprehensive tracking of voice interactions
- **MCP Tracing**: Monitoring of MCP server interactions
- **Error Tracking**: Detailed error logging with context

## Setup Instructions

### 1. Environment Configuration

Add these environment variables to your `.env` file:

```bash
# LangSmith Configuration (Optional - for enhanced observability)
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=livekit-voice-agent
LANGCHAIN_TRACING_V2=true

# Logging Configuration
LOG_LEVEL=INFO
```

### 2. LangSmith Setup

1. **Create a LangSmith Account**: Sign up at [smith.langchain.com](https://smith.langchain.com)
2. **Get API Key**: Navigate to Settings > API Keys and create a new key
3. **Set Environment Variables**: Add your API key to the `.env` file
4. **Install Dependencies**: The system will automatically install `langsmith` when you run the agent

### 3. Running with Observability

The agent automatically detects LangSmith configuration and enables tracing when available:

```bash
# With LangSmith tracing (if environment variables are set)
python -m src.agent

# Without tracing (fallback to standard logging)
LANGCHAIN_TRACING_V2=false python -m src.agent
```

## Observability Features

### 1. LangSmith Tracing

When enabled, the system provides:
- **LLM Call Tracing**: Every OpenAI API call is traced with input/output
- **Function Call Tracking**: Tool/function usage is monitored
- **Performance Metrics**: Response times and token usage
- **Error Tracking**: Failed calls with error context

### 2. Structured Logging

All interactions are logged in JSON format:

```json
{
  "event_type": "user_input",
  "session_id": "session_123",
  "room_name": "room_456",
  "timestamp": "2024-01-15T10:30:00Z",
  "duration_ms": 1500,
  "user_input": "What's the weather like?",
  "metadata": {
    "interaction_number": 1,
    "stt_duration_ms": 1500
  }
}
```

### 3. Session Metrics

At the end of each session, you'll see:
- Total interactions
- Function call counts
- Error rates
- Session duration
- Token usage (STT, TTS, LLM)

### 4. MCP Server Monitoring

MCP server interactions are tracked:
- Request/response logging
- Performance metrics
- Error handling

## Monitoring and Analysis

### LangSmith Dashboard

1. **Access Dashboard**: Go to [smith.langchain.com](https://smith.langchain.com)
2. **View Traces**: Navigate to your project to see detailed traces
3. **Analyze Performance**: Use the built-in analytics tools
4. **Debug Issues**: Trace through individual conversations

### Log Analysis

Use structured logs for:
- **Real-time Monitoring**: Stream logs to monitoring tools
- **Error Analysis**: Search for error patterns
- **Performance Optimization**: Identify bottlenecks
- **Usage Analytics**: Understand user interaction patterns

## Alternative Observability Approaches

If you prefer not to use LangSmith, consider these alternatives:

### 1. Custom Logging with ELK Stack

```python
# Example: Send logs to Elasticsearch
import json
from elasticsearch import Elasticsearch

def log_to_elasticsearch(event_data):
    es = Elasticsearch(['localhost:9200'])
    es.index(index='voice-agent-logs', body=event_data)
```

### 2. Prometheus + Grafana

```python
# Example: Custom metrics
from prometheus_client import Counter, Histogram, start_http_server

llm_calls = Counter('llm_calls_total', 'Total LLM calls')
llm_duration = Histogram('llm_duration_seconds', 'LLM call duration')
```

### 3. Datadog Integration

```python
# Example: Datadog tracing
from ddtrace import patch_all
patch_all()

# Automatic tracing of OpenAI calls
```

## Troubleshooting

### Common Issues

1. **LangSmith Not Working**:
   - Check API key is correct
   - Verify environment variables are set
   - Check network connectivity

2. **High Log Volume**:
   - Adjust log levels in configuration
   - Use log filtering in your monitoring setup

3. **Performance Impact**:
   - LangSmith tracing has minimal overhead
   - Structured logging is optimized for performance

### Debug Mode

Enable debug logging for troubleshooting:

```bash
LOG_LEVEL=DEBUG python -m src.agent
```

## Best Practices

1. **Privacy**: Be mindful of logging sensitive user data
2. **Performance**: Monitor the impact of observability on latency
3. **Storage**: Plan for log storage and retention policies
4. **Alerting**: Set up alerts for error rates and performance issues
5. **Cost Management**: Monitor LangSmith usage and costs

## Example Output

With observability enabled, you'll see logs like:

```
2024-01-15 10:30:00 - voice_observability - INFO - User Input: {"event_type": "user_input", "session_id": "session_123", ...}
2024-01-15 10:30:02 - langsmith_llm - INFO - LLM Chat Input: messages=3, last_user='What's the weather like?'
2024-01-15 10:30:03 - langsmith_llm - INFO - LLM Chat completed successfully in 1.23s
2024-01-15 10:30:03 - voice_observability - INFO - Agent Response: {"event_type": "agent_response", ...}
```

This provides comprehensive visibility into your voice agent's behavior and performance.
