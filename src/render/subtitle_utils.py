"""
Utility functions for adding captions to videos using ffmpeg.
Adapted from reference/utils.py for the AI Video Agent pipeline.
"""
import subprocess
import tempfile
import os
from typing import Optional


def format_ass_time(seconds: float) -> str:
    """
    Convert seconds to ASS timestamp format (H:MM:SS.cc).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string (e.g., "0:00:05.50")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def color_to_ass(color: str) -> str:
    """
    Convert common color names to ASS format (&HAABBGGRR).
    
    Args:
        color: Color name or hex code
        
    Returns:
        ASS format color code (BGR format without &H prefix)
    """
    color_map = {
        'white': 'FFFFFF',
        'black': '000000',
        'red': '0000FF',
        'green': '00FF00',
        'blue': 'FF0000',
        'yellow': '00FFFF',
        'cyan': 'FFFF00',
        'magenta': 'FF00FF',
    }
    
    color_lower = color.lower()
    if color_lower in color_map:
        hex_color = color_map[color_lower]
    elif color.startswith('#'):
        # Remove # and reverse RGB to BGR for ASS format
        hex_color = color[1:]
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            hex_color = f"{b}{g}{r}".upper()
    else:
        hex_color = 'FFFFFF'  # Default to white
    
    return hex_color


def create_ass_file(
    text: str,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    duration: Optional[float] = None,
    fontname: str = "Arial",
    fontsize: int = 48,
    fontcolor: str = "white",
    outline: int = 2,
    outlinecolor: str = "black",
    alignment: int = 2,
    margin_v: int = 50,
    video_height: int = 1080,
    output_path: Optional[str] = None,
    style: str = "scroll"
) -> str:
    """
    Create an ASS subtitle file with scrolling or static text.
    
    Args:
        text: The subtitle text to display
        start_time: When the subtitle should appear (in seconds)
        end_time: When the subtitle should disappear (in seconds)
        duration: Alternative to end_time - how long to show (in seconds)
        fontname: Name of the font
        fontsize: Font size in pixels (default 48 for 1080p)
        fontcolor: Primary color of the text
        outline: Width of the text outline
        outlinecolor: Color of the text outline
        alignment: Subtitle alignment (1-9, numpad style, 2=bottom center, 5=middle center)
        margin_v: Vertical margin from edge in pixels
        video_height: Height of the video in pixels (for scrolling calculation)
        output_path: Optional path for the ASS file. If None, creates a temp file.
        style: Animation style - "scroll" for bottom-to-top, "static" for centered/fixed
        
    Returns:
        Path to the ASS file
    """
    # Calculate end_time if not provided
    if end_time is None:
        if duration is not None:
            end_time = start_time + duration
        else:
            # Default: 10 seconds for scrolling
            end_time = start_time + 10.0
    
    # Convert colors to ASS format (without HTML escaping)
    primary_color = "&H00" + color_to_ass(fontcolor)
    outline_color = "&H00" + color_to_ass(outlinecolor)
    
    # Clean the text
    cleaned_text = text.replace('\r\n', '\\N').replace('\r', '\\N').replace('\n', '\\N')
    
    # Build animation based on style
    if style.lower() == "scroll":
        # Calculate scrolling animation for bottom-to-top scroll
        # Start position: at the bottom of the video
        start_y = video_height
        # End position: near the top of the video (leave some margin)
        end_y = 50
        # Center horizontally for the movement (960 is center of 1920 width)
        x_center = 960
        animation = f"{{\\move({x_center},{start_y},{x_center},{end_y})}}"
        # Use bottom-center alignment for scrolling
        text_alignment = 2
    else:  # static/centered
        # No animation, just static centered text
        animation = ""
        # Use middle-center alignment for static
        text_alignment = 5
    
    # Create ASS content
    ass_content = f"""[Script Info]
