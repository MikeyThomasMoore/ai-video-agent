"""
Veo 3 Horoscope Automation Scaffold
-----------------------------------

This script connects horoscope text generation (from horoscope_writer.py)
with Veo video generation prompts. For now, Veo is stubbed, so it writes
prompt .txt files, a manifest.json, and placeholder .mp4 files.

"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import argparse
import dataclasses
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Protocol, runtime_checkable, Optional
import requests
import time

class VeoClient:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"  # Vertex AI Generative API
    MODEL_ID = "veo-3.0-fast-generate-001"  # Always use the FAST variant

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("VEO_API_KEY")
        if not self.api_key:
            raise RuntimeError("VEO_API_KEY missing — add it to your .env")

    def _params(self):
        return {"key": self.api_key}

    def submit(self, scene: SceneSpec) -> VideoJob:
        payload = {
            "prompt": {
                "text": scene.prompt
            },
            "videoConfig": {
                "aspectRatio": scene.render.aspect_ratio,
                "durationSeconds": scene.render.seconds,
                "fps": scene.render.fps,
            }
        }

        r = requests.post(
            f"{self.BASE_URL}/models/{self.MODEL_ID}:generateVideo",
            params=self._params(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        # Google returns a long-running operation name we need to poll
        job_id = data["name"]
        return VideoJob(id=job_id, scene=scene, status="queued")

    def poll_until_done(self, job: VideoJob, out_dir: Path) -> VideoJob:
        while True:
            r = requests.get(
                f"{self.BASE_URL}/operations/{job.id}",
                params=self._params(),
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("done", False)

            if status:
                result = data.get("response", {})
                video_url = result.get("videoUri")
                if not video_url:
                    job.status = "failed"
                    return job

                renders = out_dir / "renders"
                renders.mkdir(parents=True, exist_ok=True)
                video_path = renders / f"{job.id}.mp4"

                with requests.get(video_url, stream=True) as resp:
                    resp.raise_for_status()
                    with open(video_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)

                job.video_path = str(video_path)
                job.status = "done"
                return job

            time.sleep(5)  # poll every 5 seconds

# Import horoscope generator
try:
    from src.write.horoscope_writer import generate_daily_horoscopes as real_generate
    if os.getenv("OPENAI_API_KEY"):
        generate_daily_horoscopes = real_generate
    else:
        raise ImportError("No API key, using mock")
except Exception:
    def generate_daily_horoscopes(topic_date: dt.date | None = None):
        date_str = (topic_date or dt.date.today()).strftime("%B %d, %Y")
        signs = [
            "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
            "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
        ]
        return {sign: f"{sign}: {date_str} is your lucky day — test horoscope only." for sign in signs}

# -----------------------------
# Data models
# -----------------------------
@dataclasses.dataclass
class RenderSpec:
    aspect_ratio: str = "9:16"
    seconds: int = 8   # Locked to Veo 3's max duration
    fps: int = 24
    seed: Optional[int] = None

@dataclasses.dataclass
class SceneSpec:
    sign: str
    script_text: str
    prompt: str
    render: RenderSpec
    style_tag: str

@dataclasses.dataclass
class VideoJob:
    id: str
    scene: SceneSpec
    status: str = "queued"
    video_path: Optional[str] = None

# -----------------------------
# Prompt template + transformers
# -----------------------------
DEFAULT_TEMPLATE = (
    "Cinematic {aspect} shot. Theme: whimsical astrology vlog in a cozy neon-lit studio. "
    "Foreground: narrator presence implied via over-the-shoulder framing or empty chair, "
    "floating holographic zodiac glyphs for {sign}. Ambient particle dust. Soft volumetric "
    "light through blinds. Camera: slow push-in, shallow depth of field. "
    "Color palette: muted teal, soft gold highlights. "
    "On-screen caption (subtitle style): '{caption}'. "
    "Keep timing readable for {seconds}s."
)

@runtime_checkable
class PromptTransformer(Protocol):
    def __call__(self, prompt: str, scene: SceneSpec) -> str: ...

class IdentityTransformer:
    def __call__(self, prompt: str, scene: SceneSpec) -> str:
        return prompt

class CyberpunkPunchup:
    def __call__(self, prompt: str, scene: SceneSpec) -> str:
        addon = " Add neon signage in the distance, subtle rain streaks, and UI scanlines."
        return prompt + addon

# -----------------------------
# Veo stub client
# -----------------------------
class VeoClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("VEO_API_KEY", "demo-key")

    def submit(self, scene: SceneSpec) -> VideoJob:
        job_id = f"veo_{scene.sign.lower()}_{int(dt.datetime.utcnow().timestamp())}"
        return VideoJob(id=job_id, scene=scene, status="queued")

    def poll_until_done(self, job: VideoJob, out_dir: Path) -> VideoJob:
        renders = out_dir / "renders"
        renders.mkdir(parents=True, exist_ok=True)
        job.video_path = str(renders / f"{job.id}.mp4")
        job.status = "done"
        return job

# -----------------------------
# Scene planner
# -----------------------------
class ScenePlanner:
    def __init__(self, render: RenderSpec, style_tag: str = "whimsical_astrology"):
        self.render = render
        self.style_tag = style_tag

    def build_scene(self, sign: str, text: str, template: str = DEFAULT_TEMPLATE) -> SceneSpec:
        prompt = template.format(
            aspect=self.render.aspect_ratio,
            sign=sign,
            caption=text,
            seconds=self.render.seconds,
        )
        return SceneSpec(sign, text, prompt, self.render, self.style_tag)

# -----------------------------
# Orchestrator
# -----------------------------
class HoroscopeVeoPipeline:
    def __init__(self, veo: VeoClient, transformers: Optional[List[PromptTransformer]] = None):
        self.veo = veo
        self.transformers = transformers or [IdentityTransformer()]

    def run(self, date: dt.date, out_dir: Path, render: RenderSpec, template: str = DEFAULT_TEMPLATE, style_tag: str = "whimsical_astrology") -> List[VideoJob]:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "prompts").mkdir(exist_ok=True)
        (out_dir / "renders").mkdir(exist_ok=True)

        scripts = generate_daily_horoscopes(date)
        planner = ScenePlanner(render, style_tag)
        scenes = [planner.build_scene(sign, text, template) for sign, text in scripts.items()]

        for scene in scenes:
            for t in self.transformers:
                scene.prompt = t(scene.prompt, scene)
            (out_dir / "prompts" / f"{scene.sign}.txt").write_text(scene.prompt, encoding="utf-8")

        jobs = []
        for scene in scenes:
            job = self.veo.submit(scene)
            job = self.veo.poll_until_done(job, out_dir)
            jobs.append(job)

        manifest = {
            "date": date.isoformat(),
            "aspect_ratio": render.aspect_ratio,
            "seconds": render.seconds,
            "jobs": [
                {
                    "id": j.id,
                    "sign": j.scene.sign,
                    "status": j.status,
                    "style": j.scene.style_tag,
                    "video_path": j.video_path,
                    "prompt_file": f"prompts/{j.scene.sign}.txt",
                }
                for j in jobs
            ],
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return jobs

# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Veo 3 Horoscope Automation")
    p.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--out", type=str, default="./out", help="Output directory")
    p.add_argument("--aspect", type=str, default="9:16", choices=["9:16", "16:9", "1:1"])
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--style", type=str, default="whimsical_astrology")
    p.add_argument("--cyberpunk", action="store_true")
    return p.parse_args()

def build_transformers(args: argparse.Namespace) -> List[PromptTransformer]:
    transformers: List[PromptTransformer] = [IdentityTransformer()]
    if args.cyberpunk:
        transformers.append(CyberpunkPunchup())
    return transformers

def main() -> None:
    args = parse_args()
    date = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else dt.date.today()

    render = RenderSpec(aspect_ratio=args.aspect, fps=args.fps)
    out_dir = Path(args.out)

    transformers = build_transformers(args)
    pipeline = HoroscopeVeoPipeline(veo=VeoClient(), transformers=transformers)

    jobs = pipeline.run(date=date, out_dir=out_dir, render=render, style_tag=args.style)

    print(json.dumps({"completed": len(jobs), "out": str(out_dir / 'manifest.json')}, indent=2))


if __name__ == "__main__":
    main()
