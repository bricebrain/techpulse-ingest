from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx

from app.core.config import settings

router = APIRouter(prefix="/reddit", tags=["Reddit"])
bearer = HTTPBearer(auto_error=False)

REDDIT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
REDDIT_HEADERS = {"User-Agent": REDDIT_UA, "Accept": "application/json"}


def verify_secret(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> None:
    """Vérifie le Bearer token si REDDIT_PROXY_SECRET est configuré."""
    if not settings.reddit_proxy_secret:
        return  # pas de secret → endpoint ouvert
    if not credentials or credentials.credentials != settings.reddit_proxy_secret:
        raise HTTPException(status_code=401, detail="Non autorisé")


@router.get("/{subreddit}")
async def fetch_reddit(
    subreddit: str,
    limit: int = Query(default=10, ge=1, le=25),
    _: None = Depends(verify_secret),
) -> dict:
    """
    Proxy Reddit JSON API.
    Utilisé par le Worker Cloudflare dont les IPs sont bloquées par Reddit.
    L'IP Render (AWS) n'est pas bannie.
    """
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url, headers=REDDIT_HEADERS)
            if not res.is_success:
                # Essai sur old.reddit.com en fallback
                url_old = f"https://old.reddit.com/r/{subreddit}/hot.json?limit={limit}"
                res = await client.get(url_old, headers=REDDIT_HEADERS)
                if not res.is_success:
                    return {"posts": [], "subreddit": subreddit, "count": 0,
                            "error": f"Reddit returned {res.status_code}"}

            data = res.json()
            posts = [
                {
                    "id": child["data"]["id"],
                    "title": child["data"]["title"],
                    "selftext": child["data"].get("selftext", ""),
                    "url": child["data"].get("url", ""),
                    "permalink": child["data"].get("permalink", ""),
                    "created_utc": child["data"].get("created_utc"),
                }
                for child in data.get("data", {}).get("children", [])
                if child.get("data", {}).get("title")
            ]
            return {"posts": posts, "subreddit": subreddit, "count": len(posts)}

        except httpx.TimeoutException:
            return {"posts": [], "subreddit": subreddit, "count": 0, "error": "timeout"}
        except Exception as e:
            return {"posts": [], "subreddit": subreddit, "count": 0, "error": str(e)}
