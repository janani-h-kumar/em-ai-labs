# Agents Architecture

This document describes the extensible agent architecture for the AI Lab project.

## Overview

Agents are specialized AI components that combine:
- **Data Retrieval**: Fetch information from external APIs or services
- **LLM Integration**: Process data through a local LLM (Ollama) for intelligent responses
- **Configuration Management**: Use centralized YAML configuration for consistency
- **Error Handling**: Robust exception handling with custom exception classes
- **Logging**: Comprehensive logging for debugging and monitoring

## Standard Agent Design Pattern

All agents follow this architecture pattern:

```python
# 1. Imports & Logging
import logging
from providers.ollama_provider import OllamaClient, ConfigManager
from tools.some_tool import SomeClient, SomeConfigManager

logger = logging.getLogger(__name__)

# 2. Custom Exceptions
class AgentError(Exception):
    """Base exception"""
    pass

class AgentInitError(AgentError):
    """Initialization error"""
    pass

# 3. Agent Class
class SomeAgent:
    def __init__(self, config_path: str = "../configs/config.yaml"):
        """Initialize with configuration"""
        self.config_manager = ConfigManager(config_path)
        self.ollama_client = OllamaClient(self.config_manager)
        self.some_client = SomeClient(config_path)
    
    def execute(self, input_data):
        """Main execution method"""
        # 1. Get data from tool/API
        data = self.some_client.get_data(input_data)
        # 2. Format for LLM
        prompt = self._format_for_llm(data)
        # 3. Get LLM response
        response = self.ollama_client.chat_completion(prompt)
        return response
```

## Current Agents

### WeatherAgent

**Purpose**: Provides friendly weather summaries using LLM analysis

**Location**: `src/agents/weather_agent.py`

**Features**:
- Fetches weather data from OpenWeatherMap API
- Generates friendly, AI-powered weather summaries
- Supports multiple temperature units (metric, imperial)
- Customizable system prompts
- Comprehensive error handling

**Configuration**:
```yaml
# config.yaml
# Sensitive values are stored in configs/.env only.
weather:
  base_url: "https://api.openweathermap.org/data/2.5"

ollama:
  # ollama.api_key is loaded from configs/.env via OLLAMA_API_KEY
```

**Usage**:

```python
from src.agents.weather_agent import WeatherAgent

# Initialize agent
agent = WeatherAgent()

# Get weather summary
summary = agent.get_weather_summary("New York")
# Output: "🌡️ New York is currently 72°F with clear skies - perfect for outdoor activities!"

# Get detailed weather
detailed = agent.get_detailed_weather("London", temperature_units="metric")
# Returns: {city, country, temperature, humidity, pressure, condition, ...}

# Use custom system prompt
agent = WeatherAgent(
    system_prompt="You are a meteorologist. Provide a scientific weather analysis in one sentence."
)
summary = agent.get_weather_summary("Paris")
```

**Exception Hierarchy**:
- `WeatherAgentError` (base)
  - `WeatherAgentInitError` - Initialization failures
  - `WeatherAgentExecutionError` - Runtime errors (city not found, API issues)

**Testing**:
```bash
cd src/agents
python weather_agent.py  # Run demo

# Or run full test suite
cd tests
python test_weather_agent.py
```

## Standards Applied

All agents follow these standards:

### 1. **Configuration Management**
- Use `ConfigManager` from `providers/ollama_provider.py`
- Store all credentials and settings in `config.yaml`
- Never hardcode API keys or sensitive data
- Support nested configuration with dot notation

### 2. **Error Handling**
- Define custom exception hierarchy for each component
- Use specific exceptions (e.g., `CityNotFoundError` vs generic `Exception`)
- Include helpful error messages with context
- Log errors at appropriate levels

### 3. **Logging**
```python
import logging
logger = logging.getLogger(__name__)

# Log initialization
logger.info("Initializing agent...")

# Log steps
logger.debug("Fetching data...")

# Log errors
logger.error("Failed to fetch: ") from e
```

### 4. **Type Hints & Docstrings**
```python
def get_weather_summary(
    self,
    city: str,
    temperature_units: str = "imperial"
) -> str:
    """
    Get a friendly weather summary for a city
    
    Args:
        city: Name of the city
        temperature_units: 'metric' or 'imperial'
        
    Returns:
        str: Weather summary
        
    Raises:
        WeatherAgentExecutionError: If operation fails
    """
```

### 5. **Input Validation**
```python
if not city or not isinstance(city, str) or not city.strip():
    raise ValueError("City name must be a non-empty string")
```

### 6. **Separation of Concerns**
- **Tools**: Data retrieval and formatting (`src/tools/`)
- **Providers**: LLM and config management (`src/providers/`)
- **Agents**: Orchestration and LLM integration (`src/agents/`)
- **Tests**: Comprehensive test coverage (`tests/`)

## Creating a New Agent

Follow this checklist:

1. **Create Agent File**: `src/agents/your_agent.py`

