# mcp_tools/tools.py
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nexus-tools")


@mcp.tool()
def search_web(query: str) -> str:
    """Search the web using DuckDuckGo instant answers."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=5
        )
        data = resp.json()
        answer = data.get("AbstractText") or data.get("Answer") or ""
        related = [r["Text"] for r in data.get("RelatedTopics", [])[:3] if "Text" in r]
        if not answer and not related:
            return f"No instant answer found for '{query}'."
        return answer or " | ".join(related)
    except Exception as e:
        return f"Search failed: {e}"


@mcp.tool()
def get_crypto_price(symbol: str) -> str:
    """Get live cryptocurrency price from CoinGecko (free, no API key needed)."""
    try:
        coin_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
        coin_id = coin_map.get(symbol.upper(), symbol.lower())
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_vol": "true"},
            timeout=5
        )
        data = resp.json()
        if coin_id not in data:
            return f"Symbol '{symbol}' not found."
        price = data[coin_id]["usd"]
        vol = data[coin_id].get("usd_24h_vol", "N/A")
        return f"{symbol.upper()}: ${price:,.2f} USD | 24h Vol: ${vol:,.0f}"
    except Exception as e:
        return f"Price fetch failed: {e}"


@mcp.tool()
def get_weather(city: str) -> str:
    """Get current weather for a city using Open-Meteo (free, no API key)."""
    try:
        # Geocode the city first
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=5
        ).json()
        results = geo.get("results")
        if not results:
            return f"City '{city}' not found."
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]

        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current_weather": True
            },
            timeout=5
        ).json()
        cw = weather.get("current_weather", {})
        return (
            f"{city}: {cw.get('temperature')}°C, "
            f"wind {cw.get('windspeed')} km/h, "
            f"weathercode {cw.get('weathercode')}"
        )
    except Exception as e:
        return f"Weather fetch failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")