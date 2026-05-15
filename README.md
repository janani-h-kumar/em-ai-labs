# AI Lab - Ollama Local LLM Client

Production-grade Python application for interacting with local Ollama models with configuration management, health checks, multi-turn conversation support, and extensible agent architecture.

## Features

- **ConfigManager**: YAML-based configuration with nested value access and validation
- **OllamaClient**: Model health checks via `/api/tags` endpoint with auto-model selection
- **WeatherAgent**: AI-powered weather summaries with custom prompts
- **Custom Exceptions**: Detailed error messages with specific exception hierarchy for better error handling
- **Multi-turn Support**: Maintains conversation history for contextual responses
- **Interactive Chat**: Terminal-based interactive chat interface with commands
- **Extensible Architecture**: Simple standards-based pattern for creating new agents
- **Isolated Environment**: All dependencies in local virtual environment
- **Comprehensive Logging**: Structured logging for debugging and monitoring

## Setup

### Migration note
Sensitive values have moved out of `config.yaml` and into `configs/.env`. Set `OLLAMA_HOST`, `OLLAMA_API_KEY`, and `WEATHER_API_KEY` in `configs/.env` and do not commit that file.

### Prerequisites
- Python 3.8+
- Ollama running locally (`http://localhost:11434`)
- A model pulled in Ollama (e.g., `ollama pull phi3`)

### Installation

1. **Clone or navigate to the repository**
   ```bash
   cd c:\Workspace\ai-lab
   ```

2. **Activate virtual environment**
   ```powershell
   .\venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Ollama connection** (Required)
   ```bash
   cd configs
   cp config.yaml.example config.yaml
   ```

   Create a `configs/.env` file with the required sensitive settings:
   ```bash
   cd configs
   copy NUL .env
   ```

   Add the following values to `configs/.env`:
   ```text
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_API_KEY=your_ollama_api_key
   WEATHER_API_KEY=your_openweathermap_api_key
   ```

   Edit `config.yaml` if your setup differs. `config.yaml` should not contain OLLAMA_HOST, OLLAMA_API_KEY, or WEATHER_API_KEY.

5. **Configure Weather API** (Optional - only needed for WeatherAgent)
   
   If you want to use the WeatherAgent, get a free API key from [OpenWeatherMap](https://openweathermap.org/api).
   The sensitive keys must be set in `configs/.env`:
   - `OLLAMA_API_KEY` for Ollama
   - `WEATHER_API_KEY` for OpenWeatherMap

## Usage

### Test App (Sample Demonstrations)
Runs sample prompts and multi-turn conversation examples:
```bash
cd Samples
python test_local_llm.py
```

Output shows:
- **EXAMPLE 1**: Simple string prompts (single-turn)
- **EXAMPLE 2**: Multi-turn conversation with system message and context

### Interactive Chat (MAIN APPLICATION)
Start an interactive chat session to converse with the model in real-time:
```bash
cd src
python main.py
```

#### Chat Commands
- **Type any text + Enter**: Send message to model and get response
- **exit, quit, close, bye**: Exit the application
- **clear**: Reset conversation history (start fresh)
- **help**: Show available commands
- **model**: Display current model name
- **history**: Show full conversation so far
- **save**: Export conversation to a timestamped text file

#### Example Interactive Chat
```
🤖 Interactive Ollama Chat
======================================================================

You: What is machine learning?
⏳ Thinking... ✅ Response received.
```

### Agents

Agents are specialized AI components that combine external data with LLM reasoning to provide intelligent responses. See [AGENTS.md](AGENTS.md) for full documentation.

#### Weather Agent
Get friendly weather summaries powered by AI:

```bash
cd src/agents
python weather_agent.py
```

Or use in your code:
```python
from src.agents.weather_agent import WeatherAgent

agent = WeatherAgent()
summary = agent.get_weather_summary("New York")
print(summary)
# Output: "🌡️ New York is currently 72°F with clear skies - perfect for outdoor activities!"

# Get detailed weather data
weather = agent.get_detailed_weather("London", temperature_units="metric")
```

#### Testing Agents
```bash
# Test weather agent
python tests/test_weather_agent.py

