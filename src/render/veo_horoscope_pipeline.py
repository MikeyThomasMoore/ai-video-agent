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

# Import subtitle utilities
try:
    from .subtitle_utils import add_caption_to_video
except ImportError:
    # Fall back to absolute import when run as script
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from subtitle_utils import add_caption_to_video

class VeoClient:
    """Client for Google Vertex AI Veo video generation API"""
    
    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None, 
                 region: Optional[str] = None, model_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.project_id = project_id or os.getenv("GOOGLE_PROJECT_ID")
        self.region = region or os.getenv("GOOGLE_REGION", "us-central1")
        self.model_id = model_id or os.getenv("VEO_MODEL_ID", "veo-3.1-generate-001")
        
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY missing — add it to your .env")
        if not self.project_id:
            raise RuntimeError("GOOGLE_PROJECT_ID missing — add it to your .env")

    def submit(self, scene: SceneSpec) -> VideoJob:
        """Submit video generation request using predictLongRunning endpoint"""
        url = (f"https://{self.region}-aiplatform.googleapis.com/v1/"
               f"projects/{self.project_id}/locations/{self.region}/"
               f"publishers/google/models/{self.model_id}:predictLongRunning"
               f"?key={self.api_key}")
        
        # Build parameters dict from RenderSpec
        parameters = {
            "aspectRatio": scene.render.aspect_ratio,
            "durationSeconds": scene.render.seconds,
            "sampleCount": 1
        }
        
        # Add optional parameters
        if hasattr(scene.render, 'resolution') and scene.render.resolution:
            parameters["resolution"] = scene.render.resolution
        if hasattr(scene.render, 'generate_audio') and scene.render.generate_audio is not None:
            parameters["generateAudio"] = scene.render.generate_audio
        if hasattr(scene.render, 'compression_quality') and scene.render.compression_quality:
            parameters["compressionQuality"] = scene.render.compression_quality
        if scene.render.seed is not None:
            parameters["seed"] = scene.render.seed
        
        payload = {
            "instances": [{
                "prompt": scene.prompt
            }],
            "parameters": parameters
        }
        
        print(f"\n🎬 Submitting video generation for {scene.sign}")
        print(f"   Model: {self.model_id}")
        print(f"   Aspect: {parameters['aspectRatio']} | Duration: {parameters['durationSeconds']}s")
        if parameters.get('resolution'):
            print(f"   Resolution: {parameters['resolution']} | Audio: {parameters.get('generateAudio', 'N/A')}")
        
        try:
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
            r.raise_for_status()
            data = r.json()
            
            if "name" not in data:
                raise RuntimeError(f"No operation name in response: {data}")
            
            operation_name = data["name"]
            print(f"✅ Operation started: {operation_name}")
            return VideoJob(id=operation_name, scene=scene, status="queued")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"   Error details: {error_data}")
                except:
                    print(f"   Response text: {e.response.text}")
            raise

    def poll_until_done(self, job: VideoJob, out_dir: Path, max_polls: int = 120) -> VideoJob:
        """Poll for operation completion using fetchPredictOperation endpoint"""
        
        # Extract model ID from operation name
        # Format: projects/PROJECT_ID/locations/REGION/publishers/google/models/MODEL_ID/operations/OPERATION_ID
        model_match = job.id.split("/models/")
        if len(model_match) < 2:
            raise RuntimeError(f"Could not extract model ID from operation name: {job.id}")
        
        model_id = model_match[1].split("/operations")[0]
        
        fetch_url = (f"https://{self.region}-aiplatform.googleapis.com/v1/"
                    f"projects/{self.project_id}/locations/{self.region}/"
                    f"publishers/google/models/{model_id}:fetchPredictOperation"
                    f"?key={self.api_key}")
        
        print(f"🔄 Polling operation for {job.scene.sign}... (max {max_polls * 5 // 60} minutes)")
        poll_count = 0
        last_update = 0
        
        while poll_count < max_polls:
            poll_count += 1
            
            try:
                r = requests.post(
                    fetch_url,
                    json={"operationName": job.id},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                r.raise_for_status()
                data = r.json()
                
                if data.get("done"):
                    if "error" in data:
                        print(f"❌ Operation failed: {data['error']}")
                        job.status = "failed"
                        return job
                    
                    # Extract video URLs from response.videos[]
                    response = data.get("response", {})
                    videos = response.get("videos", [])
                    
                    if not videos:
                        print(f"❌ No videos found in completed operation")
                        job.status = "failed"
                        return job
                    
                    # Get first video URL (gcsUri or bytesBase64Encoded)
                    video = videos[0]
                    video_url = video.get("gcsUri") or video.get("bytesBase64Encoded")
                    
                    if not video_url:
                        print(f"❌ No video URL in completed operation")
                        job.status = "failed"
                        return job
                    
                    # Download video if it's a GCS URL
                    renders = out_dir / "renders"
                    renders.mkdir(parents=True, exist_ok=True)
                    
                    if video_url.startswith("gs://"):
                        # For GCS URLs, we'd need signed URLs or Cloud Storage API
                        # For now, store the GCS path
                        print(f"✅ Video ready at: {video_url}")
                        job.video_path = video_url
                        job.status = "done"
                    elif video_url.startswith("http"):
                        # Download from HTTP URL
                        video_path_raw = renders / f"{job.scene.sign.lower()}_raw.mp4"
                        with requests.get(video_url, stream=True) as resp:
                            resp.raise_for_status()
                            with open(video_path_raw, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    f.write(chunk)
                        print(f"✅ Video downloaded: {video_path_raw}")
                        
                        # Add caption using ffmpeg
                        video_path_final = renders / f"{job.scene.sign.lower()}.mp4"
                        print(f"🎬 Adding caption to video...")
                        success, message = add_caption_to_video(
                            video_path=str(video_path_raw),
                            caption_text=job.scene.script_text,
                            output_path=str(video_path_final),
                            duration=float(job.scene.render.seconds),
                            resolution=job.scene.render.resolution or "720p",
                            fontsize=int(os.getenv("CAPTION_FONT_SIZE", "36")),
                            fontcolor="white",
                            outline=2,
                            outlinecolor="black",
                            crf=18,
                            preset="medium",
                            style=os.getenv("CAPTION_STYLE", "scroll")
                        )
                        
                        if success:
                            print(f"✅ Caption added successfully: {video_path_final}")
                            job.video_path = str(video_path_final)
                            job.status = "done"
                        else:
                            print(f"⚠️  Caption failed: {message}")
                            print(f"   Using raw video instead: {video_path_raw}")
                            job.video_path = str(video_path_raw)
                            job.status = "done"
                    else:
                        # Base64 encoded video - decode and save
                        import base64
                        video_path_raw = renders / f"{job.scene.sign.lower()}_raw.mp4"
                        try:
                            video_data = base64.b64decode(video_url)
                            with open(video_path_raw, "wb") as f:
                                f.write(video_data)
                            print(f"✅ Video decoded and saved: {video_path_raw}")
                            
                            # Add caption using ffmpeg
                            video_path_final = renders / f"{job.scene.sign.lower()}.mp4"
                            print(f"🎬 Adding caption to video...")
                            success, message = add_caption_to_video(
                                video_path=str(video_path_raw),
                                caption_text=job.scene.script_text,
                                output_path=str(video_path_final),
                                duration=float(job.scene.render.seconds),
                                resolution=job.scene.render.resolution or "720p",
                                fontsize=int(os.getenv("CAPTION_FONT_SIZE", "36")),
                                fontcolor="white",
                                outline=2,
                                outlinecolor="black",
                                crf=18,
                                preset="medium",
                                style=os.getenv("CAPTION_STYLE", "scroll")
                            )
                            
                            if success:
                                print(f"✅ Caption added successfully: {video_path_final}")
                                job.video_path = str(video_path_final)
                                job.status = "done"
                            else:
                                print(f"⚠️  Caption failed: {message}")
                                print(f"   Using raw video instead: {video_path_raw}")
                                job.video_path = str(video_path_raw)
                                job.status = "done"
                        except Exception as e:
                            print(f"❌ Failed to decode video: {e}")
                            job.video_path = video_url  # Store base64 string as fallback
                            job.status = "done"
                    
                    return job
                
                # Still processing
                if poll_count % 12 == 0:  # Every minute
                    elapsed = poll_count * 5
                    print(f"   ⏳ Still processing... ({elapsed}s elapsed, poll #{poll_count}/{max_polls})")
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ Polling error: {e}")
                if poll_count >= max_polls:
                    job.status = "failed"
                    return job
            
            time.sleep(5)  # poll every 5 seconds
        
        print(f"⏱️  Polling timeout after {max_polls} attempts")
        job.status = "timeout"
        return job

# Import horoscope generator
try:
    # Try relative import first (when run as module)
    try:
        from ..write.horoscope_writer import generate_daily_horoscopes as real_generate, OPENAI_MODELS
    except (ImportError, ValueError):
        # Fall back to absolute import with path manipulation (when run as script)
        import sys
        from pathlib import Path
        # Add project root to path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src.write.horoscope_writer import generate_daily_horoscopes as real_generate, OPENAI_MODELS
    
    if os.getenv("OPENAI_API_KEY"):
        generate_daily_horoscopes = real_generate
    else:
        raise RuntimeError("OPENAI_API_KEY not found in environment. Add it to your .env file.")
except Exception as e:
    print("\n" + "=" * 70)
    print("❌ ERROR: Failed to initialize OpenAI horoscope generator")
    print("=" * 70)
    print(f"Error details: {str(e)}")
    print("\nPossible causes:")
    print("  1. OPENAI_API_KEY missing or invalid in .env file")
    print("  2. OpenAI SDK not installed (pip install openai)")
    print("  3. Import error in horoscope_writer.py")
    print("\nTo fix:")
    print("  - Check your .env file has OPENAI_API_KEY set")
    print("  - Run: pip install openai")
    print("=" * 70)
    raise

# -----------------------------
# Constants
# -----------------------------
VEO_MODELS = {
    "veo-2.0-generate-001": "Veo 2 (Standard)",
    "veo-2.0-generate-exp": "Veo 2 (Experimental)",
    "veo-2.0-generate-preview": "Veo 2 (Preview)",
    "veo-3.0-generate-001": "Veo 3 (Standard)",
    "veo-3.0-fast-generate-001": "Veo 3 (Fast)",
    "veo-3.1-generate-001": "Veo 3.1 (Standard)",
    "veo-3.1-fast-generate-001": "Veo 3.1 (Fast)",
    "veo-3.1-generate-preview": "Veo 3.1 (Preview)",
    "veo-3.1-fast-generate-preview": "Veo 3.1 Fast (Preview)",
}

# -----------------------------
# Data models
# -----------------------------
@dataclasses.dataclass
class RenderSpec:
    aspect_ratio: str = "9:16"
    seconds: int = 8   # Locked to Veo 3's max duration
    fps: int = 24
    resolution: Optional[str] = "720p"  # 720p, 1080p, etc.
    generate_audio: Optional[bool] = True  # Veo 3+ only
    compression_quality: Optional[str] = "optimized"  # optimized, high
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
    "Foreground: narrator presence implied via over-the-shoulder framing, "
    "Ambient particle dust. Soft volumetric "
    "light through blinds. Camera: slow push-in, shallow depth of field. "
    "Color palette: muted teal, soft gold highlights. "
#    "On-screen caption (subtitle style): '{caption}'. "
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
    def __init__(self, veo: VeoClient, transformers: Optional[List[PromptTransformer]] = None, openai_model: Optional[str] = None):
        self.veo = veo
        self.transformers = transformers or [IdentityTransformer()]
        self.openai_model = openai_model

    def run(self, date: dt.date, out_dir: Path, render: RenderSpec, template: str = DEFAULT_TEMPLATE, style_tag: str = "whimsical_astrology", signs: Optional[List[str]] = None, test_mode: bool = False) -> List[VideoJob]:
        print("\n" + "=" * 70)
        print("STEP 1/3: SETUP & HOROSCOPE GENERATION")
        print("=" * 70)
        
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "prompts").mkdir(exist_ok=True)
        (out_dir / "renders").mkdir(exist_ok=True)
        print(f"📁 Output directory: {out_dir}")

        scripts = generate_daily_horoscopes(date, model=self.openai_model, signs=signs)
        
        print("\n" + "=" * 70)
        print("STEP 2/3: BUILDING VIDEO PROMPTS")
        print("=" * 70)
        print(f"🎨 Style: {style_tag}")
        print(f"🔧 Transformers: {len(self.transformers)}")
        
        planner = ScenePlanner(render, style_tag)
        scenes = [planner.build_scene(sign, text, template) for sign, text in scripts.items()]

        print(f"\n📝 Applying transformers and saving prompts...")
        for i, scene in enumerate(scenes, 1):
            for t in self.transformers:
                scene.prompt = t(scene.prompt, scene)
            (out_dir / "prompts" / f"{scene.sign}.txt").write_text(scene.prompt, encoding="utf-8")
            print(f"   [{i}/{len(scenes)}] {scene.sign} prompt saved")

        # TEST MODE: Output parameters and stop
        if test_mode:
            print("\n" + "=" * 70)
            print("TEST MODE: VEO API PARAMETERS (NOT SUBMITTING)")
            print("=" * 70)
            for i, scene in enumerate(scenes, 1):
                print(f"\n{'─' * 70}")
                print(f"VIDEO {i}/{len(scenes)}: {scene.sign}")
                print(f"{'─' * 70}")
                print(f"\n📋 Horoscope Text:")
                print(f"   {scene.script_text}")
                print(f"\n📝 Veo Prompt (saved to prompts/{scene.sign}.txt):")
                print(f"   {scene.prompt[:200]}..." if len(scene.prompt) > 200 else f"   {scene.prompt}")
                print(f"\n🎬 Veo API Parameters:")
                print(f"   Model: {self.veo.model_id}")
                print(f"   Aspect Ratio: {scene.render.aspect_ratio}")
                print(f"   Duration: {scene.render.seconds} seconds")
                print(f"   Resolution: {scene.render.resolution}")
                print(f"   Generate Audio: {scene.render.generate_audio}")
                print(f"   Compression: {scene.render.compression_quality}")
                print(f"   FPS: {scene.render.fps}")
                if scene.render.seed:
                    print(f"   Seed: {scene.render.seed}")
            
            print("\n" + "=" * 70)
            print("TEST MODE COMPLETE")
            print("=" * 70)
            print(f"\n✅ Generated {len(scenes)} horoscope(s) and prompt(s)")
            print(f"📁 Output directory: {out_dir}")
            print(f"📝 Prompts saved to: {out_dir / 'prompts'}")
            print(f"\n💡 To submit these to Veo API, run without --test-mode flag")
            print("=" * 70 + "\n")
            return []

        print("\n" + "=" * 70)
        print("STEP 3/3: VIDEO GENERATION (This may take a while...)")
        print("=" * 70)
        print(f"🎥 Generating {len(scenes)} videos")
        print(f"⏱️  Estimated time: ~{len(scenes) * 2}-{len(scenes) * 5} minutes\n")
        
        jobs = []
        start_time = dt.datetime.now()
        
        for i, scene in enumerate(scenes, 1):
            print(f"\n{'─' * 70}")
            print(f"VIDEO {i}/{len(scenes)}: {scene.sign}")
            print(f"{'─' * 70}")
            
            job = self.veo.submit(scene)
            job = self.veo.poll_until_done(job, out_dir)
            jobs.append(job)
            
            completed = sum(1 for j in jobs if j.status == "done")
            failed = sum(1 for j in jobs if j.status == "failed")
            
            elapsed = (dt.datetime.now() - start_time).total_seconds() / 60
            print(f"\n📊 Progress: {i}/{len(scenes)} processed | ✓ {completed} done | ✗ {failed} failed | ⏱️  {elapsed:.1f} min elapsed")

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
        
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        
        total_time = (dt.datetime.now() - start_time).total_seconds() / 60
        completed = sum(1 for j in jobs if j.status == "done")
        failed = sum(1 for j in jobs if j.status == "failed")
        
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"\n📊 RESULTS:")
        print(f"   ✓ Completed: {completed}/{len(jobs)}")
        if failed > 0:
            print(f"   ✗ Failed: {failed}")
        print(f"   ⏱️  Total time: {total_time:.1f} minutes")
        print(f"   📁 Output: {out_dir}")
        print(f"   📄 Manifest: {manifest_path}")
        print(f"\n🎬 Videos saved to: {out_dir / 'renders'}")
        print(f"📝 Prompts saved to: {out_dir / 'prompts'}")
        
        if failed > 0:
            print(f"\n⚠️  WARNING: {failed} video(s) failed to generate")
            failed_signs = [j.scene.sign for j in jobs if j.status == "failed"]
            print(f"   Failed signs: {', '.join(failed_signs)}")
        
        print("\n" + "=" * 70 + "\n")
        
        return jobs

# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Veo Horoscope Video Generation")
    p.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--out", type=str, default="./out", help="Output directory")
    
    # Video parameters - read defaults from .env if available
    p.add_argument("--aspect", type=str, 
                   default=os.getenv("VIDEO_ASPECT_RATIO", "9:16"),
                   choices=["9:16", "16:9", "1:1"], 
                   help="Aspect ratio")
    p.add_argument("--duration", type=int, 
                   default=int(os.getenv("VIDEO_DURATION", "8")),
                   help="Video duration in seconds (max 8)")
    p.add_argument("--resolution", type=str, 
                   default=os.getenv("VIDEO_RESOLUTION", "720p"),
                   choices=["720p", "1080p"],
                   help="Video resolution")
    p.add_argument("--fps", type=int, 
                   default=int(os.getenv("VIDEO_FPS", "24")),
                   help="Frames per second")
    p.add_argument("--no-audio", action="store_true", 
                   default=os.getenv("VIDEO_GENERATE_AUDIO", "true").lower() == "false",
                   help="Disable audio generation (Veo 3+ only)")
    p.add_argument("--compression", type=str, 
                   default=os.getenv("VIDEO_COMPRESSION", "optimized"),
                   choices=["optimized", "high"],
                   help="Compression quality")
    p.add_argument("--seed", type=int, 
                   default=int(os.getenv("VIDEO_SEED")) if os.getenv("VIDEO_SEED") else None,
                   help="Random seed for reproducibility")
    
    # Model selection
    p.add_argument("--veo-model", type=str, 
                   default=os.getenv("VEO_MODEL_ID", "veo-3.1-generate-001"),
                   dest="veo_model",
                   choices=list(VEO_MODELS.keys()),
                   help=f"Veo video generation model (default: from VEO_MODEL_ID env or veo-3.1-generate-001)")
    p.add_argument("--openai-model", type=str, default=None,
                   dest="openai_model",
                   choices=list(OPENAI_MODELS.keys()) if OPENAI_MODELS else None,
                   help=f"OpenAI model for horoscope generation (default: gpt-4o-mini)")
    p.add_argument("--list-models", action="store_true",
                   help="List available models and exit")
    
    # Style parameters
    p.add_argument("--style", type=str, default="whimsical_astrology",
                   help="Style tag for the videos")
    p.add_argument("--cyberpunk", action="store_true",
                   help="Add cyberpunk style enhancements")
    
    # Testing parameters
    p.add_argument("--signs", type=str, nargs="+", default=None,
                   help="Generate only specific signs (e.g., --signs Aries Leo Pisces)")
    p.add_argument("--test-mode", action="store_true",
                   help="Test mode: generate horoscope and Veo prompt but don't submit to API")
    
    return p.parse_args()

