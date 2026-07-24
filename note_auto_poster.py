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

async def post_to_note(email: str, password: str, title: str, content: str) -> bool:
    """Playwrightを使用してnoteに投稿"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            logger.info("noteログインページにアクセス中...")
            await page.goto("https://note.com/login", wait_until="networkidle")

            # ログイン
            logger.info("ログイン中...")
            await page.fill('input[type="email"]', email)
            await page.fill('input[type="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            # ホームページでログイン確認
            if "login" in page.url:
                logger.error("ログイン失敗")
                return False

            logger.info("ログイン成功")

            # 新規投稿ページへ
            logger.info("新規投稿ページにアクセス中...")
            await page.goto("https://note.com/my/notes/create", wait_until="networkidle")

            # タイトル入力
            logger.info("タイトル入力中...")
            await page.fill('input[placeholder*="タイトル"], textarea[placeholder*="タイトル"]', title)
            await page.wait_for_timeout(500)

            # 本文入力
            logger.info("本文入力中...")
            # noteのエディタは複数存在する可能性があるので、複数試行
            content_selectors = [
                'div[contenteditable="true"]',
                'textarea[placeholder*="本文"], textarea[placeholder*="内容"]',
                '.editor-content'
            ]

            for selector in content_selectors:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 1:  # 本文は通常2番目のエディタ
                    await elements[1].click()
                    await page.keyboard.type(content, delay=1)
                    break

            await page.wait_for_timeout(1000)

            # 価格設定（1,000円）
            logger.info("価格設定中...")
            # 有料化ボタンを探す
            paid_button = await page.query_selector('button:has-text("有料化")')
            if paid_button:
                await paid_button.click()
                await page.wait_for_timeout(500)

                # 価格入力
                price_input = await page.query_selector('input[placeholder*="価格"], input[type="number"]')
                if price_input:
                    await price_input.fill("1000")

            await page.wait_for_timeout(500)

            # 投稿ボタンをクリック
            logger.info("投稿中...")
            publish_button = await page.query_selector('button:has-text("投稿")')
            if publish_button:
                await publish_button.click()
                await page.wait_for_load_state("networkidle")

            logger.info("投稿完了")
            return True

        except Exception as e:
            logger.error(f"投稿エラー: {str(e)}")
            return False
        finally:
            await browser.close()

async def main():
    """メイン処理"""
    try:
        # 環境変数確認
        note_email = os.environ.get('NOTE_EMAIL')
        note_password = os.environ.get('NOTE_PASSWORD')

        if not note_email or not note_password:
            logger.error("NOTE_EMAIL または NOTE_PASSWORD が設定されていません")
            return False

        # トピック選択（ランダムまたはスケジュール）
        import random
        topic = random.choice(INVESTMENT_TOPICS)

        # 記事生成
        content = await generate_article(topic)

        # noteに投稿
        success = await post_to_note(note_email, note_password, topic['title'], content)

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
