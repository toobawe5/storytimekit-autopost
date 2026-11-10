"""Posting to each platform through its own free official API.

Every function returns {"ok": bool, "id": str|None, "url": str|None, "error": str|None}
and never raises, so one platform failing doesn't stop the others.
"""
import os
import time
from pathlib import Path

import requests

from common import env, log

GRAPH = "https://graph.facebook.com"
TIMEOUT = 120


def _result(ok, id=None, url=None, error=None):
    return {"ok": ok, "id": id, "url": url, "error": error}


def _check(resp, what):
    if resp.status_code >= 400:
        raise RuntimeError(f"{what} failed ({resp.status_code}): {resp.text[:600]}")
    try:
        return resp.json()
    except ValueError:
        return {}


def _graph_version():
    return env("GRAPH_VERSION", "v23.0")


# ---------------------------------------------------------------- Instagram

def post_instagram(video: Path, caption: str):
    token, ig_id = env("META_PAGE_TOKEN"), env("IG_USER_ID")
    if not token or not ig_id:
        return _result(False, error="Missing META_PAGE_TOKEN or IG_USER_ID secret")
    v = _graph_version()
    try:
        container = _check(requests.post(
            f"{GRAPH}/{v}/{ig_id}/media",
            data={"media_type": "REELS", "upload_type": "resumable", "caption": caption,
                  "share_to_feed": "true", "thumb_offset": "1000", "access_token": token},
            timeout=TIMEOUT), "Instagram: create container")
        cid, upload_uri = container["id"], container["uri"]
        size = os.path.getsize(video)
        with open(video, "rb") as f:
            _check(requests.post(upload_uri, data=f, timeout=600, headers={
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}),
                "Instagram: upload video")
        # wait for Instagram to process the video
        for _ in range(60):
            status = _check(requests.get(f"{GRAPH}/{v}/{cid}", params={
                "fields": "status_code,status", "access_token": token}, timeout=TIMEOUT),
                "Instagram: check status")
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram processing {code}: {status.get('status')}")
            time.sleep(10)
        else:
            raise RuntimeError("Instagram took more than 10 minutes to process the video")
        published = _check(requests.post(f"{GRAPH}/{v}/{ig_id}/media_publish", data={
            "creation_id": cid, "access_token": token}, timeout=TIMEOUT), "Instagram: publish")
        media_id = published.get("id")
        link = None
        try:
            link = requests.get(f"{GRAPH}/{v}/{media_id}", params={
                "fields": "permalink", "access_token": token}, timeout=TIMEOUT).json().get("permalink")
        except Exception:
            pass
        return _result(True, id=media_id, url=link)
    except Exception as e:
        return _result(False, error=str(e))


# ---------------------------------------------------------------- Facebook Page Reels

def post_facebook(video: Path, description: str):
    token, page_id = env("META_PAGE_TOKEN"), env("META_PAGE_ID")
    if not token or not page_id:
        return _result(False, error="Missing META_PAGE_TOKEN or META_PAGE_ID secret")
    v = _graph_version()
    try:
        start = _check(requests.post(f"{GRAPH}/{v}/{page_id}/video_reels", data={
            "upload_phase": "start", "access_token": token}, timeout=TIMEOUT), "Facebook: start upload")
        video_id = start["video_id"]
        upload_url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{v}/{video_id}"
        size = os.path.getsize(video)
        with open(video, "rb") as f:
            _check(requests.post(upload_url, data=f, timeout=600, headers={
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}),
                "Facebook: upload video")
        _check(requests.post(f"{GRAPH}/{v}/{page_id}/video_reels", data={
            "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
            "description": description, "access_token": token}, timeout=TIMEOUT), "Facebook: publish")
        return _result(True, id=video_id, url=f"https://www.facebook.com/reel/{video_id}")
    except Exception as e:
        return _result(False, error=str(e))


# ---------------------------------------------------------------- YouTube Shorts

def _google_access_token():
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=TIMEOUT)
    return _check(resp, "YouTube: refresh login")["access_token"]


