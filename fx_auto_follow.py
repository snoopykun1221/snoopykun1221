#!/usr/bin/env python3
"""
FX Auto Follow Bot (Playwright版)
X上でFXについて発言しているユーザーを1日200人自動フォロー
"""

import asyncio
import json
import logging
import os
import random
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import (
    async_playwright,
    Page,
    BrowserContext,
    TimeoutError as PlaywrightTimeout,
)

load_dotenv()

# ── 設定 ────────────────────────────────────────────────────────
X_USERNAME        = os.getenv("X_USERNAME")        # XのIDまたはメールアドレス
X_PASSWORD        = os.getenv("X_PASSWORD")        # Xのパスワード
X_EMAIL           = os.getenv("X_EMAIL", "")       # 2段階認証時に使用するメールアドレス

DAILY_FOLLOW_LIMIT  = int(os.getenv("DAILY_FOLLOW_LIMIT", "200"))
FOLLOW_DELAY_MIN    = int(os.getenv("FOLLOW_DELAY_MIN", "30"))   # フォロー間隔 最小（秒）
FOLLOW_DELAY_MAX    = int(os.getenv("FOLLOW_DELAY_MAX", "90"))   # フォロー間隔 最大（秒）
HEADLESS            = os.getenv("HEADLESS", "false").lower() == "true"

STATE_FILE   = Path("follow_state.json")
COOKIES_FILE = Path("x_cookies.json")

# FX関連検索キーワード
FX_KEYWORDS = [
    "FX トレード",
    "ドル円",
    "USDJPY",
    "スキャルピング FX",
    "FX 投資",
    "ユーロ円",
    "MT4 FX",
    "為替 取引",
    "ポンド円",
    "豪ドル円",
]

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


# ── 状態管理 ────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    return {"followed_users": [], "daily_counts": {}}


def save_state(state: dict) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_today_count(state: dict) -> int:
    return state["daily_counts"].get(str(date.today()), 0)


def increment_today_count(state: dict) -> None:
    today = str(date.today())
    state["daily_counts"][today] = state["daily_counts"].get(today, 0) + 1


# ── Cookie管理 ──────────────────────────────────────────────────

async def save_cookies(context: BrowserContext) -> None:
    cookies = await context.cookies()
    with COOKIES_FILE.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logger.info("Cookieを保存しました。")


async def load_cookies(context: BrowserContext) -> bool:
    if not COOKIES_FILE.exists():
        return False
    with COOKIES_FILE.open(encoding="utf-8") as f:
        cookies = json.load(f)
    await context.add_cookies(cookies)
    logger.info("Cookieを読み込みました。")
    return True


# ── ランダム待機 ────────────────────────────────────────────────

