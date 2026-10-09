import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, ElementTree
from email.utils import format_datetime
from datetime import datetime, timezone, timedelta
import hashlib
import os
import re

BASE_URL = "https://www.convex-okayama.co.jp"
LIST_URL = "https://www.convex-okayama.co.jp/event/"
OUTPUT_FILE = "convex_okayama.xml"

JST = timezone(timedelta(hours=9))

headers = {
    "User-Agent": "Mozilla/5.0"
}

# --------------------------------------------------
# 以前のRSSに存在するイベントとpubDateを読み込む
# --------------------------------------------------

old_items = {}

if os.path.exists(OUTPUT_FILE):
    try:
        old_tree = ElementTree()
        old_tree.parse(OUTPUT_FILE)
        old_root = old_tree.getroot()

        for item in old_root.findall("./channel/item"):
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()

            if link:
                old_items[link] = pub_date

    except Exception as e:
        print("既存XML読み込みエラー:", e)

print("既存RSS件数:", len(old_items))

# --------------------------------------------------
# イベント一覧を全ページ取得
# --------------------------------------------------

events = {}
page = 1

while True:
    if page == 1:
        url = LIST_URL
    else:
        url = f"{LIST_URL}page/{page}/"

    r = requests.get(url, headers=headers, timeout=30)

    print(f"PAGE {page} HTTP:", r.status_code)

    if r.status_code == 404:
        break

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    found = 0

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a["href"])

        # /event/数字/ の個別イベントだけ
        if not re.fullmatch(
            r"https://www\.convex-okayama\.co\.jp/event/\d+/",
            href
        ):
            continue

        text = " ".join(a.stripped_strings).strip()

        if not text:
            continue

        # 「期間：...」の後ろからタイトル部分を取り出す
        text = re.sub(r"^期間：\S+(?:〜\S+)?\s*", "", text)

        # 会場名などより前をタイトル候補にする
        separators = [
            " 大展示場",
            " 中展示場",
            " 小展示場",
            " 屋外展示場",
        ]

        title = text

        positions = [
            title.find(s)
            for s in separators
            if title.find(s) != -1
        ]

        if positions:
            title = title[:min(positions)]

        title = title.strip()

        if not title:
            continue

        events[href] = title
        found += 1

    print(f"PAGE {page} イベント:", found)

    # 次ページが存在するか確認
    next_url = f"{LIST_URL}page/{page + 1}/"

    has_next = any(
        urljoin(BASE_URL, a.get("href", "")) == next_url
        for a in soup.find_all("a", href=True)
    )

    if not has_next:
        break

    page += 1

print()
print("現在のイベント総数:", len(events))

# --------------------------------------------------
# RSS作成
# --------------------------------------------------

now = datetime.now(JST)

rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "コンベックス岡山 イベント情報"
SubElement(channel, "link").text = LIST_URL
SubElement(channel, "description").text = "コンベックス岡山のイベント情報"
SubElement(channel, "language").text = "ja"

rss_items = []

for link, title in events.items():

    if link in old_items and old_items[link]:
        pub_date = old_items[link]
        is_new = False
    else:
        pub_date = format_datetime(now)
        is_new = True

    rss_items.append({
        "title": title,
        "link": link,
        "pubDate": pub_date,
        "new": is_new,
    })

# 新規イベントを先頭へ
rss_items.sort(
    key=lambda x: (not x["new"], x["link"])
)

for i, data in enumerate(rss_items, 1):

    item = SubElement(channel, "item")

    SubElement(item, "title").text = data["title"]
    SubElement(item, "link").text = data["link"]

    guid = SubElement(item, "guid", isPermaLink="false")
    guid.text = hashlib.sha256(
        data["link"].encode("utf-8")
    ).hexdigest()

    SubElement(item, "pubDate").text = data["pubDate"]

    status = "NEW" if data["new"] else "OLD"

    print(
        f"[{i}] {status} "
        f"{data['title']} "
        f"{data['link']}"
    )

tree = ElementTree(rss)

tree.write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)

print()
print("保存:", OUTPUT_FILE)
