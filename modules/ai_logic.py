"""
PaperBrief — AI Orchestration Module
Converts academic abstracts & conclusions into narration scripts using LLM APIs.
Output follows the PaperBrief content structure:
  Hook (0-10s) → Insight (10-40s) → Impact (40-60s)

Supported providers:
  - gemini   (Google Gemini via google.genai)
  - openai   (OpenAI GPT models via openai SDK)
  - openrouter (Any model via OpenRouter API)
"""

import json
import logging
import re
from typing import Optional

from google import genai
from google.genai import types
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config

logger = logging.getLogger(__name__)

# ── Language Configs ──────────────────────────────────────────────────────────

LANGUAGE_CONFIGS = {
    "EN": {
        "name": "English",
        "hook_examples": [
            '"Scientists just discovered a way to..."',
            '"This latest paper changes how we see [Topic]..."',
        ],
        "impact_opener": '"This means in the future, we could..."',
    },
    "ID": {
        "name": "Bahasa Indonesia",
        "hook_examples": [
            '"Ilmuwan baru saja menemukan cara untuk..."',
            '"Paper terbaru ini mengubah cara kita melihat [Topik]..."',
        ],
        "impact_opener": '"Artinya, di masa depan kita bisa..."',
    },
    "ES": {
        "name": "Español",
        "hook_examples": [
            '"Los científicos acaban de descubrir una forma de..."',
            '"Este último artículo cambia nuestra visión de [Tema]..."',
        ],
        "impact_opener": '"Esto significa que en el futuro podremos..."',
    },
    "FR": {
        "name": "Français",
        "hook_examples": [
            '"Des scientifiques viennent de découvrir un moyen de..."',
            '"Ce dernier article change notre vision de [Sujet]..."',
        ],
        "impact_opener": '"Cela signifie que dans le futur, nous pourrons..."',
    },
}


def _build_system_prompt(lang: str = "EN") -> str:
    """Build the system prompt for the given language."""
    lang = lang.upper()
    lang_config = LANGUAGE_CONFIGS.get(lang, LANGUAGE_CONFIGS["EN"])
    lang_name = lang_config["name"]
    hook_ex = " or ".join(lang_config["hook_examples"])
    impact_opener = lang_config["impact_opener"]

    return f"""You are a world-class Science Communicator who creates viral YouTube Shorts scripts.
Your job is to transform dense academic papers into exciting, accessible 60-second narration scripts.

CRITICAL: You MUST write the ENTIRE script in {lang_name}.
The paper source may be in English, but your output narration MUST be in {lang_name}.

RULES:
- Write in {lang_name}, conversational tone — as if explaining to a smart friend.
- Total word count MUST be 120–150 words (this maps to ~50-60 seconds of narration).
- Use vivid analogies and concrete examples. NO jargon without explanation.
- Follow the EXACT content structure below.

CONTENT STRUCTURE (strict timing):
1. HOOK (0-10 seconds, ~20-25 words):
   Start with an attention-grabbing opener like:
   {hook_ex}

2. INSIGHT (10-40 seconds, ~60-80 words):
   - Briefly explain the methodology in 1-2 sentences.
   - State the key finding clearly.
   - Use ONE powerful analogy to make it click.
   - This is the "meat" — large text overlay material.

3. IMPACT (40-60 seconds, ~30-40 words):
   - Connect findings to real life: {impact_opener}
   - End with a thought-provoking statement or call to action.
   - Make the viewer feel the significance.

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown fencing:
{{
  "hook": "The hook narration text in {lang_name} (0-10s)",
  "insight": "The insight narration text in {lang_name} (10-40s)",
  "insight_points": [
    "Key finding #1 — short text overlay phrase in {lang_name}",
    "Key finding #2 — short text overlay phrase in {lang_name}",
    "Key finding #3 — short text overlay phrase in {lang_name}"
  ],
  "impact": "The impact narration in {lang_name} (40-60s)",
  "visual_prompts": {{
    "hook": "Highly detailed, cinematic Midjourney-style image generation prompt for the hook background. Include lighting, atmosphere, and specific subjects related to the core topic. (always in English)",
    "insight": "Description for insight background image (always in English)",
    "impact": "Description for impact background image (always in English)"
  }},
  "title_short": "A catchy 5-8 word title in {lang_name}",
  "hashtags": ["#science", "#research", "#relevant_tag"]
}}"""


def _build_user_prompt(paper_data: dict) -> str:
    """Build the user-facing prompt with paper content."""
    authors_str = ", ".join(paper_data["authors"][:3])
    if len(paper_data["authors"]) > 3:
        authors_str += " et al."

    # Truncate conclusion if too long
    conclusion = paper_data.get("conclusion", "")
    if len(conclusion) > 2000:
        conclusion = conclusion[:2000] + "..."

    return f"""Transform this research paper into a 60-second YouTube Short script:

PAPER TITLE: {paper_data['title']}
AUTHORS: {authors_str}
arXiv ID: {paper_data.get('arxiv_id', 'N/A')}

ABSTRACT:
{paper_data['abstract']}

CONCLUSION/KEY FINDINGS:
{conclusion}

Remember: Output ONLY valid JSON following the exact schema specified. Total narration ~120-150 words."""


# ── Gemini API ───────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, model: str = "gemini-2.5-flash",
                 system_prompt: str = "") -> str:
    """Call Google Gemini API and return raw text response."""
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    logger.info(f"  Gemini model: {model}")
    response = client.models.generate_content(
        model=model,
        contents=system_prompt + "\n\n" + prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=2048,
        ),
    )

    return response.text


# ── OpenAI API ───────────────────────────────────────────────────────────────

