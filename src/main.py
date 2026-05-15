import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import ConfigManager
from router import route_message
from agents.weather_agent import WeatherAgent
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AgentManager:
    """
    Enterprise agent manager with proper initialization and lifecycle management

    Features:
    - Agent registration and instantiation
    - Health checks
    - Error handling
    - Configuration management
    """

    def __init__(self, config_path: str = None):
        """
        Initialize agent manager

        Args:
            config_path: Path to configuration file. If None, uses default path.
        """
        if config_path is None:
            # Default path from src/ directory
            config_path = str(Path(__file__).parent.parent / "configs" / "config.yaml")
        self.config_manager = ConfigManager(config_path)
        self.agents: Dict[str, Any] = {}
        self._initialized = False

        try:
            self._initialize_agents()
            if not self.agents:
                raise RuntimeError("No agents were successfully initialized")
            self._initialized = True
            logger.info("✅ AgentManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AgentManager: {e}")
            raise

    def _initialize_agents(self) -> None:
        """Initialize all available agents"""
        logger.info("Initializing agents...")

        # Weather Agent
        try:
            self.agents["weather"] = WeatherAgent()
            logger.info("WeatherAgent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WeatherAgent: {e}")
            # Continue without weather agent

        # Add more agents here as they become available
        # self.agents["science"] = ScienceAgent()
        # self.agents["piano"] = PianoAgent()

        if not self.agents:
            logger.warning("No agents were successfully initialized")

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """
        Get agent by name

        Args:
            agent_name: Name of the agent

        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(agent_name)

    def list_agents(self) -> list:
        """
        List all available agents

        Returns:
            list: Agent names
        """
        return list(self.agents.keys())

    def handle_message(self, message: str) -> str:
        """
        Handle user message by routing to appropriate agent

        Args:
            message: User input message

        Returns:
            str: Agent response
        """
        try:
            agent_name = route_message(message)
            agent = self.get_agent(agent_name)

            if agent:
                logger.info(f"Routing message to {agent_name} agent")
                response = agent.handle(message)
                return response
            else:
                logger.warning(f"No agent found for: {agent_name}")
                return "Sorry, I don't have an agent for that type of request yet."

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return f"Sorry, I encountered an error processing your request: {e}"

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all agents

        Returns:
            dict: Health status information
        """
        health = {
            "manager_initialized": self._initialized,
            "agents": {},
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }

        for name, agent in self.agents.items():
            try:
                if hasattr(agent, 'health_check'):
                    health["agents"][name] = agent.health_check()
                elif hasattr(agent, 'is_initialized'):
                    health["agents"][name] = {
                        "initialized": agent.is_initialized(),
                        "status": "healthy" if agent.is_initialized() else "unhealthy"
                    }
                else:
                    health["agents"][name] = {"status": "unknown"}
            except Exception as e:
                health["agents"][name] = {"status": "error", "error": str(e)}

        return health

    def is_initialized(self) -> bool:
        """Check if manager is properly initialized"""
        return self._initialized


def run_interactive_chat():
    """
    Run interactive chat loop
    """
    print("🤖 AI Lab Agent System")
    print("======================")
    print("Available agents: weather")
    print("Type 'exit' to quit, 'help' for commands\n")

    # Initialize agent manager
    try:
        manager = AgentManager()
    except Exception as e:
        print(f"❌ Failed to initialize agent system: {e}")
        return

    while True:
        try:
            msg = input("You: ").strip()

            if not msg:
                continue

            if msg.lower() in ["exit", "quit"]:
                print("Goodbye! 👋")
                break

            if msg.lower() == "help":
                print("\nCommands:")
                print("- exit/quit: Exit the chat")
                print("- agents: List available agents")
                print("- health: Show system health")
                print("- help: Show this help")
                print("\nOr just ask a question!\n")
                continue

            if msg.lower() == "agents":
                agents = manager.list_agents()
                print(f"Available agents: {', '.join(agents) if agents else 'None'}")
                continue

            if msg.lower() == "health":
                health = manager.health_check()
                print(f"System Health: {'✅ Healthy' if health['manager_initialized'] else '❌ Unhealthy'}")
                for name, status in health["agents"].items():
                    status_icon = "✅" if status.get("status") == "healthy" else "❌"
                    print(f"  {name}: {status_icon} {status.get('status', 'unknown')}")
                continue

            # Handle regular message
            response = manager.handle_message(msg)
            print(f"\n🤖 {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    run_interactive_chat()