"""
Web search tool using DuckDuckGo API (free, no API key required).

This module provides a simple web search client for general queries,
complementing the weather tool for comprehensive information retrieval.
"""

import logging
import requests
from typing import List, Dict
from dataclasses import dataclass
from src.middleware.retry import retry_with_backoff
from pydantic import BaseModel, Field
from src.tools.base_tool import BaseTool
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)

# --- 1. Schema Input Definition ---
class WebSearchInput(BaseModel):
    query: str = Field(
        description="The web search query string, e.g., 'latest space exploration news'"
    )

# Custom Exceptions
class WebSearchError(Exception):
    """Base exception for web search errors."""
    pass


class WebSearchExecutionError(WebSearchError):
    """Runtime execution error during web search."""
    pass


@dataclass
class SearchResult:
    """Single search result from web search."""
    title: str
    url: str
    snippet: str


# --- 2. The Core API Client (Pure Data Fetcher) ---
class WebSearchClient:
    """
    Web search client using DuckDuckGo (free, no API key required).
    
    DuckDuckGo provides free web search via their unofficial API.
    Note: May have rate limits; for production, consider paid alternatives.
    """
    
    def __init__(self):
        """Initialize web search client."""
        self.base_url = "https://api.duckduckgo.com"
        self.timeout = 10
        logger.info("WebSearchClient initialized (DuckDuckGo)")
    
    @retry_with_backoff(max_retries=3, base_delay=1)
    def search(
        self,
        query: str,
        num_results: int = 5
    ) -> List[SearchResult]:
        if not query or not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        
        # Clamp num_results to valid range
        num_results = min(max(num_results, 1), 10)
        
        try:
            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "t": "em-ai-labs"  # User agent
            }
            
            logger.debug(f"Searching: {query}")
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("Results", [])[:num_results]:
                result = SearchResult(
                    title=item.get("Title", ""),
                    url=item.get("FirstURL", ""),
                    snippet=item.get("Text", "")
                )
                if result.title and result.url:
                    results.append(result)
            
            logger.info(f"Search found {len(results)} results for: {query}")
            return results
        
        except requests.RequestException as e:
            error_msg = f"Web search API request failed: {e}"
            logger.error(error_msg)
            raise WebSearchExecutionError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during web search: {e}"
            logger.error(error_msg)
            raise WebSearchExecutionError(error_msg)
    
    def search_as_dict(
        self,
        query: str,
        num_results: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        results = self.search(query, num_results)
        return {
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet
                }
                for r in results
            ]
        }


# --- 3. The LangChain Framework Agent Tool Wrapper ---
class WebSearchTool(BaseTool):
    """LangChain integration interface for the Web Search Client."""
    name = "web_search"
    description = "Search the web. Input: query string. Output: titles, URLs, snippets."
    args_schema = WebSearchInput

    def __init__(self, config_manager: ConfigManager):
        # Pass configuration upward to satisfy abstract BaseTool contract
        super().__init__(config_manager)
        # Instantiate the localized network data client once during setup
        self.client = WebSearchClient()

    def _run(self, *args, **kwargs) -> str:
        # Pull parameter safely from framework arguments
        query = kwargs.get("query") or (args[0] if args else None)
        if not query:
            raise ValueError("Query parameter is required.")
            
        # Execute search and turn structural results into a string format for LLM context
        return str(self.client.search_as_dict(query=query, num_results=3))