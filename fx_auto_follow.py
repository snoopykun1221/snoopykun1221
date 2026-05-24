#!/usr/bin/env python3
"""
FX Auto Follow Bot
X (Twitter) でFXについて発言しているユーザーを1日200人自動フォローするシステム
"""

import os
import json
import time
import logging
import sys
from datetime import datetime, date
from pathlib import Path

import tweepy
from dotenv import load_dotenv

load_dotenv()

# ── ロギング設定 ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fx_follow.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── 設定 ────────────────────────────────────────────────────────
API_KEY             = os.getenv("X_API_KEY")
API_SECRET          = os.getenv("X_API_SECRET")
ACCESS_TOKEN        = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
BEARER_TOKEN        = os.getenv("X_BEARER_TOKEN")

DAILY_FOLLOW_LIMIT  = int(os.getenv("DAILY_FOLLOW_LIMIT", "200"))
FOLLOW_INTERVAL_SEC = int(os.getenv("FOLLOW_INTERVAL_SEC", "18"))   # 1フォローあたりの待機秒数
SEARCH_MAX_RESULTS  = int(os.getenv("SEARCH_MAX_RESULTS", "100"))   # 1クエリあたりの最大件数

STATE_FILE = Path("follow_state.json")

# FX関連キーワード（日本語・英語）
FX_KEYWORDS = [
    "FX",
    "外国為替",
    "ドル円",
    "USDJPY",
    "ユーロ円",
    "EURUSD",
    "為替トレード",
    "スキャルピング",
    "スワップポイント",
    "MT4",
    "MT5",
    "fx取引",
    "テクニカル分析 FX",
    "ポンド円",
    "豪ドル円",
    "fx投資",
]

# ── 状態管理 ────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    return {"followed_ids": [], "daily_counts": {}}


def save_state(state: dict) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_today_count(state: dict) -> int:
    today = str(date.today())
    return state["daily_counts"].get(today, 0)


def increment_today_count(state: dict) -> None:
    today = str(date.today())
    state["daily_counts"][today] = state["daily_counts"].get(today, 0) + 1


# ── Twitter クライアント初期化 ───────────────────────────────────

def build_client() -> tweepy.Client:
    for var, name in [
        (API_KEY,             "X_API_KEY"),
        (API_SECRET,          "X_API_SECRET"),
        (ACCESS_TOKEN,        "X_ACCESS_TOKEN"),
        (ACCESS_TOKEN_SECRET, "X_ACCESS_TOKEN_SECRET"),
        (BEARER_TOKEN,        "X_BEARER_TOKEN"),
    ]:
        if not var:
            logger.error(f"環境変数 {name} が設定されていません。.env を確認してください。")
            sys.exit(1)

    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def get_my_id(client: tweepy.Client) -> str:
    me = client.get_me()
    return str(me.data.id)


# ── ツイート検索 ─────────────────────────────────────────────────

def search_fx_users(client: tweepy.Client, already_followed: set) -> list:
    """FX関連ツイートを投稿したユーザーIDリストを返す（重複・自分除く）"""
    query_parts = [f'"{kw}"' for kw in FX_KEYWORDS[:8]]   # APIクエリ長制限のため上限設定
    query = "(" + " OR ".join(query_parts) + ") lang:ja -is:retweet -is:reply"

    logger.info(f"検索クエリ: {query}")

    found_user_ids = []
    seen = set()

    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=min(SEARCH_MAX_RESULTS, 100),
            tweet_fields=["author_id"],
        )
    except tweepy.TweepyException as e:
        logger.error(f"ツイート検索エラー: {e}")
        return []

    if not resp.data:
        logger.info("該当ツイートが見つかりませんでした。")
        return []

    for tweet in resp.data:
        uid = str(tweet.author_id)
        if uid not in seen and uid not in already_followed:
            seen.add(uid)
            found_user_ids.append(uid)

    logger.info(f"新規フォロー候補: {len(found_user_ids)} 人")
    return found_user_ids


# ── フォロー実行 ─────────────────────────────────────────────────

def follow_users(
    client: tweepy.Client,
    my_id: str,
    user_ids: list,
    state: dict,
) -> int:
    followed_count = 0
    today_count = get_today_count(state)
    remaining = DAILY_FOLLOW_LIMIT - today_count

    if remaining <= 0:
        logger.info(f"本日の上限 {DAILY_FOLLOW_LIMIT} 人に達しました。明日また実行してください。")
        return 0

    targets = user_ids[:remaining]
    logger.info(f"本日の残り枠: {remaining} 人 / 今回フォロー予定: {len(targets)} 人")

    for uid in targets:
        try:
            client.follow_user(my_id, uid)
            state["followed_ids"].append(uid)
            increment_today_count(state)
            save_state(state)
            followed_count += 1
            today_total = get_today_count(state)
            logger.info(
                f"フォロー完了: user_id={uid}  本日累計={today_total}/{DAILY_FOLLOW_LIMIT}"
            )
        except tweepy.errors.Forbidden as e:
            # すでにフォロー済み / ブロックされている等
            logger.warning(f"フォロー不可 user_id={uid}: {e}")
            state["followed_ids"].append(uid)  # 再試行しないようリストに追加
            save_state(state)
        except tweepy.TweepyException as e:
            logger.error(f"フォローエラー user_id={uid}: {e}")

        if followed_count < len(targets):
            time.sleep(FOLLOW_INTERVAL_SEC)

    return followed_count


# ── メイン ──────────────────────────────────────────────────────

def main():
    logger.info("=" * 50)
    logger.info("FX 自動フォローBot 起動")
    logger.info(f"1日上限: {DAILY_FOLLOW_LIMIT} 人 / 待機間隔: {FOLLOW_INTERVAL_SEC}秒")
    logger.info("=" * 50)

    state = load_state()
    today_count = get_today_count(state)
    logger.info(f"本日既フォロー数: {today_count}/{DAILY_FOLLOW_LIMIT}")

    if today_count >= DAILY_FOLLOW_LIMIT:
        logger.info("本日のフォロー上限に達しています。終了します。")
        return

    client = build_client()
    my_id = get_my_id(client)
    logger.info(f"認証済みアカウント ID: {my_id}")

    already_followed = set(state["followed_ids"])
    user_ids = search_fx_users(client, already_followed)

    if not user_ids:
        logger.info("フォロー対象が見つかりませんでした。終了します。")
        return

    total = follow_users(client, my_id, user_ids, state)
    logger.info(f"今回フォロー完了: {total} 人 / 本日累計: {get_today_count(state)}/{DAILY_FOLLOW_LIMIT}")


if __name__ == "__main__":
    main()
