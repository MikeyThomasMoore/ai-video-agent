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

SYSTEM_STYLE = (
    "You are a witty, positive horoscope writer. "
    "Write concise, 2–3 sentence daily horoscopes with a clear prediction or action. "
    "Keep it PG, approachable, and a little playful."
)

def _client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing. Add it to your .env")
    return OpenAI(api_key=api_key)

def _model() -> str:
    return os.getenv("MODEL", "gpt-4o-mini")

def generate_daily_horoscopes(topic_date: datetime.date | None = None) -> Dict[str, str]:
    """
    Generates 12 short, prediction-style horoscopes (one per sign).
    Returns a dict: { sign: text }
    """
    client = _client()
    model = _model()
    today = (topic_date or datetime.date.today()).strftime("%B %d, %Y")

    results: Dict[str, str] = {}
    for i, sign in enumerate(ZODIAC_SIGNS, start=1):
        user_prompt = (
            f"Date: {today}\n"
            f"Sign: {sign}\n\n"
            "Write a short daily horoscope (2–3 sentences). "
            "Include a concrete prediction or recommended action for today."
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.8,
                messages=[
                    {"role": "system", "content": SYSTEM_STYLE},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            results[sign] = text
        except Exception as e:
            # If the API is out of quota, or any other error, use a placeholder
            results[sign] = f"({sign} placeholder horoscope: Today is a lucky day! 🌟)"
        # Tiny delay to be polite on rate limits (adjust as needed)
        time.sleep(0.3)

    return results

def save_horoscopes(horoscopes: Dict[str, str], base_dir: str = "data/horoscopes") -> str:
    """
    Saves JSON + individual .txt files in a dated subfolder.
    Returns the directory path.
    """
    date_tag = datetime.date.today().strftime("%Y-%m-%d")
    out_dir = Path(base_dir) / date_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = out_dir / "horoscopes.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(horoscopes, f, ensure_ascii=False, indent=2)

    # Write one .txt per sign
    for sign, text in horoscopes.items():
        (out_dir / f"{sign}.txt").write_text(text, encoding="utf-8")

    return str(out_dir)

if __name__ == "__main__":
    hs = generate_daily_horoscopes()
    folder = save_horoscopes(hs)
    print(f"✅ Saved {len(hs)} horoscopes to {folder}")