def post_youtube(video: Path, thumbnail: Path, title: str, description: str, tags):
    if not (env("YT_CLIENT_ID") and env("YT_CLIENT_SECRET") and env("YT_REFRESH_TOKEN")):
        return _result(False, error="Missing YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN secret")
    try:
        token = _google_access_token()
        size = os.path.getsize(video)
        meta = {
            "snippet": {"title": title[:100], "description": description[:4900],
                        "tags": list(tags or [])[:15], "categoryId": "26"},  # 26 = Howto & Style
            # This content is FOR PARENTS, not made for kids.
            "status": {"privacyStatus": env("YT_PRIVACY", "public"), "selfDeclaredMadeForKids": False},
        }
        init = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            json=meta, timeout=TIMEOUT, headers={
                "Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size)})
        _check(init, "YouTube: start upload")
        location = init.headers["Location"]
        with open(video, "rb") as f:
            done = _check(requests.put(location, data=f, timeout=900, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "video/mp4"}), "YouTube: upload video")
        vid = done["id"]
        if thumbnail and Path(thumbnail).exists():
            with open(thumbnail, "rb") as f:
                t = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                                  data=f, timeout=TIMEOUT, headers={
                                      "Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
            if t.status_code >= 400:
                log(f"  (YouTube thumbnail skipped: {t.status_code} — verify your channel by phone to allow custom thumbnails)")
        return _result(True, id=vid, url=f"https://youtube.com/shorts/{vid}")
    except Exception as e:
        return _result(False, error=str(e))


# ---------------------------------------------------------------- Pinterest

def _pinterest_access_token():
    resp = requests.post("https://api.pinterest.com/v5/oauth/token",
                         auth=(env("PINTEREST_APP_ID"), env("PINTEREST_APP_SECRET")),
                         data={"grant_type": "refresh_token", "refresh_token": env("PINTEREST_REFRESH_TOKEN")},
                         timeout=TIMEOUT)
    return _check(resp, "Pinterest: refresh login")["access_token"]


def post_pinterest(video: Path, board_id: str, title: str, description: str, link: str):
    if not (env("PINTEREST_APP_ID") and env("PINTEREST_APP_SECRET") and env("PINTEREST_REFRESH_TOKEN")):
        return _result(False, error="Missing PINTEREST_APP_ID / PINTEREST_APP_SECRET / PINTEREST_REFRESH_TOKEN secret")
    if not board_id:
        return _result(False, error="No Pinterest board id for this product (set pinterest_board_id in products.json or PINTEREST_DEFAULT_BOARD_ID)")
    try:
        token = _pinterest_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        reg = _check(requests.post("https://api.pinterest.com/v5/media", json={"media_type": "video"},
                                   headers=headers, timeout=TIMEOUT), "Pinterest: register upload")
        with open(video, "rb") as f:
            up = requests.post(reg["upload_url"], data=reg["upload_parameters"],
                               files={"file": ("video.mp4", f, "video/mp4")}, timeout=600)
        if up.status_code >= 300:
            raise RuntimeError(f"Pinterest: upload video failed ({up.status_code}): {up.text[:400]}")
        media_id = reg["media_id"]
        for _ in range(60):
            st = _check(requests.get(f"https://api.pinterest.com/v5/media/{media_id}", headers=headers,
                                     timeout=TIMEOUT), "Pinterest: check status").get("status")
            if st == "succeeded":
                break
            if st == "failed":
                raise RuntimeError("Pinterest could not process the video")
            time.sleep(10)
        else:
            raise RuntimeError("Pinterest took more than 10 minutes to process the video")
        pin = _check(requests.post("https://api.pinterest.com/v5/pins", headers=headers, timeout=TIMEOUT, json={
            "board_id": board_id, "title": title[:100], "description": description[:800], "link": link,
            "media_source": {"source_type": "video_id", "media_id": media_id, "cover_image_key_frame_time": 1},
        }), "Pinterest: create pin")
        return _result(True, id=pin.get("id"), url=f"https://www.pinterest.com/pin/{pin.get('id')}/")
    except Exception as e:
        return _result(False, error=str(e))