async def human_wait(min_sec: float = 1.5, max_sec: float = 4.0) -> None:
    """人間らしいランダム待機（短い操作間）"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def follow_wait() -> None:
    """フォロー間のランダム待機（BANリスク軽減）"""
    sec = random.randint(FOLLOW_DELAY_MIN, FOLLOW_DELAY_MAX)
    logger.info(f"次のフォローまで {sec} 秒待機...")
    await asyncio.sleep(sec)


# ── ログイン ────────────────────────────────────────────────────

async def login(page: Page) -> bool:
    logger.info("ログイン開始...")
    await page.goto("https://x.com/login", wait_until="load", timeout=60000)
    await asyncio.sleep(4)
    logger.info(f"ページURL: {page.url}")

    # ユーザー名入力
    try:
        await page.wait_for_selector('input', timeout=20000)
        username_input = page.locator('input[name="text"], input[autocomplete="username"], input[type="text"]').first
        await username_input.wait_for(state="visible", timeout=20000)
        await username_input.click()
        await username_input.fill(X_USERNAME)
        logger.info("ユーザー名入力完了")
        await human_wait()
        # 「次へ」ボタンをクリック
        next_btn = page.locator('button[data-testid="LoginForm_Login_Button"], button:has-text("Next"), button:has-text("次へ")').first
        if await next_btn.count() > 0:
            await next_btn.click()
        else:
            await page.keyboard.press("Enter")
        # パスワード画面に遷移するまで待機
        try:
            await page.wait_for_url("**/login_enter_password**", timeout=10000)
        except PlaywrightTimeout:
            pass
        await asyncio.sleep(3)
        logger.info(f"ユーザー名後URL: {page.url}")
    except PlaywrightTimeout:
        logger.error("ユーザー名入力欄が見つかりません。")
        return False

    # メールアドレス確認が求められる場合
    email_input = page.locator('input[data-testid="ocfEnterTextTextInput"]')
    if await email_input.count() > 0:
        logger.info("メールアドレス確認が求められています。")
        if not X_EMAIL:
            logger.error("X_EMAIL が未設定です。.env に設定してください。")
            return False
        await email_input.fill(X_EMAIL)
        await human_wait()
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)

    # パスワード入力
    try:
        await page.wait_for_selector('input[type="password"]', timeout=15000)
        await asyncio.sleep(1)
        password_inputs = await page.locator('input[type="password"]').all()
        logger.info(f"パスワード入力欄の数: {len(password_inputs)}")
        password_input = page.locator('input[type="password"]').last
        await password_input.click(force=True)
        await password_input.fill(X_PASSWORD)
        logger.info("パスワード入力完了")
        await human_wait()
        await page.keyboard.press("Enter")
        await asyncio.sleep(6)
    except PlaywrightTimeout:
        logger.error("パスワード入力欄が見つかりません。")
        return False

    # ログイン成功確認
    logger.info(f"ログイン後URL: {page.url}")
    if "home" in page.url or ("x.com" in page.url and "login" not in page.url and "onboarding" not in page.url):
        logger.info("ログイン成功。")
        return True

    logger.error(f"ログイン失敗。現在のURL: {page.url}")
    return False


async def is_logged_in(page: Page) -> bool:
    """ログイン済みかどうか確認"""
    await page.goto("https://x.com/home", wait_until="load", timeout=30000)
    await human_wait()
    return "login" not in page.url


# ── ユーザー収集 ────────────────────────────────────────────────

async def collect_users_from_search(
    page: Page,
    keyword: str,
    already_followed: set,
    limit: int,
) -> list:
    """キーワード検索からフォロー候補ユーザーのusernameを収集"""
    import urllib.parse
    query = urllib.parse.quote(keyword)
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"

    logger.info(f"検索: [{keyword}]")
    await page.goto(url, wait_until="load", timeout=30000)
    await human_wait(2, 4)

    # スクロールしてツイートを読み込む
    for _ in range(3):
        await page.keyboard.press("End")
        await human_wait(1.5, 3)

    usernames = []
    seen = set()

    # ツイートからユーザーリンクを取得
    try:
        links = await page.locator('article[data-testid="tweet"] a[href*="/"]').all()
        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            parts = href.strip("/").split("/")
            # /username 形式のリンクを抽出（リプライ・ハッシュタグ等を除く）
            if (
                len(parts) == 1
                and not parts[0].startswith("?")
                and not parts[0].startswith("#")
                and parts[0] not in ("home", "explore", "notifications", "messages", "i")
            ):
                username = parts[0].lower()
                if username not in seen and username not in already_followed:
                    seen.add(username)
                    usernames.append(username)
                    if len(usernames) >= limit:
                        break
    except Exception as e:
        logger.warning(f"ユーザー取得エラー [{keyword}]: {e}")

    logger.info(f"  → {len(usernames)} 人の候補を取得")
    return usernames


# ── フォロー実行 ─────────────────────────────────────────────────

async def follow_user(page: Page, username: str) -> bool:
    """指定ユーザーのプロフィールを開いてフォローする"""
    try:
        await page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=20000)
        await human_wait(1.5, 3)

        # フォローボタンを探す
        follow_btn = page.locator('[data-testid="follow"]').first
        if await follow_btn.count() == 0:
            # すでにフォロー済み or 存在しないアカウント
            following_btn = page.locator('[data-testid="following"]')
            if await following_btn.count() > 0:
                logger.info(f"  {username}: すでにフォロー済み")
            else:
                logger.warning(f"  {username}: フォローボタンが見つかりません（非公開 or 存在しないアカウント）")
            return False

        await follow_btn.click()
        await human_wait(1, 2)

        # フォロー確認（ボタンが Following に変わる）
        if await page.locator('[data-testid="following"]').count() > 0:
            logger.info(f"  ✓ フォロー完了: @{username}")
            return True

        logger.warning(f"  {username}: フォロー操作後の確認ができませんでした")
        return False

    except PlaywrightTimeout:
        logger.warning(f"  {username}: タイムアウト")
        return False
    except Exception as e:
        logger.error(f"  {username}: エラー - {e}")
        return False


# ── 異常検知 ────────────────────────────────────────────────────

async def check_for_challenge(page: Page) -> bool:
    """Xの異常検知・チャレンジ画面を検出"""
    suspicious_texts = ["unusual activity", "認証", "Verify", "suspicious"]
    for text in suspicious_texts:
        if await page.locator(f'text={text}').count() > 0:
            return True
    if "challenge" in page.url or "suspended" in page.url:
        return True
    return False


# ── メイン ──────────────────────────────────────────────────────

async def main():
    logger.info("=" * 55)
    logger.info("FX 自動フォローBot (Playwright版) 起動")
    logger.info(f"1日上限: {DAILY_FOLLOW_LIMIT} 人  |  待機: {FOLLOW_DELAY_MIN}〜{FOLLOW_DELAY_MAX}秒")
    logger.info("=" * 55)

    # 認証情報確認
    if not X_USERNAME or not X_PASSWORD:
        logger.error("X_USERNAME / X_PASSWORD が未設定です。.env を確認してください。")
        sys.exit(1)

    # 状態読み込み
    state = load_state()
    today_count = get_today_count(state)
    logger.info(f"本日既フォロー数: {today_count} / {DAILY_FOLLOW_LIMIT}")

    if today_count >= DAILY_FOLLOW_LIMIT:
        logger.info("本日のフォロー上限に達しています。明日また実行してください。")
        return

    already_followed = set(state["followed_users"])
    remaining = DAILY_FOLLOW_LIMIT - today_count

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = await context.new_page()

        # Cookie ロードorログイン
        cookie_loaded = await load_cookies(context)
        logged_in = cookie_loaded and await is_logged_in(page)

        if not logged_in:
            logger.info("Cookieが無効です。ログインします。")
            success = await login(page)
            if not success:
                logger.error("ログインに失敗しました。終了します。")
                await browser.close()
                return
            await save_cookies(context)

        # フォロー候補を収集（複数キーワード）
        candidates = []
        per_keyword = max(10, remaining // len(FX_KEYWORDS) + 1)

        for keyword in FX_KEYWORDS:
            if len(candidates) >= remaining * 2:
                break
            users = await collect_users_from_search(page, keyword, already_followed, per_keyword)
            for u in users:
                if u not in [c for c in candidates]:
                    candidates.append(u)
            await human_wait(3, 6)

        logger.info(f"フォロー候補合計: {len(candidates)} 人")

        if not candidates:
            logger.info("フォロー候補が見つかりませんでした。終了します。")
            await browser.close()
            return

        # フォロー実行
        followed_count = 0
        for username in candidates:
            if get_today_count(state) >= DAILY_FOLLOW_LIMIT:
                logger.info("本日の上限に達しました。終了します。")
                break

            # 異常検知チェック
            if await check_for_challenge(page):
                logger.error("Xの異常検知画面が表示されました。手動で確認してください。")
                break

            success = await follow_user(page, username)

            # 成否に関わらずフォロー済みとして記録
            state["followed_users"].append(username)
            already_followed.add(username)

            if success:
                increment_today_count(state)
                followed_count += 1

            save_state(state)

            # 次のフォローまで待機（最後の1人は不要）
            today_total = get_today_count(state)
            logger.info(f"  本日累計: {today_total} / {DAILY_FOLLOW_LIMIT}")

            if today_total < DAILY_FOLLOW_LIMIT and username != candidates[-1]:
                await follow_wait()

        await save_cookies(context)
        await browser.close()

    logger.info(f"完了: 今回フォロー {followed_count} 人 / 本日累計 {get_today_count(state)} 人")


if __name__ == "__main__":
    asyncio.run(main())