Title: Caption
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{primary_color},{outline_color},{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,{outline},0,{text_alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Default,,0,0,0,,{animation}{cleaned_text}
"""
    
    # Create ASS file
    if output_path:
        ass_path = output_path
        with open(ass_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(ass_content)
    else:
        # Create temporary ASS file
        fd, ass_path = tempfile.mkstemp(suffix=".ass", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(ass_content)
    
    return ass_path


def build_ass_filter(ass_path: str) -> str:
    """
    Creates a subtitles filter for FFmpeg using an ASS file.
    
    Args:
        ass_path: Path to the ASS subtitle file
        
    Returns:
        Complete FFmpeg subtitles filter string
    """
    # Escape backslashes in paths for Windows
    escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
    
    # Use the subtitles filter which works for both SRT and ASS files
    return f"subtitles='{escaped_ass}'"


def run_ffmpeg(
    input_path: str,
    output_path: str,
    filter_complex: str,
    crf: int = 18,
    preset: str = "medium"
) -> subprocess.CompletedProcess:
    """
    Uses FFmpeg to burn the caption into the video.
    
    Preserves audio stream and re-encodes video with libx264.
    
    Args:
        input_path: Path to input video file
        output_path: Path to output video file
        filter_complex: Complete FFmpeg filter string
        crf: Constant Rate Factor (0-51, lower is better quality)
        preset: Encoding preset (ultrafast to veryslow)
    
    Returns:
        CompletedProcess object with returncode, stdout, and stderr
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if it exists
        "-i", input_path,
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "copy",  # Copy audio stream without re-encoding (ignored if no audio)
        "-map", "0:v:0",  # Map video stream
        "-map", "0:a?",  # Map audio stream if it exists (? makes it optional)
        output_path
    ]
    
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return result


def add_caption_to_video(
    video_path: str,
    caption_text: str,
    output_path: str,
    duration: float = 8.0,
    resolution: str = "720p",
    fontsize: int = 36,
    fontcolor: str = "white",
    outline: int = 2,
    outlinecolor: str = "black",
    crf: int = 18,
    preset: str = "medium",
    style: str = "scroll"
) -> tuple[bool, str]:
    """
    Add a caption to a video file using ffmpeg.
    
    Args:
        video_path: Path to the input video file
        caption_text: Text to display as caption
        output_path: Path for the output video with caption
        duration: Duration of the video in seconds
        resolution: Video resolution (720p or 1080p)
        fontsize: Font size for the caption
        fontcolor: Color of the caption text
        outline: Width of text outline
        outlinecolor: Color of text outline
        crf: Quality setting (lower is better, 18 is high quality)
        preset: Encoding speed preset
        style: Caption style - "scroll" for scrolling animation, "static" for centered
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Determine video height based on resolution
        video_height = 1080 if resolution == "1080p" else 720
        
        # Create ASS subtitle file with animation style
        ass_path = create_ass_file(
            text=caption_text,
            start_time=0.0,
            duration=duration,
            fontname="Arial",
            fontsize=fontsize,
            fontcolor=fontcolor,
            outline=outline,
            outlinecolor=outlinecolor,
            alignment=2,  # Will be overridden by style setting
            margin_v=50,
            video_height=video_height,
            style=style
        )
        
        # Build ffmpeg filter
        subtitle_filter = build_ass_filter(ass_path)
        
        # Run ffmpeg to burn in captions
        result = run_ffmpeg(
            input_path=video_path,
            output_path=output_path,
            filter_complex=subtitle_filter,
            crf=crf,
            preset=preset
        )
        
        # Clean up ASS file
        try:
            os.unlink(ass_path)
        except:
            pass
        
        if result.returncode != 0:
            return False, f"FFmpeg failed: {result.stderr}"
        
        if not os.path.exists(output_path):
            return False, "Output file was not created"
        
        return True, "Caption added successfully"
        
    except Exception as e:
        return False, f"Error adding caption: {str(e)}"
