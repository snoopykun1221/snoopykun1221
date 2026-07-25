import os
import re
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

【書式の厳守（noteに直接入力されるため重要）】
- 見出しは「## 見出し文」の形式のみ使う。それ以外の記号は一切使わない
- 記事タイトルは本文に書かない。「# タイトル」で始めてはいけない（タイトルは別欄に入るため二重になる）
- 表（| 項目 | 値 |）は使用禁止。noteでは表として表示されず記号の羅列になる
  数値を並べるときは「売上高：3兆1,080億円（前年同期比 +12.3%）」のように1行1項目で書く
- 箇条書き記号（- や * や 1.）は使わない。文章か、上記の「項目：値」形式で書く
- 太字（**）、引用（>）、コードブロック（```）も使わない
- 見出しに「（無料部分）」「（有料部分）」などの注釈を書かない
- セクションの区切り線や「ここから有料」といった案内文も書かない

【構造（この見出しをこの順番で使う）】
## この銘柄の要点
   - 3〜5行で「どんな会社で、いま何が論点か」を提示
   - タイトルが問いかけ形式の場合、記事全体でその問いに答える構成にする
     （「展望は？」なら見通しの材料を、「何で稼いでいるのか」なら収益構造を厚く書く）
## 事業内容
   - 何で稼いでいるのか、収益の柱を具体的に
   - セグメント別の売上構成を「項目：値」形式で
## 業績の推移
   - 直近数期の売上・営業利益・純利益を「項目：値」形式で
## 株価と主要指標
   - 株価、時価総額、PER、PBR、配当利回りを「項目：値」形式で。同業他社とも比較する
## 強みと追い風
   - 2〜4個、それぞれ根拠となる数字とともに
## リスク要因
   - 2〜4個。競合、規制、為替、業績変動要因など具体的に
## まとめ
   - 強気に見るなら何が根拠か、慎重に見るなら何が懸念か、両論を整理
## 参照した情報源
   - 媒体名とURLを1行ずつ
## 免責事項
   - 下記の文言をそのまま記載する

【免責事項の文言（そのまま記載）】
本記事は特定の銘柄の売買を推奨するものではなく、情報提供を目的としています。記載の数値は執筆時点で公開されている情報にもとづきますが、正確性を保証するものではありません。投資判断はご自身の責任でお願いします。

【必須要素】
- 検索で裏付けた具体的な数値を10個以上
- 分量：3000〜4500文字

【無料で読める範囲について】
「この銘柄の要点」と「事業内容」までが無料で読める部分になる。
この2つだけでも読んで良かったと思える密度にしつつ、続きが気になる終わり方にすること。"""

# 1日1銘柄を解説する。日付でローテーションし、同じ銘柄が続かないようにする。
STOCKS = [
    {"name": "トヨタ自動車", "ticker": "7203", "market": "東証プライム", "image_keyword": "自動車"},
    {"name": "ソニーグループ", "ticker": "6758", "market": "東証プライム", "image_keyword": "ゲーム"},
    {"name": "三菱UFJフィナンシャル・グループ", "ticker": "8306", "market": "東証プライム", "image_keyword": "銀行"},
    {"name": "任天堂", "ticker": "7974", "market": "東証プライム", "image_keyword": "ゲーム"},
    {"name": "信越化学工業", "ticker": "4063", "market": "東証プライム", "image_keyword": "半導体"},
    {"name": "東京エレクトロン", "ticker": "8035", "market": "東証プライム", "image_keyword": "半導体"},
    {"name": "ファーストリテイリング", "ticker": "9983", "market": "東証プライム", "image_keyword": "アパレル"},
    {"name": "日立製作所", "ticker": "6501", "market": "東証プライム", "image_keyword": "工場"},
    {"name": "キーエンス", "ticker": "6861", "market": "東証プライム", "image_keyword": "工場"},
    {"name": "リクルートホールディングス", "ticker": "6098", "market": "東証プライム", "image_keyword": "オフィス"},
    {"name": "オリエンタルランド", "ticker": "4661", "market": "東証プライム", "image_keyword": "遊園地"},
    {"name": "武田薬品工業", "ticker": "4502", "market": "東証プライム", "image_keyword": "医薬品"},
    {"name": "NVIDIA", "ticker": "NVDA", "market": "NASDAQ", "image_keyword": "半導体"},
    {"name": "Apple", "ticker": "AAPL", "market": "NASDAQ", "image_keyword": "スマートフォン"},
    {"name": "Microsoft", "ticker": "MSFT", "market": "NASDAQ", "image_keyword": "パソコン"},
    {"name": "Alphabet", "ticker": "GOOGL", "market": "NASDAQ", "image_keyword": "検索"},
    {"name": "Amazon.com", "ticker": "AMZN", "market": "NASDAQ", "image_keyword": "物流倉庫"},
    {"name": "Meta Platforms", "ticker": "META", "market": "NASDAQ", "image_keyword": "SNS"},
    {"name": "Eli Lilly", "ticker": "LLY", "market": "NYSE", "image_keyword": "医薬品"},
    {"name": "Visa", "ticker": "V", "market": "NYSE", "image_keyword": "クレジットカード"},
    {"name": "Coca-Cola", "ticker": "KO", "market": "NYSE", "image_keyword": "飲料"},
    {"name": "Costco Wholesale", "ticker": "COST", "market": "NASDAQ", "image_keyword": "スーパーマーケット"},
]

def pick_stock_of_the_day(today: date) -> dict:
    """日付でローテーションし、毎日違う銘柄を選ぶ。"""
    return STOCKS[today.toordinal() % len(STOCKS)]


# タイトルの問いかけ。読者が知りたいことを見出しにする。
# 銘柄数(22)と互いに素な個数にして、銘柄と問いかけの組み合わせが長く一巡しないようにする。
TITLE_PATTERNS = [
    "{stock}、これからの展望は？",
    "{stock}は今どうなっている？業績と株価を追う",
    "{stock}の強みとリスクを整理する",
    "{stock}は何で稼いでいるのか",
    "{stock}、いま何が論点か",
    "{stock}の決算から見えてきたこと",
    "{stock}をゼロから理解する",
]


def build_title(stock: dict, today: date) -> str:
    pattern = TITLE_PATTERNS[today.toordinal() % len(TITLE_PATTERNS)]
    return f"【{stock['ticker']}】" + pattern.format(stock=stock["name"])


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
    return sanitize_article(article_content, title)


def sanitize_article(content: str, title: str) -> str:
    """noteで崩れる書式を投稿前に取り除く。

    システムプロンプトで禁止していても書式が混ざることがあり、そのまま入力すると
    記号がそのまま記事に表示されてしまうため、ここで最終的に整える。
    """
    cleaned = []
    removed = 0
    for raw in content.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        # タイトルの重複（本文冒頭の「# タイトル」）を落とす
        if stripped.lstrip("# ").strip() == title.strip():
            removed += 1
            continue
        # 有料エリアの案内や区切り線は内部的なものなので記事に出さない
        if "ここから有料" in stripped or set(stripped) <= {"＝", "=", "─", "-", "—", " "} and len(stripped) >= 3:
            removed += 1
            continue
        # 表は表示されないため、記号を外して読める形に直す
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= {"-", ":", " "} for c in cells):  # 表の区切り行
                removed += 1
                continue
            line = "：".join(c for c in cells if c)
        else:
            # 箇条書き記号を落とす
            line = re.sub(r"^\s*[-*・]\s+", "", line)
            line = re.sub(r"^\s*\d+\.\s+", "", line)

        # 強調・引用・コード記法を外す
        line = line.replace("**", "").replace("`", "")
        line = re.sub(r"^\s*>\s?", "", line)
        # 見出しの注釈（無料部分）などを外す
        if line.lstrip().startswith("#"):
            line = re.sub(r"（(無料|有料)部分）", "", line).rstrip()
        cleaned.append(line)

    # 連続する空行を1つにまとめる
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()
    if removed:
        logger.info(f"記事の整形: 不要な行を{removed}行削除")
    return result

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

