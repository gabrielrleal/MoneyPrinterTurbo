import os
import random
import threading
from typing import List
from urllib.parse import urlencode

import requests
from loguru import logger
from moviepy import (
    AudioClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
)
from moviepy.video.io.VideoFileClip import VideoFileClip

from app.config import config
from app.models.schema import MaterialInfo, VideoAspect, VideoConcatMode
from app.utils import utils

# Thread-safe counter for API key rotation
_api_key_counter = 0
_api_key_lock = threading.Lock()


def _get_tls_verify() -> bool:
    # 默认开启 TLS 证书校验，防止素材搜索和下载过程被中间人篡改。
    # 仅在企业代理、自签证书等明确需要的场景下，允许用户通过
    # `config.toml` 显式设置 `tls_verify = false` 临时关闭。
    tls_verify = config.app.get("tls_verify", True)
    if isinstance(tls_verify, str):
        tls_verify = tls_verify.strip().lower() not in ("0", "false", "no", "off")

    if not tls_verify:
        logger.warning(
            "TLS certificate verification is disabled by config.app.tls_verify=false. "
            "Only use this in trusted proxy environments."
        )

    return bool(tls_verify)


def get_api_key(cfg_key: str):
    api_keys = config.app.get(cfg_key)
    if not api_keys:
        raise ValueError(
            f"\n\n##### {cfg_key} is not set #####\n\nPlease set it in the config.toml file: {config.config_file}\n\n"
            f"{utils.to_json(config.app)}"
        )

    # if only one key is provided, return it
    if isinstance(api_keys, str):
        return api_keys

    global _api_key_counter
    with _api_key_lock:
        _api_key_counter += 1
        return api_keys[_api_key_counter % len(api_keys)]


