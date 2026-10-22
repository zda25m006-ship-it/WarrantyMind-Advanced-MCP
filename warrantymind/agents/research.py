from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import httpx

from warrantymind.config import (
    BRAVE_SEARCH_API_KEY,
    BRAVE_SEARCH_BASE_URL,
    RESEARCH_COUNTRY,
    RESEARCH_TIMEOUT_SECONDS,
)

_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 30 * 60


def _safe_search_terms(value: str, limit: int = 10, allow_numbers: bool = True) -> str:
    """Keep external queries to product/symptom words; never forward case narratives."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]{1,24}", str(value or ""))
    ignored = {"the", "and", "with", "from", "this", "that", "customer", "device", "issue", "reported"}
    clean = [
        word for word in words
        if word.lower() not in ignored and (allow_numbers or not any(char.isdigit() for char in word))
    ]
    return " ".join(clean[:limit])


def _safe_symptom_topics(values: Iterable[Any]) -> List[str]:
    """Map arbitrary complaint/VLM text to a small allowlist before any web request."""
    text = " ".join(str(value or "") for value in values).lower().replace("_", " ")
    topics = (
        "green line", "display", "screen", "flicker", "battery", "charging",
        "overheating", "touch", "camera", "speaker", "microphone", "wifi",
        "bluetooth", "boot", "power", "sensor", "sync", "connectivity",
    )
    return [topic for topic in topics if re.search(rf"\b{re.escape(topic)}\b", text)]


def _host_matches(host: str, domains: Iterable[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _cached_search(group: str, query: str, country: str) -> Dict[str, Any]:
    key = (group, f"{country}:{query.lower()}")
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            result = dict(cached[1])
            result["cached"] = True
            return result

    if not BRAVE_SEARCH_API_KEY:
        return {
            "status": "not_configured",
            "provider": "Brave Search",
            "message": "Set WM_BRAVE_SEARCH_API_KEY to enable live web research.",
            "sources": [],
        }

    try:
        response = httpx.get(
            BRAVE_SEARCH_BASE_URL,
            params={
                "q": query[:600],
                "country": country or RESEARCH_COUNTRY,
                "search_lang": "en",
                "count": 10,
                "safesearch": "moderate",
            },
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
            },
            timeout=RESEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        normalized = []
        for item in (payload.get("web") or {}).get("results", [])[:10]:
            url = str(item.get("url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname:
                continue
            normalized.append({
                "title": str(item.get("title") or "Source")[:240],
                "url": url[:1000],
                "snippet": str(item.get("description") or "")[:900],
                "domain": parsed.hostname.lower(),
                "published": str(item.get("page_age") or "")[:80] or None,
            })
        result = {
            "status": "ready" if normalized else "no_results",
            "provider": "Brave Search",
            "message": "" if normalized else "No matching public sources were returned.",
            "sources": normalized,
            "cached": False,
        }
        with _CACHE_LOCK:
            _CACHE[key] = (time.monotonic(), dict(result))
        return result
    except httpx.HTTPStatusError as exc:
        status = "rate_limited" if exc.response.status_code == 429 else "unavailable"
        return {
            "status": status,
            "provider": "Brave Search",
            "message": f"Search provider returned HTTP {exc.response.status_code}.",
            "sources": [],
        }
    except (httpx.HTTPError, ValueError, OSError) as exc:
        return {
            "status": "unavailable",
            "provider": "Brave Search",
            "message": f"Search provider could not be reached ({type(exc).__name__}).",
            "sources": [],
        }


class WarrantyResearchAgent:
    """Find current warranty/repair information from Google-owned domains only."""

    name = "Google Warranty Researcher"
    allowed_domains = ("google.com",)

    def run(self, order_record: Dict[str, Any], symptoms: List[str]) -> Dict[str, Any]:
        model = _safe_search_terms(order_record.get("product_model", "Pixel device"), 6) or "Google Pixel device"
        symptom = _safe_search_terms(" ".join(symptoms), 8, allow_numbers=False)
        region = _safe_search_terms(order_record.get("region", RESEARCH_COUNTRY), 2) or RESEARCH_COUNTRY
        query = f'site:support.google.com OR site:store.google.com "{model}" warranty repair {region} {symptom}'
        result = _cached_search("warranty", query, region)
        sources = []
        for item in result.get("sources", []):
            if not _host_matches(item.get("domain", ""), self.allowed_domains):
                continue
            sources.append({"source_id": f"W{len(sources) + 1}", "source_type": "official_google", **item})
        return {
            "agent": self.name,
            "status": result["status"] if sources or result["status"] in {"not_configured", "unavailable", "rate_limited"} else "no_results",
            "provider": result.get("provider"),
            "query": query,
            "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "message": result.get("message", "") if sources or result["status"] in {"not_configured", "unavailable", "rate_limited"} else "No official Google warranty source was found. Coverage remains unverified.",
            "sources": sources,
        }


class CommunityResearchAgent:
    """Search indexed Reddit and Google Help Community posts; treat them as anecdotes."""

    name = "Pixel Community Researcher"
    allowed_domains = ("reddit.com", "support.google.com")

    @staticmethod
    def _communities(product_category: str) -> Tuple[str, str]:
        category = product_category.lower()
        if "watch" in category:
            return "GooglePixelWatch", "googlepixelwatch"
        if "book" in category or "laptop" in category or "chromebook" in category:
            return "chromeos", "chromebook"
        return "GooglePixel", "pixelphone"

    def run(self, order_record: Dict[str, Any], symptoms: List[str]) -> Dict[str, Any]:
        model = _safe_search_terms(order_record.get("product_model", "Pixel device"), 6) or "Google Pixel device"
        symptom = _safe_search_terms(" ".join(symptoms), 8, allow_numbers=False)
        country = _safe_search_terms(order_record.get("region", RESEARCH_COUNTRY), 2) or RESEARCH_COUNTRY
        reddit_community, google_community = self._communities(order_record.get("product_category", "Pixel Phone"))
        query = (
            f'(site:reddit.com/r/{reddit_community} OR '
            f'site:support.google.com/{google_community}/community) "{model}" {symptom} repair experience'
        )
        result = _cached_search("community", query, country)
        sources = []
        for item in result.get("sources", []):
            domain = item.get("domain", "")
            path = urlparse(item.get("url", "")).path.lower()
            if not _host_matches(domain, self.allowed_domains):
                continue
            if domain == "support.google.com" and not any(part in path for part in ("community", "thread")):
                continue
            sources.append({"source_id": f"C{len(sources) + 1}", "source_type": "community_anecdote", **item})
        return {
            "agent": self.name,
            "status": result["status"] if sources or result["status"] in {"not_configured", "unavailable", "rate_limited"} else "no_results",
            "provider": result.get("provider"),
            "query": query,
            "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "message": (
                "Community posts are user reports; contributor identity and technical qualifications are not verified."
                if sources else result.get("message", "") if result["status"] in {"not_configured", "unavailable", "rate_limited"}
                else "No matching community reports were found. Community sources are not policy authority."
            ),
            "sources": sources,
            "source_limitations": ["Anecdotal, not verified technical advice", "Never determines warranty eligibility"],
        }


def collect_device_research(order_record: Dict[str, Any], visual_observations: Dict[str, Any], reported_symptom: str) -> Dict[str, Any]:
    symptoms = _safe_symptom_topics(
        [reported_symptom, *(visual_observations.get("observable_symptoms") or [])]
    )
    warranty_agent = WarrantyResearchAgent()
    community_agent = CommunityResearchAgent()
    with ThreadPoolExecutor(max_workers=2) as executor:
        warranty_future = executor.submit(warranty_agent.run, order_record, symptoms)
        community_future = executor.submit(community_agent.run, order_record, symptoms)
        warranty = warranty_future.result()
        community = community_future.result()
    return {
        "warranty_research": warranty,
        "community_research": community,
        "source_policy": "External searches use only product model and symptom labels; customer narrative, contact details, serial numbers, and images are not sent to the search provider.",
    }
