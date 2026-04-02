from tavily import TavilyClient
from config import TAVILY_API_KEY


def search_targets(brief: str, n: int = 7) -> dict:
    """
    Search for BD targets using Tavily.
    Returns: {"success": bool, "data": [{"title", "url", "snippet"}]}
    """
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=brief,
            max_results=n,
            search_depth="advanced"
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")
            })
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}
