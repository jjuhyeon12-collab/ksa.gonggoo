"""상품 링크 페이지에서 Open Graph 미리보기 이미지를 추출한다.

공동구매 개설 시 item_url 이 있으면 해당 페이지의 대표 이미지(og:image 등)를
가져와 카드 썸네일로 사용한다. 실패해도 무시하고 빈 문자열을 반환한다.

[SSRF 방어]
서버가 사용자 입력 URL을 요청하므로, 내부망/사설 IP/루프백/클라우드 메타데이터
(예: 169.254.169.254) 주소로의 요청을 차단한다. 리다이렉트도 매 홉마다 검증한다.
"""
import re
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

_META_RE = re.compile(r"<meta[^>]+>", re.IGNORECASE)
_PROP_RE = re.compile(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)

# 우선순위 순서
_TARGET_PROPS = ("og:image", "og:image:url", "og:image:secure_url",
                 "twitter:image", "twitter:image:src")


def _is_public_url(url):
    """URL이 외부 공개 호스트(http/https)를 가리키는지 검사. SSRF 방어 핵심."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        # 호스트가 가리키는 모든 IP가 공인 IP여야 통과
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


def fetch_og_image(url, timeout=4):
    """URL 페이지의 대표 이미지 주소를 반환. 실패 시 빈 문자열."""
    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (compatible; GongGoo/1.0)"}
        current = url
        # 리다이렉트를 직접 따라가며 매 홉마다 공개 URL인지 검증
        for _ in range(5):
            if not _is_public_url(current):
                return ""
            resp = requests.get(
                current, timeout=timeout, allow_redirects=False, headers=headers
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location")
                if not loc:
                    return ""
                current = urljoin(current, loc)
                continue
            if resp.status_code != 200:
                return ""
            return _extract(resp.text[:300000], current)
        return ""
    except Exception:
        return ""


def _extract(html, page_url):
    """HTML 의 meta 태그에서 대표 이미지 URL 추출."""
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
            img = _absolutize(found[key], page_url)
            # http/https 이미지 주소만 허용
            if img.startswith(("http://", "https://")):
                return img
    return ""


def _absolutize(img_url, page_url):
    """상대경로/프로토콜 생략 이미지 주소를 절대 URL 로 변환."""
    if img_url.startswith("//"):
        return urlparse(page_url).scheme + ":" + img_url
    if img_url.startswith(("http://", "https://")):
        return img_url
    return urljoin(page_url, img_url)