def _call_openai(prompt: str, model: str = "gpt-4o-mini",
                 system_prompt: str = "") -> str:
    """Call OpenAI Chat Completions API."""
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")

    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

    logger.info(f"  OpenAI model: {model}")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=2048,
    )

    return response.choices[0].message.content


# ── OpenRouter API ───────────────────────────────────────────────────────────

def _call_openrouter(prompt: str, model: str = config.OPENROUTER_MODEL,
                     system_prompt: str = "") -> str:
    """Call OpenRouter API — supports any model available on OpenRouter."""
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://paperbrief.app",
        "X-Title": "PaperBrief",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 2048,
    }

    logger.info(f"  OpenRouter model: {model}")
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{config.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


# ── Provider Dispatcher ──────────────────────────────────────────────────────

# Default models for each provider (used when user doesn't specify a model)
DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "openrouter": config.OPENROUTER_MODEL,
}

# Maps provider name → callable
PROVIDER_FUNCTIONS = {
    "gemini": _call_gemini,
    "openai": _call_openai,
    "openrouter": _call_openrouter,
}


def _dispatch_llm(prompt: str, provider: str, model: str = None,
                  system_prompt: str = "") -> str:
    """
    Dispatch a prompt to the specified provider + model.

    Args:
        prompt: The user prompt text
        provider: "gemini", "openai", or "openrouter"
        model: Model name override (if None, uses provider default)
        system_prompt: The system prompt to use

    Returns:
        Raw LLM text response
    """
    if provider not in PROVIDER_FUNCTIONS:
        raise ValueError(f"Unknown LLM provider: {provider}. Choose from: {list(PROVIDER_FUNCTIONS.keys())}")

    call_fn = PROVIDER_FUNCTIONS[provider]
    use_model = model or DEFAULT_MODELS.get(provider, "")

    return call_fn(prompt, model=use_model, system_prompt=system_prompt)


# ── JSON Parsing ─────────────────────────────────────────────────────────────

def _parse_script_json(raw_text: str) -> dict:
    """
    Parse the LLM response into a structured script dict.
    Handles common issues like markdown code fences around JSON.
    """
    if not raw_text:
        raise ValueError("Received empty or null response from LLM (possibly blocked or rate-limited).")

    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        script = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw response:\n{raw_text[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # Validate required keys
    required_keys = ["hook", "insight", "insight_points", "impact", "visual_prompts"]
    missing = [k for k in required_keys if k not in script]
    if missing:
        raise ValueError(f"Script JSON missing required keys: {missing}")

    return script


# ── Main Entry Point ─────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(config.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=lambda retry_state: logger.warning(
        f"Script generation retry #{retry_state.attempt_number}..."
    ),
)
def generate_script(paper_data: dict, provider: str = "gemini",
                    model: str = None, lang: str = "EN") -> dict:
    """
    Generate a narration script from paper data using an LLM.

    Args:
        paper_data: Dict with keys: title, authors, abstract, conclusion
        provider: "gemini", "openai", or "openrouter"
        model: Specific model name (e.g. "gemini-2.0-flash", "gpt-4o-mini",
               "xiaomi/mimo-v2-flash"). If None, uses provider default.
        lang: Language code ("EN", "ID", "ES", "FR", etc.)

    Returns:
        Structured script dict with hook, insight, insight_points, impact, visual_prompts
    """
    user_prompt = _build_user_prompt(paper_data)
    use_model = model or DEFAULT_MODELS.get(provider, "")
    system_prompt = _build_system_prompt(lang)

    lang_name = LANGUAGE_CONFIGS.get(lang.upper(), LANGUAGE_CONFIGS["EN"])["name"]
    logger.info(f"🤖 Generating script with {provider} ({use_model}) in {lang_name}...")

    # We will try the primary provider/model first, then fallbacks
    # For openrouter, free models often hit hard output limits, so we add intra-provider model fallbacks
    attempts = [
        {"provider": provider, "model": use_model}
    ]
    
    # Add cross-provider fallbacks
    for p in ["openrouter", "gemini", "openai"]:
        if p != provider:
            attempts.append({"provider": p, "model": DEFAULT_MODELS.get(p)})
            
    # Add specific openrouter fallbacks just in case main openrouter fails due to token limits
    if provider == "openrouter":
        attempts.extend([
            {"provider": "openrouter", "model": "google/gemma-3-27b-it:free"},
            {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
            {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free"},
            {"provider": "openrouter", "model": "microsoft/phi-3-mini-128k-instruct:free"}
        ])

    script = None
    last_err = None

    import time
    for attempt in attempts:
        attempt_prov = attempt["provider"]
        attempt_model = attempt["model"]
        
        try:
            raw_response = _dispatch_llm(user_prompt, attempt_prov, attempt_model, system_prompt=system_prompt)
            script = _parse_script_json(raw_response)
            
            # Combine full narration text for TTS
            script["full_narration"] = f"{script['hook']} {script['insight']} {script['impact']}"
            logger.info(f"✅ Success with {attempt_prov} ({attempt_model}). Generated script: '{script.get('title_short', 'N/A')}' ({len(script['full_narration'].split())} words)")
            break
            
        except Exception as e:
            last_err = e
            logger.warning(f"⚠ Attempt with {attempt_prov} ({attempt_model}) failed: {e}")
            if "gemini" not in attempt_prov and "openai" not in attempt_prov:
                # Sleep briefly to avoid immediately triggering a 429 on the next OpenRouter fallback
                time.sleep(3)
            continue

    if not script:
        raise RuntimeError(f"All LLM providers and fallback models failed. Last error: {last_err}")

    return script
