import os
import json
import logging
from datetime import date, datetime
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

SYSTEM_PROMPT = """あなたは個別銘柄の解説記事を書く金融ライターです。
1銘柄を1記事で掘り下げ、読者がその企業を理解して自分で投資判断できる材料を提供してください。

【最重要：事実にもとづくこと】
- 株価・時価総額・PER・PBR・配当利回り・業績などの数値は、必ずweb検索で取得した実際のデータのみを使う
- 検索で確認できなかった数値は書かない。「◯◯円」と推測で埋めることは絶対にしない
- 数値には必ず基準日を添える（例：株価3,240円（2026年7月25日終値））
- 記事末尾に参照した情報源（媒体名とURL）を列挙する
- 決算の数字は「会社発表」「四半期報告書」など出典が明確なものを使う

【文体】
- 一人称は使わない。筆者個人の体験談・売買記録・保有状況は一切書かない
- 「私は買った」「利益が出た」といった個人の実績を装う記述は禁止
- 客観的な解説調（「〜である」「〜と考えられる」）
- 「！」「✓」「🎉」などの記号・絵文字は使わない
- 断定的な推奨（「今すぐ買うべき」「必ず上がる」）はしない。判断材料を示し、判断は読者に委ねる

【構造（必ずこの順番で）】
1. # タイトル（与えられたタイトルをそのまま使う）
2. ## この銘柄の要点（無料部分）
   - 3〜5行で「どんな会社で、いま何が論点か」を提示
3. ## 事業内容（無料部分）
   - 何で稼いでいるのか、収益の柱を具体的に
   - セグメント別の売上構成を表にする
4. ＝＝＝＝＝ ここから有料エリア ＝＝＝＝＝
5. ## 業績の推移
   - 直近数期の売上・利益を表で示す
6. ## 株価と主要指標
   - 株価、時価総額、PER、PBR、配当利回りを表で示し、同業他社と比較する
7. ## 成長の driver（強み・追い風）
   - 2〜4個、それぞれ根拠となる数字とともに
8. ## リスク要因
   - 2〜4個。競合、規制、為替、業績変動要因など具体的に
9. ## まとめ
   - 強気に見るなら何が根拠か、慎重に見るなら何が懸念か、両論を整理
10. ## 参照した情報源
    - 媒体名とURLを列挙
11. 末尾に免責事項（下記の文言をそのまま入れる）

【免責事項（記事末尾にそのまま記載）】
本記事は特定の銘柄の売買を推奨するものではなく、情報提供を目的としています。記載の数値は執筆時点で公開されている情報にもとづきますが、正確性を保証するものではありません。投資判断はご自身の責任でお願いします。

【必須要素】
- 表を2つ以上（業績推移、主要指標の比較など）
- 検索で裏付けた具体的な数値を10個以上
- 分量：3000〜4500文字"""

# 1日1銘柄を解説する。日付でローテーションし、同じ銘柄が続かないようにする。
STOCKS = [
    {"name": "トヨタ自動車", "ticker": "7203", "market": "東証プライム"},
    {"name": "ソニーグループ", "ticker": "6758", "market": "東証プライム"},
    {"name": "三菱UFJフィナンシャル・グループ", "ticker": "8306", "market": "東証プライム"},
    {"name": "任天堂", "ticker": "7974", "market": "東証プライム"},
    {"name": "信越化学工業", "ticker": "4063", "market": "東証プライム"},
    {"name": "東京エレクトロン", "ticker": "8035", "market": "東証プライム"},
    {"name": "ファーストリテイリング", "ticker": "9983", "market": "東証プライム"},
    {"name": "日立製作所", "ticker": "6501", "market": "東証プライム"},
    {"name": "キーエンス", "ticker": "6861", "market": "東証プライム"},
    {"name": "リクルートホールディングス", "ticker": "6098", "market": "東証プライム"},
    {"name": "オリエンタルランド", "ticker": "4661", "market": "東証プライム"},
    {"name": "武田薬品工業", "ticker": "4502", "market": "東証プライム"},
    {"name": "NVIDIA", "ticker": "NVDA", "market": "NASDAQ"},
    {"name": "Apple", "ticker": "AAPL", "market": "NASDAQ"},
    {"name": "Microsoft", "ticker": "MSFT", "market": "NASDAQ"},
    {"name": "Alphabet", "ticker": "GOOGL", "market": "NASDAQ"},
    {"name": "Amazon.com", "ticker": "AMZN", "market": "NASDAQ"},
    {"name": "Meta Platforms", "ticker": "META", "market": "NASDAQ"},
    {"name": "Eli Lilly", "ticker": "LLY", "market": "NYSE"},
    {"name": "Visa", "ticker": "V", "market": "NYSE"},
    {"name": "Coca-Cola", "ticker": "KO", "market": "NYSE"},
    {"name": "Costco Wholesale", "ticker": "COST", "market": "NASDAQ"},
]

