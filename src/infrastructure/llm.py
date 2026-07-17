"""LLM client with Claude/Gemini fallback."""
import json
import os
import urllib.request

from src.adapters.gateways import LLM


class LlmClient(LLM):
    """LLM client supporting Claude and Gemini with fallback."""

    def complete(self, system, user):
        """Complete a prompt using Claude or Gemini (with fallback)."""
        # Prioritize Claude if API key available
        if os.environ.get("ANTHROPIC_API_KEY"):
            return self._call_claude(system, user)
        if os.environ.get("GEMINI_API_KEY"):
            return self._call_gemini(system, user)
        if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return self._call_claude(system, user)
        raise RuntimeError("Chưa cấu hình LLM key (GEMINI_API_KEY hoặc ANTHROPIC_API_KEY)")

    @staticmethod
    def _call_gemini(system, user):
        """Call Gemini API with retry + fallback model for rate limit handling."""
        import time
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
        }).encode()
        last = None
        # Retry + fallback model: free tier often gets 503/429 temporarily
        for model in (os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"), "gemini-3.1-flash-lite"):
            for _ in range(2):
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    data=body,
                    headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
                try:
                    j = json.load(urllib.request.urlopen(req, timeout=120))
                    return "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
                except urllib.error.HTTPError as e:
                    if e.code not in (429, 500, 503):
                        raise
                    last = e
                    time.sleep(3)
        raise last

    @staticmethod
    def _call_claude(system, user):
        """Call Claude API via Anthropic SDK (lazy import)."""
        import anthropic  # lazy: only loaded if needed
        resp = anthropic.Anthropic().messages.create(
            model="claude-opus-4-8",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")
