import os
import json
import logging
from datetime import datetime
import anthropic
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('note_poster.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは20代のOL兼個人投資家で、noteで有料記事（1,000円）を月20本以上販売している実力派です。
投資初心者ではなく、実際に利益を出している女性投資家として、読者が「この人の経験、真似したい」と思う記事を書いてください。

【絶対に守るルール】
- 一人称は「私」で統一
- 文末は「〜だった」「〜した」「〜だと思う」の実体験調
- 「！」「✓」「🎉」などの記号・絵文字は使わない
- 「〜しましょう」「〜ください」という上から目線は避ける
- 抽象論・一般論は避け、必ず「いつ・いくら・何を・何回」など具体的な数字と銘柄・ツール名で語る
- 「同僚と違う視点」「OLだからこそ気づいたこと」を必ず1つ以上入れる
- 失敗と成功の両方を生々しく、感情的に描写する

【差別化のための必須要素】
- 普通の投資ブログにない「ここだけの話」感を演出する
- 心理的な葛藤：「給料が減るんじゃないかと怖かった」「同僚に隠していた」など
- 女性だからこその工夫：「生活費は貯金で確保、給料は全額投資」など独自の戦略
- 利益確定時の喜び、損切り時の悔しさなど、感情のリアルさ
- タイミングの秘密：「なぜあの時買ったのか」という心理的背景

【構造】
1. # タイトル
2. ## 読む前に（無料部分）
3. ## [結果の概要]（無料部分）
4. ＝＝＝＝＝ ここから有料エリア ＝＝＝＝＝
5. ## [実体験セクション]×3〜5個（有料部分）
6. ## 私が失敗した話（最重要）
7. ## 同僚にはまだ言えない本音
8. ## まとめ

記事は「同じOLとして真似したい」「この人の次の記事も読みたい」と思わせることが最優先。"""

INVESTMENT_TOPICS = [
    {"title": "月給25万円のOLが年間200万円稼いだ日本株投資法", "keywords": ["日本株", "銘柄選定", "短期売買"]},
    {"title": "米国株ETFで給料の3倍を短期間で増やした方法", "keywords": ["米国株", "ETF", "配当"]},
    {"title": "仮想通貨で失敗した私が利益を出すまでの全記録", "keywords": ["仮想通貨", "リスク管理", "タイミング"]},
    {"title": "FXで月3万円を安定して稼ぐOLの取引戦略", "keywords": ["FX", "スイングトレード", "損切り"]},
    {"title": "給料を全額投資に回すOLが実践する資金管理術", "keywords": ["資金管理", "貯金", "投資割合"]},
    {"title": "同僚に隠したまま5年で1000万円を作った投資戦略", "keywords": ["長期投資", "複利", "継続"]},
    {"title": "26歳OLが経験した投資詐欺から学んだ教訓", "keywords": ["詐欺対策", "情報リテラシー", "警戒"]},
    {"title": "忙しいOL向け：朝5分で完結する投資判断法", "keywords": ["時間効率", "スクリーニング", "判断基準"]},
]

async def generate_article(topic: dict) -> str:
    """Claude APIで記事を生成"""
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    keywords_str = '、'.join(topic['keywords'])
    user_prompt = f"""以下の条件でnote有料記事（1,000円）を書いてください。

記事タイトル：{topic['title']}
関連キーワード・テーマ：{keywords_str}
ターゲット読者：20代女性、投資初心者から中級者

上記の内容に忠実に、体験談ベースのリアルな記事を生成してください。架空でも構いませんが、リアリティのある具体的な数字・エピソードを入れてください。"""

    logger.info(f"記事生成開始: {topic['title']}")

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    article_content = message.content[0].text
    logger.info(f"記事生成完了: {len(article_content)} 文字")
    return article_content

# "draft" なら下書き保存で止める（検証用）、"publish" なら実際に公開する
PUBLISH_MODE = os.environ.get("NOTE_PUBLISH_MODE", "publish").strip().lower()


async def log_visible_controls(page, label: str) -> None:
    """画面上のボタン/リンクの文言を一覧でログに出す。セレクタ特定のための診断用。"""
    try:
        texts = await page.evaluate(
            """() => Array.from(document.querySelectorAll('button, a[role="button"], a'))
                .map(el => (el.innerText || '').trim())
                .filter(t => t && t.length < 30)
                .slice(0, 40)"""
        )
        logger.info(f"[{label}] URL={page.url} 操作可能な要素: {texts}")
    except Exception as e:
        logger.warning(f"[{label}] 要素一覧の取得に失敗: {str(e)}")


async def dump_page_state(page, label: str) -> None:
    """ページが期待通り描画されないときに、原因特定のため中身をログに出す。"""
    try:
        html = await page.content()
        body_text = ""
        try:
            body_text = (await page.locator("body").inner_text())[:400]
        except Exception:
            pass
        logger.warning(
            f"[{label}] URL={page.url} HTML長={len(html)} 本文抜粋={body_text!r}"
        )
    except Exception as e:
        logger.warning(f"[{label}] ページ状態の取得に失敗: {str(e)}")


async def click_first(page, selectors: list, label: str, timeout: int = 8000):
    """候補セレクタを順に試し、最初に見つかった要素をクリックする。"""
    for selector in selectors:
        element = page.locator(selector).first
        try:
            await element.wait_for(state="visible", timeout=timeout)
            await element.click()
            logger.info(f"{label}をクリック: {selector}")
            return True
        except Exception:
            continue
    raise Exception(f"{label}が見つかりませんでした（試したセレクタ: {selectors}）")


async def post_to_note(session_file: str, title: str, content: str) -> bool:
    """Playwrightを使用してnoteに投稿（事前に保存したログインセッションを利用）"""
    async with async_playwright() as p:
        # noteのエディタはSPAで、ヘッドレス既定の環境だと起動しないことがあるため
        # 実ブラウザに近い条件（UA・言語・画面サイズ）を明示する
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=session_file,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        page = await context.new_page()
        page.on("console", lambda msg: logger.info(f"[browser:{msg.type}] {msg.text[:200]}"))
        page.on("pageerror", lambda err: logger.warning(f"[browser:pageerror] {str(err)[:300]}"))

        try:
            # noteトップページへ（ログイン済みセッションを利用するためログイン操作は不要）
            logger.info("noteトップページにアクセス中...")
            await page.goto("https://note.com/", wait_until="networkidle")

            if "login" in page.url:
                logger.error(
                    "ログインセッションが無効です。note_login_setup.py を再実行して "
                    "note_session.json を更新し、NOTE_SESSION_STATEシークレットも更新してください。"
                )
                try:
                    await page.screenshot(path="note_error_screenshot.png", full_page=True)
                    html = await page.content()
                    with open("note_error_page.html", "w", encoding="utf-8") as f:
                        f.write(html)
                except Exception as debug_e:
                    logger.error(f"デバッグ情報の保存にも失敗: {str(debug_e)}")
                return False

            logger.info("ログイン済みセッションを確認")

            # 「投稿」ボタンから新規記事エディタへ遷移（editor.note.com にランダムIDで作成される）
            logger.info("新規投稿ページへ遷移中...")
            post_button_selectors = [
                'a:has-text("投稿")',
                'button:has-text("投稿")',
            ]
            clicked = False
            for selector in post_button_selectors:
                btn = page.locator(selector).first
                try:
                    await btn.wait_for(state="visible", timeout=5000)
                    await btn.click()
                    clicked = True
                    logger.info(f"投稿ボタンをクリック: {selector}")
                    break
                except Exception:
                    continue
            if not clicked:
                raise Exception("投稿ボタンが見つかりませんでした")

            await page.wait_for_url("**editor.note.com/**", timeout=15000)
            logger.info(f"エディタページに遷移: {page.url}")

            # editor.note.com はSPAで、/new から /notes/{id}/edit/ へクライアント側遷移する。
            # 描画が完了しないことがあるため、リロードを挟んで再試行する。
            title_selector = 'textarea[placeholder*="タイトル"], input[placeholder*="タイトル"]'
            title_field = None
            for attempt in range(1, 4):
                try:
                    candidate = page.locator(title_selector).first
                    await candidate.wait_for(state="visible", timeout=20000)
                    title_field = candidate
                    logger.info(f"エディタ準備完了（{attempt}回目）: {page.url}")
                    break
                except Exception:
                    await dump_page_state(page, f"エディタ描画待ち{attempt}回目")
                    if attempt < 3:
                        logger.warning(f"エディタが描画されないためリロードします（{attempt}回目）")
                        await page.reload(wait_until="networkidle")
                        await page.wait_for_timeout(3000)
            if title_field is None:
                raise Exception("エディタのタイトル入力欄が描画されませんでした")

            logger.info("タイトル入力中...")
            await title_field.fill(title)
            await page.wait_for_timeout(500)

            # 本文入力
            logger.info("本文入力中...")
            body = page.locator('div[contenteditable="true"]').first
            await body.wait_for(state="visible", timeout=15000)
            await body.click()
            await page.wait_for_timeout(300)

            # ブロックエディタなので、行ごとに挿入してEnterで次のブロックへ進める。
            # keyboard.type は1文字ずつで数千文字だと極端に遅いため insert_text を使う。
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line:
                    await page.keyboard.insert_text(line)
                if i < len(lines) - 1:
                    await page.keyboard.press("Enter")
            logger.info(f"本文入力完了: {len(content)} 文字 / {len(lines)} 行")
            await page.wait_for_timeout(1500)

            await log_visible_controls(page, "エディタ画面")

            if PUBLISH_MODE == "draft":
                logger.info("下書き保存モードで実行中")
                await click_first(page, ['button:has-text("下書き保存")'], "下書き保存ボタン")
                await page.wait_for_timeout(3000)
                logger.info("下書き保存完了")
                return True

            # 公開設定画面へ
            logger.info("公開設定画面へ遷移中...")
            await click_first(page, ['button:has-text("公開に進む")', 'a:has-text("公開に進む")'], "公開に進むボタン")
            await page.wait_for_timeout(3000)
            await log_visible_controls(page, "公開設定画面")

            # 価格設定（1,000円）
            logger.info("価格設定中...")
            try:
                await click_first(page, ['button:has-text("有料")', 'label:has-text("有料")'], "有料設定")
                await page.wait_for_timeout(1000)
                price_input = page.locator('input[type="number"], input[placeholder*="価格"], input[name*="price"]').first
                await price_input.wait_for(state="visible", timeout=5000)
                await price_input.fill("1000")
                logger.info("価格を1000円に設定")
                await page.wait_for_timeout(500)
            except Exception as price_e:
                logger.warning(f"価格設定をスキップ（無料記事として投稿されます）: {str(price_e)}")

            # 公開
            logger.info("公開中...")
            await click_first(
                page,
                ['button:has-text("公開する")', 'button:has-text("投稿する")', 'button:has-text("公開")'],
                "公開ボタン",
            )
            await page.wait_for_timeout(5000)
            await log_visible_controls(page, "公開後の画面")

            logger.info("投稿完了")
            return True

        except Exception as e:
            logger.error(f"投稿エラー: {str(e)}")
            try:
                await page.screenshot(path="note_error_screenshot.png", full_page=True)
                html = await page.content()
                with open("note_error_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.error(f"デバッグ情報を保存しました（URL: {page.url}）")
            except Exception as debug_e:
                logger.error(f"デバッグ情報の保存にも失敗: {str(debug_e)}")
            return False
        finally:
            await browser.close()

SESSION_FILE = "note_session.json"

async def main():
    """メイン処理"""
    try:
        if not os.path.exists(SESSION_FILE):
            logger.error(
                f"{SESSION_FILE} が見つかりません。note_login_setup.py を実行して"
                "ログインセッションを作成してください。"
            )
            return False

        # トピック選択（ランダムまたはスケジュール）
        import random
        topic = random.choice(INVESTMENT_TOPICS)

        # 記事生成
        content = await generate_article(topic)

        # noteに投稿
        success = await post_to_note(SESSION_FILE, topic['title'], content)

        if success:
            logger.info(f"✅ 投稿成功: {topic['title']}")
            # 投稿履歴を記録
            with open('posted_articles.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'title': topic['title'],
                    'status': 'success'
                }, ensure_ascii=False) + '\n')
            return True
        else:
            logger.error(f"❌ 投稿失敗: {topic['title']}")
            return False

    except Exception as e:
        logger.error(f"エラー発生: {str(e)}")
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    exit(0 if success else 1)
