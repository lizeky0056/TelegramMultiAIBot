import os
import uuid
import yt_dlp

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Common headers to bypass HTTP 403 Forbidden blocks
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Sec-Fetch-Mode': 'navigate'
}

EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'web_embedded']
    }
}

def download_media(url, download_type="mp4"):
    """
    Downloads media from URL.
    download_type: 'mp4' (video) or 'mp3' (audio)
    Returns: (filepath, title, error_message)
    """
    file_id = str(uuid.uuid4())[:8]
    
    # Common base options to avoid blocks
    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'http_headers': HEADERS,
        'extractor_args': EXTRACTOR_ARGS,
    }
    
    if download_type == "mp3":
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'{file_id}_%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        # MP4: attempt to get best quality that fits in Telegram 50MB limit
        ydl_opts = {
            **base_opts,
            'format': 'best[filesize<50M]/bestvideo[filesize<40M]+bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'{file_id}_%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'media')
            
            # Search for the file starting with our unique file_id
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(file_id):
                    filepath = os.path.join(DOWNLOAD_DIR, f)
                    
                    # Verify file size limit for MP4
                    if download_type == "mp4":
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        if size_mb > 49.5:
                            # Try re-downloading worst quality if best exceeded 50MB
                            try:
                                os.remove(filepath)
                            except Exception:
                                pass
                                
                            worst_opts = {
                                **base_opts,
                                'format': 'worst/worstvideo+worstaudio',
                                'outtmpl': os.path.join(DOWNLOAD_DIR, f'{file_id}_%(title)s.%(ext)s'),
                                'merge_output_format': 'mp4',
                            }
                            with yt_dlp.YoutubeDL(worst_opts) as ydl_worst:
                                info_worst = ydl_worst.extract_info(url, download=True)
                                title = info_worst.get('title', 'media')
                                
                            for f2 in os.listdir(DOWNLOAD_DIR):
                                if f2.startswith(file_id):
                                    filepath = os.path.join(DOWNLOAD_DIR, f2)
                                    break
                                    
                    return filepath, title, None
            
            return None, None, "No se pudo localizar el archivo descargado."
            
    except Exception as e:
        return None, None, str(e)