def build_transformers(args: argparse.Namespace) -> List[PromptTransformer]:
    transformers: List[PromptTransformer] = [IdentityTransformer()]
    if args.cyberpunk:
        transformers.append(CyberpunkPunchup())
    return transformers

def main() -> None:
    args = parse_args()
    
    # List models if requested
    if args.list_models:
        print("Available Veo models:")
        for model_id, model_name in VEO_MODELS.items():
            print(f"  {model_id:<35} - {model_name}")
        print()
        print("Available OpenAI models:")
        for model_id, model_name in OPENAI_MODELS.items():
            print(f"  {model_id:<20} - {model_name}")
        return
    
    date = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else dt.date.today()

    render = RenderSpec(
        aspect_ratio=args.aspect,
        seconds=args.duration,
        fps=args.fps,
        resolution=args.resolution,
        generate_audio=not args.no_audio,
        compression_quality=args.compression,
        seed=args.seed
    )
    out_dir = Path(args.out)

    transformers = build_transformers(args)
    
    # Create VeoClient with specified model
    veo_client = VeoClient(model_id=args.veo_model)
    pipeline = HoroscopeVeoPipeline(veo=veo_client, transformers=transformers, openai_model=args.openai_model)

    print("\n" + "=" * 70)
    print("AI VIDEO AGENT - HOROSCOPE VIDEO GENERATION")
    print("=" * 70)
    print(f"\n🚀 CONFIGURATION:")
    print(f"   📅 Date: {date.strftime('%B %d, %Y')}")
    print(f"   🎥 Veo Model: {VEO_MODELS.get(args.veo_model, args.veo_model)}")
    if args.openai_model:
        print(f"   ✍️  OpenAI Model: {OPENAI_MODELS.get(args.openai_model, args.openai_model)}")
    else:
        # Get the actual default from horoscope_writer module
        actual_model = os.getenv('OPENAI_MODEL', 'gpt-5-nano')
        model_desc = OPENAI_MODELS.get(actual_model, actual_model)
        print(f"   ✍️  OpenAI Model: {model_desc} (default)")
    print(f"   📐 Aspect ratio: {args.aspect}")
    print(f"   ⏱️  Duration: {args.duration}s")
    print(f"   🎨 Resolution: {args.resolution}")
    print(f"   🔊 Audio: {'Yes' if not args.no_audio else 'No'}")
    print(f"   🎨 Style: {args.style}")
    if args.cyberpunk:
        print(f"   🌆 Cyberpunk mode: Enabled")
    if args.signs:
        print(f"   🎯 Testing mode: Generating only {', '.join(args.signs)}")
    if args.test_mode:
        print(f"   🧪 Test mode: Will NOT submit to Veo API")

    jobs = pipeline.run(date=date, out_dir=out_dir, render=render, style_tag=args.style, signs=args.signs, test_mode=args.test_mode)


if __name__ == "__main__":
    main()
