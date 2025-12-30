# AI Video Agent

An automated horoscope video generation pipeline using OpenAI for script generation and Google Vertex AI Veo for AI video creation.

## Features

- 🌟 **AI-Powered Script Writing**: Uses OpenAI GPT-4o-mini to generate witty daily horoscopes for all 12 zodiac signs
- 🎬 **AI Video Generation**: Integrates with Google Vertex AI Veo (2.0, 3.0, 3.1 variants) for cinematic video creation
- 📱 **Multiple Formats**: Supports 9:16 (TikTok/Reels), 16:9 (YouTube), and 1:1 (Instagram) aspect ratios
- 🎨 **Customizable Styles**: Whimsical astrology studio aesthetic with optional cyberpunk enhancements
- ⚙️ **Flexible Parameters**: Control resolution, duration, audio generation, and more

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables** in `.env`:
   ```bash
   # Required: OpenAI API key for horoscope generation
   OPENAI_API_KEY=your_openai_api_key
   
   # Required: Google Cloud credentials for Veo
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_PROJECT_ID=your_project_id
   
   # Optional: Customize region and model
   GOOGLE_REGION=us-central1
   VEO_MODEL_ID=veo-3.1-generate-001
   ```

## Usage

### Generate Videos for Today

```bash
python src/render/veo_horoscope_pipeline.py
```

### Custom Options

```bash
# Specify date and models
python src/render/veo_horoscope_pipeline.py --date 2025-12-25 --veo-model veo-3.1-fast-generate-001 --openai-model gpt-5-mini

# Change aspect ratio and resolution
python src/render/veo_horoscope_pipeline.py --aspect 16:9 --resolution 1080p

# Use highest quality OpenAI model for best horoscopes
python src/render/veo_horoscope_pipeline.py --openai-model gpt-5.1

# Use cheapest OpenAI model for testing
python src/render/veo_horoscope_pipeline.py --openai-model gpt-5-nano

# Enable cyberpunk style
python src/render/veo_horoscope_pipeline.py --cyberpunk

# Disable audio (Veo 3+ only)
python src/render/veo_horoscope_pipeline.py --no-audio

# Custom output directory
python src/render/veo_horoscope_pipeline.py --out ./output/2025-12-25
```

### List Available Models

```bash
python src/render/veo_horoscope_pipeline.py --list-models
```

## Available Models

### Veo Video Models

- `veo-2.0-generate-001` - Veo 2 (Standard)
- `veo-2.0-generate-exp` - Veo 2 (Experimental)
- `veo-2.0-generate-preview` - Veo 2 (Preview)
- `veo-3.0-generate-001` - Veo 3 (Standard)
- `veo-3.0-fast-generate-001` - Veo 3 (Fast)
- `veo-3.1-generate-001` - Veo 3.1 (Standard) ⭐ Default
- `veo-3.1-fast-generate-001` - Veo 3.1 (Fast)
- `veo-3.1-generate-preview` - Veo 3.1 (Preview)
- `veo-3.1-fast-generate-preview` - Veo 3.1 Fast (Preview)

### OpenAI Models (for Horoscope Generation)

| Model | Cost per 1M tokens | Quality Score | Best For |
|-------|-------------------|---------------|----------|
| `gpt-5.1` | $1.25 | 98 ⭐ | Highest quality content |
| `gpt-5` | $1.24 | 95 | Premium quality |
| `gpt-4.1` | $2.00 | 92 | High quality |
| `gpt-4o` | $2.50 | 92 | High quality |
| `gpt-5-mini` | $0.25 | 85 | Good balance |
| `gpt-4.1-mini` | $0.40 | 83 | Budget-friendly |
| `gpt-4.1-nano` | $0.10 | 80 | Very cheap |
| `gpt-4o-mini` | - | - | Legacy (default) |
| `gpt-5-nano` | $0.05 | 75 | Testing/development |

## Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--date` | today | Date in YYYY-MM-DD format |
| `--out` | `./out` | Output directory |
| `--aspect` | `9:16` | Aspect ratio (9:16, 16:9, 1:1) |
| `--duration` | `8` | Video duration in seconds (max 8) |
| `--resolution` | `720p` | Video resolution (720p, 1080p) |
| `--fps` | `24` | Frames per second |
| `--no-audio` | false | Disable audio generation |
| `--compression` | `optimized` | Compression quality (optimized, high) |
| `--seed` | random | Random seed for reproducibility |
| `--veo-model` | `veo-3.1-generate-001` | Veo video model to use |
| `--openai-model` | `gpt-4o-mini` | OpenAI model for horoscopes |
| `--style` | `whimsical_astrology` | Style tag |
| `--cyberpunk` | false | Add cyberpunk enhancements |
| `--list-models` | - | List all available models |

## Output Structure

```
out/
├── manifest.json          # Job metadata and status
├── prompts/              # Video generation prompts
│   ├── Aries.txt
│   ├── Taurus.txt
│   └── ...
└── renders/              # Generated videos
    ├── aries.mp4
    ├── taurus.mp4
    └── ...
```

## How It Works

1. **Horoscope Generation**: Uses OpenAI to generate 2-3 sentence horoscopes for each sign
2. **Prompt Engineering**: Transforms horoscopes into cinematic video prompts with detailed aesthetic descriptions
3. **Video Submission**: Submits prompts to Google Vertex AI Veo via `predictLongRunning` endpoint
4. **Polling**: Monitors operation status using `fetchPredictOperation` endpoint
5. **Download**: Retrieves generated videos from GCS or base64 encoding

## API Reference

### VeoClient

- `submit(scene)` - Submit video generation request
- `poll_until_done(job, out_dir)` - Poll for completion and download video

### RenderSpec

Configure video generation parameters:
- `aspect_ratio` - Video aspect ratio
- `seconds` - Duration (max 8 seconds)
- `resolution` - Output resolution
- `generate_audio` - Enable audio (Veo 3+ only)
- `compression_quality` - Compression setting
- `seed` - Random seed for reproducibility

## Troubleshooting

**"GOOGLE_API_KEY missing"**: Add your Google API key to `.env`

**"GOOGLE_PROJECT_ID missing"**: Add your Google Cloud project ID to `.env`

**Quota errors**: Check your Google Cloud quota limits and consider using fast models or adding delays between requests

**Videos not downloading**: Check that your API key has appropriate permissions for the storage bucket