# 有料エリアの境界はこの見出しの直前に置く。本文に余計な目印を残さないため、
# 記事の構成上必ず現れるこの見出しをアンカーとして使う。
PAYWALL_ANCHOR_HEADING = "業績の推移"


async def set_header_image(page, stock: dict) -> None:
    """記事の見出し画像を設定する。

    noteの「みんなのフォトギャラリー」から銘柄に合いそうな無料画像を選ぶ。
    画像がなくても記事自体は成立するため、失敗しても投稿は続行する。
    まずは画面構造を記録し、判明した手順で設定を試みる。
    """
    keyword = stock.get("image_keyword", "ビジネス")
    try:
        opened = await click_first(
            page,
            [
                'button:has-text("画像を追加")',
                'button:has-text("記事に画像を追加")',
                'button:has-text("見出し画像")',
                'figure button',
            ],
            "見出し画像の追加ボタン",
            timeout=6000,
        )
        if not opened:
            return
        await page.wait_for_timeout(2500)
        await log_visible_controls(page, "見出し画像の選択画面")

        await click_first(
            page,
            [
                'button:has-text("みんなのフォトギャラリー")',
                'a:has-text("みんなのフォトギャラリー")',
                'button:has-text("フォトギャラリー")',
            ],
            "みんなのフォトギャラリー",
            timeout=6000,
        )
        await page.wait_for_timeout(2500)
        await log_visible_controls(page, "フォトギャラリー画面")

        search = page.locator('input[type="text"], input[type="search"]').first
        await search.wait_for(state="visible", timeout=6000)
        await search.fill(keyword)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3500)

        thumbnail = page.locator('img').nth(3)
        await thumbnail.wait_for(state="visible", timeout=8000)
        await thumbnail.click()
        await page.wait_for_timeout(2000)
        await log_visible_controls(page, "画像選択後")

        await click_first(
            page,
            ['button:has-text("この画像を挿入")', 'button:has-text("保存")', 'button:has-text("適用")'],
            "画像の確定ボタン",
            timeout=6000,
        )
        await page.wait_for_timeout(3000)
        logger.info(f"見出し画像を設定（検索語: {keyword}）")
    except Exception as e:
        # 画像は記事の必須要素ではないため、失敗しても投稿を止めない
        logger.warning(f"見出し画像の設定をスキップします: {str(e)}")
        await log_visible_controls(page, "見出し画像の設定に失敗した時点")
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)
        except Exception:
            pass


