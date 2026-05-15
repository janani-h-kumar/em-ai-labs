import logging
from src.providers.ollama_provider import (
    ConfigManager,
    OllamaClient,
    ConfigError,
    ModelNotFoundError,
    OllamaConnectionError,
    OllamaError,
)

# Configure logging to see debug info
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main function demonstrating production-grade Ollama client usage"""
    
    try:
        # Load configuration from config.yaml
        config_manager = ConfigManager("../configs/config.yaml")
        
        # Initialize Ollama client (validates connection and model availability)
        ollama = OllamaClient(config_manager)
        
        # === EXAMPLE 1: Simple string prompts ===
        print("\n" + "="*60)
        print("EXAMPLE 1: Simple Prompts")
        print("="*60)
        simple_prompts = [
            "Explain AI agents simply",
            "What is machine learning?",
        ]
        
        for prompt in simple_prompts:
            print(f"\n--- User ---\n{prompt}")
            response = ollama.chat_completion(prompt)
            print(f"\n--- Assistant ---\n{response}")
            print("-" * 60)
        
        # === EXAMPLE 2: Multi-turn conversation (full context at once) ===
        print("\n" + "="*60)
        print("EXAMPLE 2: Multi-turn Conversation")
        print("="*60)
        
        # This is how to do multi-turn: send the entire conversation history at once
        conversation = [
            {"role": "system", "content": "You are an engineering manager's chief of staff."},
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI stands for Artificial Intelligence. It refers to the simulation of human intelligence in machines that are programmed to think and learn like humans."},
            {"role": "user", "content": "Can you give me an example of AI in everyday life?"},
        ]
        
        print(f"\n--- Conversation History ---")
        for msg in conversation:
            print(f"[{msg['role'].upper()}]: {msg['content'][:80]}...")
        
        print(f"\n--- Getting Response ---")
        response = ollama.chat_completion(conversation)
        print(f"\n--- Assistant ---\n{response}")
        print("-" * 60)
            
    except ConfigError as e:
        logger.error(f"Configuration Error: {e}")
        return 1
    except ModelNotFoundError as e:
        logger.error(f"Model Error: {e}")
        return 1
    except OllamaConnectionError as e:
        logger.error(f"Connection Error: {e}")
        return 1
    except OllamaError as e:
        logger.error(f"Ollama Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())