"""
Web search tool using DuckDuckGo API (free, no API key required).

This module provides a simple web search client for general queries,
complementing the weather tool for comprehensive information retrieval.
"""

import logging
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.middleware.retry import retry_with_backoff

logger = logging.getLogger(__name__)


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


class WebSearchClient:
    """
    Web search client using DuckDuckGo (free, no API key required).
    
    DuckDuckGo provides free web search via their unofficial API.
    Note: May have rate limits; for production, consider paid alternatives:
    - SerpAPI (reliable, supports 100+ search engines)
    - Bing Search API (reliable, Microsoft backed)
    - Google Custom Search (reliable, Google backed)
    
    Example:
        client = WebSearchClient()
        results = client.search("Python best practices", num_results=3)
        for result in results:
            print(f"{result.title}: {result.snippet}")
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
        """
        Execute web search query.
        
        Args:
            query: Search query string (non-empty)
            num_results: Number of results to return (1-10, default 5)
        
        Returns:
            List of SearchResult objects containing title, url, snippet
        
        Raises:
            ValueError: If query is invalid
            WebSearchExecutionError: If search fails
        
        Example:
            results = client.search("Python async programming", num_results=3)
            # Returns: [SearchResult(title="...", url="...", snippet="..."), ...]
        """
        if not query or not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        
        # Clamp num_results to valid range
        num_results = min(max(num_results, 1), 10)
        
        try:
            # DuckDuckGo API parameters
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
            
            # Extract results from DuckDuckGo response
            for item in data.get("Results", [])[:num_results]:
                result = SearchResult(
                    title=item.get("Title", ""),
                    url=item.get("FirstURL", ""),
                    snippet=item.get("Text", "")
                )
                # Only include results with both title and URL
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
        """
        Execute web search and return results as dictionaries.
        
        Useful for JSON serialization or tool integration.
        
        Returns:
            Dict with "results" key containing list of result dicts
        """
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