async def type_article_body(page, content: str) -> None:
    """記事本文をnoteのエディタに入力する。

    noteのエディタは「## 」と打つと見出しに変わる入力補助を持つが、
    insert_text は貼り付け扱いになりこの変換が働かない（記号がそのまま残る）。
    そのため見出し記号だけは keyboard.type で1文字ずつ打ち、変換を発火させる。
    本文はそのまま insert_text で入れる（数千文字を1文字ずつ打つと極端に遅いため）。
    """
    heading_prefixes = ("#### ", "### ", "## ", "# ")
    lines = content.split("\n")
    headings = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            prefix = next((p for p in heading_prefixes if stripped.startswith(p)), None)
            if prefix:
                # noteの見出しは2段階しかないため、###以降も小見出しに寄せる
                marker = "# " if prefix == "# " else "## "
                await page.keyboard.type(marker, delay=30)
                await page.wait_for_timeout(60)
                await page.keyboard.insert_text(stripped[len(prefix):])
                headings += 1
            else:
                await page.keyboard.insert_text(stripped)
        if i < len(lines) - 1:
            await page.keyboard.press("Enter")

    logger.info(f"本文入力完了: {len(content)} 文字 / {len(lines)} 行 / 見出し {headings} 個")
    await page.wait_for_timeout(1500)