def pick_stock_of_the_day(today: date) -> dict:
    """日付でローテーションし、毎日違う銘柄を選ぶ。"""
    return STOCKS[today.toordinal() % len(STOCKS)]


def build_title(stock: dict) -> str:
    return f"【{stock['ticker']}】{stock['name']}を解説｜事業内容・業績・リスクまで"


async def generate_article(stock: dict, title: str) -> str:
    """Claude APIで個別銘柄の解説記事を生成する。

    株価や業績は日々変わるため、web検索ツールで実際のデータを取得させたうえで書かせる。
    検索なしで書かせると、もっともらしい嘘の数値が並ぶことになる。
    """
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    today = date.today().strftime("%Y年%m月%d日")
    user_prompt = f"""今日は{today}です。以下の銘柄について、note有料記事（1,000円）を書いてください。

銘柄：{stock['name']}（{stock['market']}：{stock['ticker']}）
記事タイトル：{title}

まずweb検索で以下を調べ、確認できた事実だけを使って記事を書いてください。
- 直近の株価、時価総額、PER、PBR、配当利回り
- 直近の決算（売上高、営業利益、純利益）と前年同期比
- セグメント別の売上構成
- 直近のニュース（新製品、業績修正、経営方針など）
- 同業他社の主要指標（比較のため）

検索で確認できなかった項目は、無理に埋めず「公開情報では確認できなかった」と明記してください。
数値には必ず基準日を添え、記事末尾に参照した情報源のURLを列挙してください。"""

    logger.info(f"記事生成開始（web検索あり）: {title}")

    messages = [{"role": "user", "content": user_prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search"}]

    # web検索を伴う応答はサーバ側のループが上限に達すると pause_turn で一旦返るため、
    # 完了するまで同じ会話を送り直して再開させる。
    for attempt in range(5):
        message = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        if message.stop_reason != "pause_turn":
            break
        logger.info(f"web検索が継続中のため再開します（{attempt + 1}回目）")
        messages = [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": message.content},
        ]

    if message.stop_reason == "refusal":
        raise Exception("記事生成が安全性の理由で拒否されました")

    # web検索を使うと content に検索結果ブロックが混ざるため、本文のテキストだけを取り出す
    article_content = "\n".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
    if not article_content:
        raise Exception(f"記事本文が生成されませんでした（stop_reason={message.stop_reason}）")

    searches = sum(1 for block in message.content if block.type == "server_tool_use")
    logger.info(f"記事生成完了: {len(article_content)} 文字 / web検索 {searches} 回")
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


async def set_paid_price(page, price: str = "1000") -> None:
    """公開設定画面で記事タイプを有料にし、価格を設定する。

    実機調査の結果、記事タイプはラジオ input[name="is_paid"]、
    価格欄は type="number" ではなく placeholder に最低価格が入った text input だった。
    """
    # ラジオ本体はCSSで隠されており直接checkできないため、対応するlabelをクリックする
    await click_first(page, ['label[for="paid"]', 'label:has-text("有料")'], "記事タイプ「有料」")
    await page.wait_for_timeout(2000)

    checked = await page.evaluate(
        """() => {
            const el = document.querySelector('input[name="is_paid"][value="paid"]');
            return el ? el.checked : null;
        }"""
    )
    if not checked:
        raise Exception(f"記事タイプを有料に切り替えられませんでした（checked={checked}）")
    logger.info("記事タイプを有料に設定")

    price_input = page.locator(
        'input[placeholder="300"], input[type="text"]:not([placeholder*="ハッシュタグ"])'
    ).first
    await price_input.wait_for(state="visible", timeout=8000)
    await price_input.fill(price)
    await page.wait_for_timeout(500)
    actual = await price_input.input_value()
    if actual != price:
        raise Exception(f"価格の設定に失敗しました（入力後の値: {actual!r}）")
    logger.info(f"価格を{price}円に設定")


PAYWALL_MARKER = "＝＝＝＝＝ ここから有料エリア ＝＝＝＝＝"


async def set_paywall_boundary(page) -> None:
    """有料エリアの境界（どこから有料か）を記事内の目印の位置に移動する。

    有料エリア設定画面では各段落の間に「ラインをこの場所に変更」ボタンが並んでおり、
    初期状態では境界が記事の先頭（＝全文が有料）にある。
    本文に埋め込んだ目印の直後のボタンを押して、無料部分と有料部分を分ける。
    """
    # 目印を含む要素は入れ子になっており、外側のコンテナにマッチすると
    # 記事先頭のボタンを選んでしまうため、最も内側の要素を使う。
    info = await page.evaluate(
        """(marker) => {
            const buttons = Array.from(document.querySelectorAll('button'))
                .filter(b => (b.innerText || '').trim() === 'ラインをこの場所に変更');
            const candidates = Array.from(document.querySelectorAll('p, div, h1, h2, h3, li, span'))
                .filter(el => (el.innerText || '').includes(marker));
            const markerEl = candidates.find(
                el => !candidates.some(other => other !== el && el.contains(other))
            );
            if (!markerEl) {
                return {index: -1, candidates: candidates.length, buttons: buttons.length};
            }
            const index = buttons.findIndex(
                b => markerEl.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING
            );
            return {
                index,
                candidates: candidates.length,
                buttons: buttons.length,
                markerTag: markerEl.tagName,
                markerText: (markerEl.innerText || '').slice(0, 60),
            };
        }""",
        PAYWALL_MARKER,
    )
    logger.info(f"有料エリアの目印の解析結果: {info}")
    index = info.get("index", -1)
    if index < 0:
        raise Exception(
            f"本文中の有料エリアの目印（{PAYWALL_MARKER}）が見つからず、境界を設定できませんでした"
        )
    # 目印は記事の中盤にあるはずなので、先頭付近が選ばれた場合は解析ミスとみなす
    if index < 2:
        raise Exception(
            f"有料エリアの境界が記事の先頭付近（{index}番目）と判定されました。"
            "全文有料での公開を避けるため中断します"
        )

    button = page.locator('button:has-text("ラインをこの場所に変更")').nth(index)
    await button.click()
    logger.info(f"有料エリアの境界を目印の直後（{index}番目）に設定")
    await page.wait_for_timeout(2000)

    # 境界が目印より後ろに移動したかを確認する。移動していないと全文有料で公開されてしまう。
    result = await page.evaluate(
        """(marker) => {
            const lines = Array.from(document.querySelectorAll('*'))
                .filter(el => (el.innerText || '').trim() === 'このラインより先を有料にする');
            const line = lines.find(
                el => !lines.some(other => other !== el && el.contains(other))
            );
            const candidates = Array.from(document.querySelectorAll('p, div, h1, h2, h3, li, span'))
                .filter(el => (el.innerText || '').includes(marker));
            const markerEl = candidates.find(
                el => !candidates.some(other => other !== el && el.contains(other))
            );
            if (!line || !markerEl) return {ok: false, reason: '要素が見つからない'};
            const after = Boolean(
                markerEl.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING
            );
            const body = document.body.innerText || '';
            const markerPos = body.indexOf(marker);
            return {ok: after, freeRatio: markerPos > 0 ? markerPos / body.length : null};
        }""",
        PAYWALL_MARKER,
    )
    if not result.get("ok"):
        raise Exception(
            f"有料エリアの境界が想定位置に移動しませんでした（{result}）。全文有料を避けるため中断します"
        )
    logger.info(f"有料エリアの境界位置を確認: {result}")


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

            # 公開処理で失敗しても記事が失われないよう、先に下書きとして保存する
            await click_first(page, ['button:has-text("下書き保存")'], "下書き保存ボタン")
            await page.wait_for_timeout(3000)
            logger.info("下書き保存完了")

            if PUBLISH_MODE == "draft":
                logger.info("下書き保存モードのため、公開せずに終了します")
                return True

            # 公開設定画面へ
            logger.info("公開設定画面へ遷移中...")
            await click_first(page, ['button:has-text("公開に進む")', 'a:has-text("公開に進む")'], "公開に進むボタン")
            await page.wait_for_timeout(3000)
            await log_visible_controls(page, "公開設定画面")

            # 価格設定（1,000円）
            # 有料設定に失敗したまま公開すると意図せず無料公開されてしまい取り返しがつかないため、
            # ここで失敗した場合は公開せずに中断する。
            logger.info("価格設定中...")
            try:
                await set_paid_price(page, "1000")
            except Exception as price_e:
                await dump_page_state(page, "価格設定失敗")
                raise Exception(
                    f"1,000円の有料設定ができませんでした。無料公開を避けるため公開を中断します: {str(price_e)}"
                )

            # 有料記事は本文のどこから有料かを指定しないと投稿できない
            logger.info("有料エリアを設定中...")
            await click_first(page, ['button:has-text("有料エリア設定")'], "有料エリア設定ボタン")
            await page.wait_for_timeout(4000)
            await log_visible_controls(page, "有料エリア設定画面")
            await set_paywall_boundary(page)

            # 公開
            logger.info("公開中...")
            await click_first(
                page,
                ['button:has-text("投稿する")', 'button:has-text("公開する")'],
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

        # 今日の解説対象銘柄（日付でローテーション）
        stock = pick_stock_of_the_day(date.today())
        title = build_title(stock)
        logger.info(f"本日の銘柄: {stock['name']}（{stock['ticker']}）")

        # 記事生成
        content = await generate_article(stock, title)

        # noteに投稿
        success = await post_to_note(SESSION_FILE, title, content)

        if success:
            logger.info(f"✅ 投稿成功: {title}")
            # 投稿履歴を記録
            with open('posted_articles.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'title': title,
                    'ticker': stock['ticker'],
                    'status': 'success'
                }, ensure_ascii=False) + '\n')
            return True
        else:
            logger.error(f"❌ 投稿失敗: {title}")
            return False

    except Exception as e:
        logger.error(f"エラー発生: {str(e)}")
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    exit(0 if success else 1)
