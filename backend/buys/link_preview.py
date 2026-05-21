"""상품 링크 페이지에서 Open Graph 미리보기 이미지를 추출한다.

공동구매 개설 시 item_url 이 있으면 해당 페이지의 대표 이미지(og:image 등)를
가져와 카드 썸네일로 사용한다. 실패해도 무시하고 빈 문자열을 반환한다.
"""
import re
from urllib.parse import urljoin, urlparse

_META_RE = re.compile(r"<meta[^>]+>", re.IGNORECASE)
_PROP_RE = re.compile(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)

# 우선순위 순서
_TARGET_PROPS = ("og:image", "og:image:url", "og:image:secure_url",
                 "twitter:image", "twitter:image:src")


def fetch_og_image(url, timeout=4):
    """URL 페이지의 대표 이미지 주소를 반환. 실패 시 빈 문자열."""
    try:
        import requests
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GongGoo/1.0)"},
        )
        if resp.status_code != 200:
            return ""
        html = resp.text[:300000]  # head 영역만 보면 충분

        found = {}
        for tag in _META_RE.findall(html):
            prop = _PROP_RE.search(tag)
            content = _CONTENT_RE.search(tag)
            if prop and content:
                key = prop.group(1).strip().lower()
                val = content.group(1).strip()
                if key in _TARGET_PROPS and val and key not in found:
                    found[key] = val

        for key in _TARGET_PROPS:
            if found.get(key):
                return _absolutize(found[key], url)
        return ""
    except Exception:
        return ""


def _absolutize(img_url, page_url):
    """상대경로/프로토콜 생략 이미지 주소를 절대 URL 로 변환."""
    if img_url.startswith("//"):
        return urlparse(page_url).scheme + ":" + img_url
    if img_url.startswith(("http://", "https://")):
        return img_url
    return urljoin(page_url, img_url)