async def set_paywall_boundary(page) -> None:
    """有料エリアの境界（どこから有料か）を設定する。

    有料エリア設定画面では各段落の間に「ラインをこの場所に変更」ボタンが並んでおり、
    初期状態では境界が記事の先頭（＝全文が有料）にある。
    本文に目印の文字列を残すと記事にそのまま表示されてしまうため、
    有料部分の先頭にあたる見出しをアンカーにして、その直前のボタンを押す。
    """
    info = await page.evaluate(
        """(anchor) => {
            const buttons = Array.from(document.querySelectorAll('button'))
                .filter(b => (b.innerText || '').trim() === 'ラインをこの場所に変更');
            // 見出し要素のうち、アンカー文言を含む最も内側のものを探す
            const candidates = Array.from(
                document.querySelectorAll('h1, h2, h3, h4, p, div, span')
            ).filter(el => (el.innerText || '').trim().includes(anchor));
            const anchorEl = candidates.find(
                el => !candidates.some(other => other !== el && el.contains(other))
            );
            if (!anchorEl) {
                return {index: -1, candidates: candidates.length, buttons: buttons.length};
            }
            // アンカーより前にあるボタンのうち、最も後ろのもの＝見出しの直前
            let index = -1;
            buttons.forEach((b, i) => {
                if (anchorEl.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_PRECEDING) {
                    index = i;
                }
            });
            return {
                index,
                candidates: candidates.length,
                buttons: buttons.length,
                anchorTag: anchorEl.tagName,
                anchorText: (anchorEl.innerText || '').trim().slice(0, 40),
            };
        }""",
        PAYWALL_ANCHOR_HEADING,
    )
    logger.info(f"有料エリアのアンカー解析結果: {info}")
    index = info.get("index", -1)
    if index < 0:
        raise Exception(
            f"有料部分の先頭となる見出し（{PAYWALL_ANCHOR_HEADING}）が本文に見つからず、"
            "境界を設定できませんでした"
        )
    # アンカーは記事の中盤にあるはずなので、先頭付近なら解析ミスとみなす
    if index < 2:
        raise Exception(
            f"有料エリアの境界が記事の先頭付近（{index}番目）と判定されました。"
            "全文有料での公開を避けるため中断します"
        )

    button = page.locator('button:has-text("ラインをこの場所に変更")').nth(index)
    await button.click()
    logger.info(f"有料エリアの境界を「{PAYWALL_ANCHOR_HEADING}」の直前（{index}番目）に設定")
    await page.wait_for_timeout(2000)

    # 境界がアンカーより前に移動したかを確認する。失敗すると全文有料で公開されてしまう。
    result = await page.evaluate(
        """(anchor) => {
            const lines = Array.from(document.querySelectorAll('*'))
                .filter(el => (el.innerText || '').trim() === 'このラインより先を有料にする');
            const line = lines.find(
                el => !lines.some(other => other !== el && el.contains(other))
            );
            const candidates = Array.from(
                document.querySelectorAll('h1, h2, h3, h4, p, div, span')
            ).filter(el => (el.innerText || '').trim().includes(anchor));
            const anchorEl = candidates.find(
                el => !candidates.some(other => other !== el && el.contains(other))
            );
            if (!line || !anchorEl) return {ok: false, reason: '要素が見つからない'};
            const before = Boolean(
                anchorEl.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_PRECEDING
            );
            const body = document.body.innerText || '';
            const pos = body.indexOf(anchor);
            return {ok: before, freeRatio: pos > 0 ? pos / body.length : null};
        }""",
        PAYWALL_ANCHOR_HEADING,
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

            await set_header_image(page, stock)

            # 本文入力
            logger.info("本文入力中...")
            body = page.locator('div[contenteditable="true"]').first
            await body.wait_for(state="visible", timeout=15000)
            await body.click()
            await page.wait_for_timeout(300)

            await type_article_body(page, content)

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
        today = date.today()
        stock = pick_stock_of_the_day(today)
        title = build_title(stock, today)
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