# Test weather tool
python tests/test_weather.py
```

## Architecture

### Project Structure

```
ai-lab/
├── src/
│   ├── main.py                    # Interactive chat application
│   ├── providers/
│   │   └── ollama_provider.py     # Ollama client & configuration
│   ├── tools/
│   │   └── weather_tool.py        # Weather API client
│   └── agents/
│       ├── weather_agent.py       # Weather summarization agent
│       ├── piano_agent.py         # (Future)
│       └── science_ama_agent.py   # (Future)
├── tests/
│   ├── test_weather.py            # Weather tool tests
│   └── test_weather_agent.py      # Weather agent tests
├── configs/
│   ├── config.yaml                # User configuration (excluded from git)
│   └── config.yaml.example        # Configuration template
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── AGENTS.md                      # Agent architecture documentation
├── PLAN.md                        # Project planning
└── venv/                          # Virtual environment (excluded from git)
```

### Core Components

#### ConfigManager
Loads and validates configuration from YAML file with dot-notation access.

```python
from src.providers.ollama_provider import ConfigManager

config_manager = ConfigManager("configs/config.yaml")
host = config_manager.get("ollama.host")
api_key = config_manager.get("env.weather_api_key")  # loaded from configs/.env via WEATHER_API_KEY
```

#### OllamaClient
Manages connection to Ollama server with validation and chat completions.

```python
from src.providers.ollama_provider import OllamaClient

ollama = OllamaClient(config_manager)

# Simple prompt
response = ollama.chat_completion("What is AI?")

# Multi-turn conversation
conversation = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is AI?"},
    {"role": "assistant", "content": "AI is..."},
    {"role": "user", "content": "Tell me more"}
]
response = ollama.chat_completion(conversation)
```

#### WeatherClient
Fetches weather data from OpenWeatherMap API with validation.

```python
from src.tools.weather_tool import WeatherClient, WeatherConfigManager

config = WeatherConfigManager("configs/config.yaml")
weather = WeatherClient(config)

# Get weather data
data = weather.get_temperature("New York", units="imperial")
# Returns: {city, temperature, condition, humidity, pressure, ...}
```

### Exception Hierarchy

**Ollama Provider**:
- `OllamaError` (base)
  - `ConfigError` - Configuration issues
  - `ModelNotFoundError` - Model not available
  - `OllamaConnectionError` - Server connection failed

**Weather Tool**:
- `WeatherError` (base)
  - `WeatherConfigError` - Configuration issues
  - `WeatherAPIError` - API request failed
  - `CityNotFoundError` - City not found

**Weather Agent**:
- `WeatherAgentError` (base)
  - `WeatherAgentInitError` - Initialization failed
  - `WeatherAgentExecutionError` - Execution failed

## Security

- `config.yaml` is excluded from git (see `.gitignore`)
- API keys should only be in local `config.yaml` files
- Never commit credentials to version control
- Use `config.yaml.example` as a template for your setup
- All credentials are loaded from configuration, not hardcoded

## Development Standards

All code follows these standards (see [AGENTS.md](AGENTS.md) for details):

- ✅ Proper logging with `logger.info()`, `logger.error()`, etc.
- ✅ Configuration management via `ConfigManager`
- ✅ Custom exception classes with specific types
- ✅ Type hints for all methods
- ✅ Comprehensive docstrings
- ✅ Input validation on all public methods
- ✅ Consistent error handling patterns
- ✅ Comprehensive test coverage

## Troubleshooting

### Error: "Cannot connect to Ollama server"
- Ensure Ollama is running: `ollama serve`
- Verify correct `base_url` in `config.yaml`
- Check that Ollama is accessible on the specified port

### Error: "Model not found locally"
- Pull the model: `ollama pull <model-name>`
- Verify model name in `config.yaml`
- Leave model field empty in config to auto-select running models

### Error: "Weather API failed"
- Verify weather API key in `config.yaml`
- Ensure you have internet connectivity
- Check city name spelling

### Error: "Config file not found"
- Ensure `config.yaml` exists in the `configs/` directory
- Copy from `config.yaml.example`: `cp configs/config.yaml.example configs/config.yaml`

### Error: "ModuleNotFoundError: No module named 'requests'"
- Reinstall dependencies: `pip install -r requirements.txt`

## Development

### Running Tests
```bash
python test_local_llm.py
```

### Project Structure
```
ai-lab/
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                 # Git exclusions
├── venv/                      # Virtual environment (excluded from git)
├── configs/                   # Configuration files
│   ├── config.yaml            # Configuration (excluded from git)
│   └── config.yaml.example    # Configuration template
├── src/                       # Source code
│   ├── main.py                # Interactive chat application
│   └── providers/             # Provider modules
│       └── ollama_client.py   # Core Ollama client module
└── tests/                     # Test files
```

## License

MIT