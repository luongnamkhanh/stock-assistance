"""HTTP GET dung chung cho cac API ngoai — UA gia trinh duyet vi vai nguon chan client la."""
import json
import urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0"}


def http_get(url, headers=HEADERS, timeout=25):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout).read()


def http_json(url, headers=HEADERS, timeout=25):
    return json.loads(http_get(url, headers, timeout))
