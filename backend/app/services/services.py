import os
import tempfile
import yt_dlp
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from app.core.models import VideoData
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _extract_yt_transcript(video_id: str) -> str:
    """
    Fetches the FULL YouTube transcript using the only method 
    supported by your specific package version.
    """
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id)
        
        full_text = " ".join(t.text for t in transcript_list)
        
        print(f"Successfully extracted {len(full_text)} characters from YouTube transcript.")
        return full_text
        
    except Exception as e:
        print(f"Transcript failed for YT {video_id}: {e}")
        return ""

def _transcribe_audio_with_groq(audio_path: str) -> str:
    print(f"Sending audio to Groq for transcription: {audio_path}")
    with open(audio_path, "rb") as audio_file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_file.read()),
            model="whisper-large-v3",
            response_format="text"
        )
    return str(transcription)

def extract_video_info(url: str) -> VideoData:
    is_instagram = "instagram.com" in url
    platform = "instagram" if is_instagram else "youtube"
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    COOKIE_PATH = os.path.join(BASE_DIR, "cookies.txt")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiefile': COOKIE_PATH,
    }
    
    temp_audio_path = None
    
    if is_instagram:
        temp_dir = tempfile.gettempdir()
        temp_audio_path = os.path.join(temp_dir, "%(id)s.%(ext)s")
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': temp_audio_path,
            'postprocessors': [{
                'key': "FFmpegExtractAudio",
                'preferredcodec': "mp3",
                'preferredquality': "128",
            }]
        })
    else:
        ydl_opts.update({
            'skip_download': True
        })
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=is_instagram)
      
    transcript_text = ""
    if is_instagram:
        actual_audio_path = temp_audio_path.replace("%(id)s", info['id']).replace("%(ext)s", "mp3")
        if os.path.exists(actual_audio_path):
            transcript_text = _transcribe_audio_with_groq(actual_audio_path)
            os.remove(actual_audio_path)
    else:
        transcript_text = _extract_yt_transcript(info['id'])
        
    return VideoData(
        video_id=info.get('id'),
        platform=platform,
        title=info.get('title') or info.get('description', '')[:50],
        creator=info.get('uploader') or info.get('channel'),
        followers=info.get('channel_follower_count') or info.get('uploader_subscriber_count') or 0,
        views=info.get('view_count') or 0,
        likes=info.get('like_count') or 0,
        comments=info.get('comment_count') or 0,
        duration=info.get('duration') or 0,
        upload_date=info.get('upload_date') or "",
        transcript=transcript_text
    )