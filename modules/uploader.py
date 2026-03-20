"""
PaperBrief — Uploader Module
Handles headless uploads to YouTube, Facebook, and TikTok.
"""

import logging
import os
import config
from modules import history_db

logger = logging.getLogger(__name__)

def upload_to_all_platforms(video_path: str, title: str, arxiv_id: str):
    """
    Attempts to upload the video to all enabled platforms sequentially.
    """
    logger.info(f"📤 Preparing to upload: {arxiv_id}")
    
    if not os.path.exists(video_path):
        logger.error(f"❌ Video file not found: {video_path}")
        return

    # Check YouTube
    if config.UPLOAD_YOUTUBE_ENABLED:
        logger.info("▶ YouTube upload is ENABLED. Starting headless upload...")
        _upload_youtube(video_path, title, arxiv_id)
    else:
        logger.info("⏸ YouTube upload is DISABLED in config (UPLOAD_YOUTUBE=false). Skipping.")
        
    # Check Facebook
    if config.UPLOAD_FACEBOOK_ENABLED:
        logger.info("▶ Facebook upload is ENABLED.")
        # _upload_facebook(video_path, title, arxiv_id)
    else:
        logger.info("⏸ Facebook upload is DISABLED. Skipping.")
        
    # Check TikTok
    if config.UPLOAD_TIKTOK_ENABLED:
        logger.info("▶ TikTok upload is ENABLED.")
        # _upload_tiktok(video_path, title, arxiv_id)
    else:
        logger.info("⏸ TikTok upload is DISABLED. Skipping.")

def _upload_youtube(video_path: str, title: str, arxiv_id: str):
    import json
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    from google.auth.transport.requests import Request

    token_path = os.path.join(config.OUTPUT_DIR, ".youtube_token.json")
    creds = None

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path)
        except Exception as e:
            logger.warning(f"⚠ Failed to load YouTube credentials: {e}")

    # If no valid creds or expired, try refresh or re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("⏳ Refreshing expired YouTube token...")
                creds.refresh(Request())
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                logger.warning(f"⚠ Failed to refresh token: {e}")
                creds = None
        
        if not creds:
            logger.info("🔐 YouTube credentials missing or invalid. Triggering browser authentication...")
            try:
                import youtube_auth
                youtube_auth.main()
                
                # Check if it succeeded
                if os.path.exists(token_path):
                    creds = Credentials.from_authorized_user_file(token_path)
                else:
                    logger.error("❌ Authentication aborted or failed.")
                    return
            except Exception as e:
                logger.error(f"❌ Error during automatic authentication: {e}")
                return

    try:
        # Construct the YouTube service
        youtube = build("youtube", "v3", credentials=creds)

        # Build accurate metadata from script.json
        video_dir = os.path.dirname(video_path)
        script_path = os.path.join(video_dir, "script.json")
        desc = f"Discover more about arXiv paper {arxiv_id}."
        tags = ["shorts", "science", "ai", "research"]
        
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                s = json.load(f)
                
                # Use short title and make sure it has #shorts
                yt_title = s.get("title_short", title)
                if len(yt_title) > 85:
                    yt_title = yt_title[:82] + "..."
                if "#shorts" not in yt_title.lower():
                    yt_title += " #shorts"
                title = yt_title

                # Build description
                desc = f"{s.get('hook', '')}\n\n"
                desc += f"🔗 Source: https:*//arxiv.org/abs/{arxiv_id}\n\n"
                # Join hashtags if they exist
                hashts = s.get("hashtags", [])
                if hashts:
                    desc += " ".join(hashts)
                    tags = [t.replace("#", "") for t in hashts]
                    if "shorts" not in tags:
                        tags.append("shorts")

        logger.info(f"   Connecting to YouTube API for '{title}'...")

        body = {
            "snippet": {
                "title": title[:100],
                "description": desc,
                "tags": tags,
                "categoryId": "27"  # Education
            },
            "status": {
                "privacyStatus": "public",  # Automated push to public
                "madeForKids": False,
                "selfDeclaredMadeForKids": False
            }
        }

        # Initialize media upload
        media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True, mimetype="video/mp4")
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        # Execute resumable upload
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"   Uploading... {int(status.progress() * 100)}%")

        logger.info(f"   ✅ Uploaded to YouTube successfully! Video ID: {response.get('id')}")
        history_db.mark_uploaded(arxiv_id, "youtube")

    except Exception as e:
        logger.error(f"❌ YouTube upload failed: {e}")