2. **Define Exceptions**:
   ```python
   class YourAgentError(Exception):
       pass
   
   class YourAgentInitError(YourAgentError):
       pass
   ```

3. **Implement Agent Class**:
   ```python
   class YourAgent:
       def __init__(self, config_path: str = "../configs/config.yaml"):
           self.config_manager = ConfigManager(config_path)
           self.ollama_client = OllamaClient(self.config_manager)
           # Initialize your tool/client
   
       def main_method(self, inputs) -> str:
           # Get data
           # Format for LLM
           # Get response
           return response
   ```

4. **Add Configuration**:
   ```yaml
   # Add to config.yaml under appropriate section
   your_agent:
     api_key: "YOUR_KEY"
     base_url: "https://your-api.com"
   ```

5. **Create Tests**: `tests/test_your_agent.py`

6. **Update Documentation**: This file

## File Organization

```
src/
├── providers/
│   └── ollama_provider.py         # Ollama LLM client
├── tools/
│   └── weather_tool.py            # Weather API client
├── agents/
│   ├── weather_agent.py           # Weather agent
│   ├── piano_agent.py             # (Future)
│   └── science_ama_agent.py       # (Future)
└── main.py                        # Interactive chat entry point

tests/
├── test_weather.py                # Weather tool tests
├── test_weather_agent.py          # Weather agent tests
└── (other test files)

configs/
├── config.yaml                    # User configuration
└── config.yaml.example            # Configuration template
```

## Best Practices

### Do's ✅
- ✅ Use `ConfigManager` for all configuration
- ✅ Define custom exceptions for different error cases
- ✅ Log initialization, steps, and errors
- ✅ Add type hints to all methods
- ✅ Write comprehensive docstrings
- ✅ Validate all inputs
- ✅ Use consistent naming conventions
- ✅ Create integration tests
- ✅ Store credentials in config files
- ✅ Use dot notation for nested config access

### Don'ts ❌
- ❌ Hardcode API keys or credentials
- ❌ Use generic `Exception` classes
- ❌ Skip error handling
- ❌ Omit type hints and docstrings
- ❌ Create globals for config/clients
- ❌ Mix business logic with UI
- ❌ Skip input validation
- ❌ Use bare `except:` clauses

## Example: Weather Agent Code Structure

```python
# 1. Imports (organized by type)
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 2. Local imports
from providers.ollama_provider import (
    ConfigManager,
    OllamaClient,
    OllamaError,
)
from tools.weather_tool import (
    WeatherClient,
    WeatherConfigManager,
    WeatherAPIError,
)

# 4. Logging setup
logger = logging.getLogger(__name__)

# 5. Custom exceptions
class WeatherAgentError(Exception):
    pass

# 6. Main agent class
class WeatherAgent:
    def __init__(self, config_path: str = "../configs/config.yaml"):
        """Initialize with error handling"""
        try:
            self.config_manager = ConfigManager(config_path)
            self.ollama_client = OllamaClient(self.config_manager)
            self.weather_client = WeatherClient(
                WeatherConfigManager(config_path)
            )
            logger.info("Agent initialized")
        except Exception as e:
            logger.error("Init failed: ", e)
            raise WeatherAgentInitError("Failed to initialize: {e}") from e

    def get_weather_summary(self, city: str) -> str:
        """Get summary with full error handling"""
        try:
            # Step 1: Get data
            weather_data = self.weather_client.get_temperature(city)
            
            # Step 2: Format for LLM
            prompt = self._format_weather(weather_data)
            
            # Step 3: Get LLM response
            response = self.ollama_client.chat_completion(prompt)
            
            logger.info(f"Generated summary for {city}")
            return response
            
        except Exception as e:
            logger.error(f"Failed: {e}")
            raise WeatherAgentExecutionError(f"Failed: {e}")

    def _format_weather(self, data: Dict) -> str:
        """Helper method"""
        return f"Weather: {data}"
```

## Testing Guidelines

Each agent should have comprehensive tests covering:

1. **Initialization Tests**
   - Successful initialization
   - Configuration errors
   - Connection failures

2. **Functionality Tests**
   - Normal operation
   - Multiple inputs
   - Different configurations

3. **Error Handling Tests**
   - Invalid inputs
   - API failures
   - Missing data

4. **Integration Tests**
   - Full workflow
   - Custom configurations
   - Multiple agents

Example test structure:
```python
def test_agent_initialization():
    agent = WeatherAgent()
    assert agent.ollama_client is not None

def test_weather_summary():
    agent = WeatherAgent()
    summary = agent.get_weather_summary("New York")
    assert isinstance(summary, str)
    assert len(summary) > 0

def test_error_handling():
    agent = WeatherAgent()
    with pytest.raises(WeatherAgentExecutionError):
        agent.get_weather_summary("InvalidCity123")
```

## Future Agents

Planned agents following the same standards:

- **PianoAgent**: Music information and recommendations
- **ScienceAMAAgent**: Science questions and explanations
- (More to come...)

Each will follow the same pattern and standards documented here.