def search_videos_pexels(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)
    video_orientation = aspect.name
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("pexels_api_keys")
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/videos/search?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
        response = r.json()
        video_items = []
        if "videos" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["videos"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["video_files"]
            # loop through each url to determine the best quality
            for video in video_files:
                w = int(video["width"])
                h = int(video["height"])
                if w == video_width and h == video_height:
                    item = MaterialInfo()
                    item.provider = "pexels"
                    item.url = video["link"]
                    item.duration = duration
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def search_videos_pixabay(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)

    video_width, video_height = aspect.to_resolution()

    api_key = get_api_key("pixabay_api_keys")
    # Build URL
    params = {
        "q": search_term,
        "video_type": "all",  # Accepted values: "all", "film", "animation"
        "per_page": 50,
        "key": api_key,
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url, proxies=config.proxy, verify=_get_tls_verify(), timeout=(30, 60)
        )
        response = r.json()
        video_items = []
        if "hits" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["hits"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["videos"]
            # loop through each url to determine the best quality
            for video_type in video_files:
                video = video_files[video_type]
                w = int(video["width"])
                # h = int(video["height"])
                if w >= video_width:
                    item = MaterialInfo()
                    item.provider = "pixabay"
                    item.url = video["url"]
                    item.duration = duration
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def save_video(video_url: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    url_without_query = video_url.split("?")[0]
    url_hash = utils.md5(url_without_query)
    video_id = f"vid-{url_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    # if video already exists, return the path
    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"video already exists: {video_path}")
        return video_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # if video does not exist, download it
    with open(video_path, "wb") as f:
        f.write(
            requests.get(
                video_url,
                headers=headers,
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=(60, 240),
            ).content
        )

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        clip = None
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            if duration > 0 and fps > 0:
                return video_path
        except Exception as e:
            logger.warning(f"invalid video file: {video_path} => {str(e)}")
            try:
                os.remove(video_path)
            except Exception as remove_error:
                logger.warning(
                    f"failed to remove invalid video file: {video_path}, error: {str(remove_error)}"
                )
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as close_error:
                    logger.warning(
                        f"failed to close video clip: {video_path}, error: {str(close_error)}"
                    )
    return ""


def download_wikimedia_art(
    search_term: str,
    save_dir: str = "",
    clip_duration: int = 4,
    video_aspect: VideoAspect = VideoAspect.portrait,
    layout: str = "sequential",
) -> str | None:
    try:
        title = search_term.removeprefix("wiki:").strip()
        if not title:
            logger.warning(f"empty wiki search term: {search_term!r}")
            return None

        logger.info(f"searching Wikimedia for: {title!r}")

        params = {
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "pithumbsize": 1920,
            "format": "json",
        }
        wiki_headers = {
            "User-Agent": "MoneyPrinterTurbo/1.0 (https://github.com/harry0703/MoneyPrinterTurbo)"
        }
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers=wiki_headers,
            proxies=config.proxy,
            timeout=(15, 30),
        )
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            logger.warning(f"no pages found for wiki title: {title!r}")
            return None

        page = next(iter(pages.values()))
        if "missing" in page:
            logger.warning(f"wiki page does not exist: {title!r}")
            return None

        thumbnail = page.get("thumbnail")
        if not thumbnail or "source" not in thumbnail:
            logger.warning(f"wiki page has no image: {title!r}")
            return None

        image_url = thumbnail["source"]
        logger.info(f"found wiki image: {image_url}")

        if not save_dir:
            save_dir = utils.storage_dir("cache_videos")

        os.makedirs(save_dir, exist_ok=True)

        url_hash = utils.md5(image_url)
        image_filename = f"wiki-{url_hash}.jpg"
        image_path = os.path.join(save_dir, image_filename)
        video_path = os.path.join(save_dir, f"wiki-{url_hash}.mp4")

        # Overlay: retorna o .jpg diretamente, sem converter para vídeo
        if layout == "overlay":
            if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                logger.info(f"wiki overlay image ready: {image_path}")
                return image_path

        # Sequential: reutilizar .mp4 em cache se existir
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            logger.info(f"wiki video already exists: {video_path}")
            return video_path

        img_headers = {
            "User-Agent": "MoneyPrinterTurbo/1.0 (https://github.com/harry0703/MoneyPrinterTurbo)"
        }
        img_resp = requests.get(
            image_url,
            headers=img_headers,
            proxies=config.proxy,
            timeout=(30, 60),
        )
        img_resp.raise_for_status()

        with open(image_path, "wb") as f:
            f.write(img_resp.content)

        if not os.path.getsize(image_path):
            logger.warning(f"downloaded wiki image is empty: {image_path}")
            return None

        # Overlay: após baixar a imagem, retorna o .jpg
        if layout == "overlay":
            logger.info(f"wiki overlay image downloaded: {image_path}")
            return image_path

        aspect = VideoAspect(video_aspect)
        target_w, target_h = aspect.to_resolution()

        clip = ImageClip(image_path)

        img_w, img_h = clip.size
        img_ratio = img_w / img_h
        target_ratio = target_w / target_h

        if img_ratio > target_ratio:
            scale_factor = target_w / img_w
        else:
            scale_factor = target_h / img_h

        new_w = int(img_w * scale_factor)
        new_h = int(img_h * scale_factor)

        clip = (
            clip
            .resized(new_size=(new_w, new_h))
            .with_position("center")
            .with_duration(clip_duration)
        )

        background = (
            ColorClip(size=(target_w, target_h), color=(0, 0, 0))
            .with_duration(clip_duration)
        )

        zoom_factor = 1.10
        zoom_clip = clip.resized(
            lambda t: 1 + (zoom_factor - 1) * (t / clip.duration)
        )

        final_clip = CompositeVideoClip([background, zoom_clip])

        silent_audio = AudioClip(
            lambda t: 0,
            duration=clip_duration,
            fps=44100,
        )
        final_clip = final_clip.with_audio(silent_audio)

        final_clip.write_videofile(
            video_path,
            fps=30,
            logger=None,
        )

        final_clip.close()
        clip.close()

        logger.success(f"wiki artwork video created: {video_path}")
        return video_path

    except Exception:
        logger.warning(
            f"failed to process wiki artwork for {search_term!r}",
            exc_info=True,
        )
        return None


def download_videos(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> tuple[list[str], str | None]:
    valid_video_items = []
    valid_video_urls = []
    found_duration = 0.0
    search_videos = search_videos_pexels
    if source == "pixabay":
        search_videos = search_videos_pixabay

    for search_term in search_terms:
        if search_term.lower().startswith("wiki:"):
            continue

        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        for item in video_items:
            if item.url not in valid_video_urls:
                valid_video_items.append(item)
                valid_video_urls.append(item.url)
                found_duration += item.duration

    logger.info(
        f"found total videos: {len(valid_video_items)}, required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )
    video_paths = []
    wiki_overlay_image = None

    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""

    concat_mode_value = getattr(video_contact_mode, "value", video_contact_mode)
    if concat_mode_value == VideoConcatMode.random.value:
        random.shuffle(valid_video_items)

    total_duration = 0.0
    preset_name = str(config.app.get("preset_name", "sequential")).strip().lower()

    for search_term in search_terms:
        if not search_term.lower().startswith("wiki:"):
            continue
        logger.info(f"searching wikimedia art for '{search_term}'")
        wiki_video = download_wikimedia_art(
            search_term=search_term,
            save_dir=material_directory or utils.storage_dir("cache_videos"),
            clip_duration=max_clip_duration,
            video_aspect=video_aspect,
            layout=preset_name,
        )
        if wiki_video:
            if preset_name != "sequential":
                wiki_overlay_image = wiki_video
                logger.info(f"wiki overlay image saved: {wiki_video}")
            else:
                video_paths.append(wiki_video)
                total_duration += max_clip_duration
                logger.info(f"wiki video saved: {wiki_video}")
        else:
            logger.warning(f"failed to get wiki artwork for '{search_term}'")

    for item in valid_video_items:
        if total_duration > audio_duration:
            logger.info(
                f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
            )
            break
        try:
            logger.info(f"downloading video: {item.url}")
            saved_video_path = save_video(
                video_url=item.url, save_dir=material_directory
            )
            if saved_video_path:
                logger.info(f"video saved: {saved_video_path}")
                video_paths.append(saved_video_path)
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
        except Exception as e:
            logger.error(f"failed to download video: {utils.to_json(item)} => {str(e)}")
    logger.success(f"downloaded {len(video_paths)} videos")
    return video_paths, wiki_overlay_image


if __name__ == "__main__":
    download_videos(
        "test123", ["Money Exchange Medium"], audio_duration=100, source="pixabay"
    )
