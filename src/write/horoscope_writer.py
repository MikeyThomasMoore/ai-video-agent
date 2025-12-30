# src/write/horoscope_writer.py
import os, json, datetime, time
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# OpenAI SDK (pip install openai)
from openai import OpenAI

ZODIAC_SIGNS: List[str] = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]

OPENAI_MODELS = {
    "gpt-5-mini": "gpt-5-mini ($0.25 / 1M tokens, score 85)",
    "gpt-5.1": "gpt-5.1 ($1.25 / 1M tokens, score 98)",
    "gpt-5": "gpt-5 ($1.24 / 1M tokens, score 95)",
    "gpt-5-nano": "gpt-5-nano ($0.05 / 1M tokens, score 75)",
    "gpt-4.1": "gpt-4.1 ($2.00 / 1M tokens, score 92)",
    "gpt-4.1-mini": "gpt-4.1-mini ($0.40 / 1M tokens, score 83)",
    "gpt-4.1-nano": "gpt-4.1-nano ($0.10 / 1M tokens, score 80)",
    "gpt-4o": "gpt-4o ($2.50 / 1M tokens, score 92)",
    "gpt-4o-mini": "gpt-4o-mini (Legacy, budget option)",
}

SYSTEM_STYLE = (
    "You are a witty, positive horoscope writer. "
    "Write concise, 2–3 sentence daily horoscopes with a clear prediction or action. "
    "Keep it PG, approachable, and a little playful."
)

# Initialize OpenAI client at module level
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY missing. Add it to your .env")
client = OpenAI(api_key=api_key)

def _model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5-nano")

def generate_daily_horoscopes(topic_date: datetime.date | None = None, model: str | None = None, signs: List[str] | None = None) -> Dict[str, str]:
    """
    Generates 12 short, prediction-style horoscopes (one per sign).
    
    Args:
        topic_date: Date for the horoscopes (defaults to today)
        model: OpenAI model to use (defaults to env OPENAI_MODEL or gpt-4o-mini)
        signs: List of specific signs to generate (defaults to all 12)
    
    Returns:
        Dict mapping zodiac sign to horoscope text
    """
    model = model or _model()
    today = (topic_date or datetime.date.today()).strftime("%B %d, %Y")
    
    # Filter to specific signs if requested
    signs_to_generate = signs if signs else ZODIAC_SIGNS

    print(f"\n✍️  Generating horoscopes for {today}")
    print(f"   Model: {OPENAI_MODELS.get(model, model)}")
    print(f"   Signs: {len(signs_to_generate)}")
    print()

    results: Dict[str, str] = {}
    for i, sign in enumerate(signs_to_generate, start=1):
        print(f"   [{i}/{len(signs_to_generate)}] Generating {sign}...", end=" ", flush=True)
        user_prompt = (
            f"Date: {today}\n"
            f"Sign: {sign}\n\n"
            "Write a short daily horoscope (2–3 sentences). "
            "Include a concrete prediction or recommended action for today."
        )
        try:
            # Some models (like gpt-5-nano) only support default temperature
            api_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_STYLE},
                    {"role": "user", "content": user_prompt},
                ],
            }
            # Only add temperature for models that support it
            if model not in ["gpt-5-nano", "gpt-4.1-nano"]:
                api_params["temperature"] = 0.8
            
            resp = client.chat.completions.create(**api_params)
            text = (resp.choices[0].message.content or "").strip()
            results[sign] = text
            print("✓")
        except Exception as e:
            # If the API is out of quota, or any other error, use a placeholder
            print(f"✗")
            print(f"       ERROR: {str(e)}")
            results[sign] = f"({sign} placeholder horoscope: Today is a lucky day! 🌟)"
        # Tiny delay to be polite on rate limits (adjust as needed)
        time.sleep(0.3)
    
    print(f"\n✅ Generated {len(results)} horoscopes")

    return results

def save_horoscopes(horoscopes: Dict[str, str], base_dir: str = "data/horoscopes") -> str:
    """
    Saves JSON + individual .txt files in a dated subfolder.
    Returns the directory path.
    """
    date_tag = datetime.date.today().strftime("%Y-%m-%d")
    out_dir = Path(base_dir) / date_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving horoscopes to {out_dir}")

    # Write JSON
    json_path = out_dir / "horoscopes.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(horoscopes, f, ensure_ascii=False, indent=2)

    # Write one .txt per sign
    for sign, text in horoscopes.items():
        (out_dir / f"{sign}.txt").write_text(text, encoding="utf-8")

    return str(out_dir)

if __name__ == "__main__":
    print("=" * 60)
    print("HOROSCOPE GENERATOR")
    print("=" * 60)
    hs = generate_daily_horoscopes()
    folder = save_horoscopes(hs)
    print(f"\n✅ Complete! Saved {len(hs)} horoscopes to {folder}")
    print("=" * 60)