import json
import os
from flask import Flask, render_template, request, Response, stream_with_context
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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

【読者に価値を感じさせる工夫】
- 無料部分の最後で「この続きに、私だから儲かった理由がある」と期待を持たせる
- 有料部分は「実際の取引記録」「タイミングの判断基準」など、真似できる具体性を持たせる
- 結末で「明日からできるアクション」を1つ示す

【図・表を効果的に使う】
- 買値・売値・利益をMarkdownの表で見える化（| 銘柄 | 買値 | 売値 | 利益 |）
- 投資判断の流れを矢印で図解（例：ニュース → 分析 → エントリー → 決済 → 利益100万円）
- チャート・スクリーンショット指示：【画像：◯◯株の買値時点のチャート】のように具体的に

【構造（必ずこの順番で）】
1. # タイトル（与えられたタイトルをそのまま使う）
2. ## 読む前に（無料部分）
   - 「普通のOLと違う」というフック
   - 失敗・損失経験で共感を作る
   - 「それでも読んでくれるなら、実際にやった方法を全部書く」で締める
3. ## [結果の概要]（無料部分）
   例：「給料の○倍を短期間で稼いだ仕組み」など
   - 具体的な利益（例：月給の3倍、年間200万円など）
   - 実装期間（例：3ヶ月で軌道に乗った）

4. ＝＝＝＝＝ ここから有料エリア ＝＝＝＝＝
5. ## [実体験セクション]（有料部分）×3〜5個
   例：「月給25万円の私が最初に100万円を用意した方法」
   - 具体的な金額・数字・銘柄名を含める
   - 実際の心理状態（怖かったこと、迷ったこと）を描写
   - 表や図解を1つ以上含める
   - 「なぜそう判断したのか」の背景を書く

6. ## 私が失敗した話（最重要）
   - 具体的な損失例を2〜3個
   - 「あの時こうしていれば」という悔しさと学習
   - 今だからわかる教訓

7. ## 同僚にはまだ言えない本音
   - OLとしての立場の話
   - なぜこっそり投資しているのか
   - お金の価値観の違い

8. ## まとめ
   - 次に買う銘柄/やってみるべきアクション
   - 読者へのメッセージ

【必須要素】
- 具体的な数字を合計12個以上（金額・利益・損失・銘柄株価・時間など）
- 失敗談を最低2つ（損失額も明記）
- 成功例を最低2つ（実利益を明記）
- 表または図解を2つ以上
- 「私だからこそ」という個性的な視点が3回以上
- 感情的な描写（怖かった、嬉しかった、悔しかった）
- 分量：3500〜5000文字

【投資ジャンル別のポイント】
- 日本株：銘柄コード・業種・チャートパターンを具体化
- 米国株：ティッカー・ETF名・為替の影響を具体化
- 仮想通貨：コイン名・チャート・リスク管理の工夫を具体化
- FX：通貨ペア・レート・レバレッジの使い方を具体化

記事は「同じOLとして真似したい」「この人の次の記事も読みたい」と思わせることが最優先。"""

@app.route('/')
def index():
    has_api_key = bool(os.environ.get('ANTHROPIC_API_KEY'))
    return render_template('note_generator.html', has_api_key=has_api_key)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    title = (data.get('title') or '').strip()
    keywords = [k.strip() for k in data.get('keywords', []) if k.strip()]
    overview = (data.get('overview') or '').strip()
    episodes = (data.get('episodes') or '').strip()
    structure = (data.get('structure') or '').strip()
    target = (data.get('target') or '').strip()
    model = (data.get('model') or '').strip() or 'claude-opus-4-8'
    user_api_key = (data.get('api_key') or '').strip()

    if not title:
        return Response(
            f"data: {json.dumps({'error': 'タイトルを入力してください'})}\n\n",
            mimetype='text/event-stream'
        )

    api_key = os.environ.get('ANTHROPIC_API_KEY') or user_api_key
    if not api_key:
        return Response(
            f"data: {json.dumps({'error': 'APIキーを入力してください'})}\n\n",
            mimetype='text/event-stream'
        )

    keywords_str = '、'.join(keywords) if keywords else 'なし'
    user_prompt = f"以下の条件でnote有料記事（1,000円）を書いてください。\n\n記事タイトル：{title}\n関連キーワード・テーマ：{keywords_str}"
    if target:
        user_prompt += f"\nターゲット読者：{target}"
    if overview:
        user_prompt += f"\n\n記事の概要・伝えたいこと：\n{overview}"
    if episodes:
        user_prompt += f"\n\n含めたいエピソード・体験談：\n{episodes}"
    if structure:
        user_prompt += f"\n\n章立て（この構成を参考にしてください）：\n{structure}"
    user_prompt += "\n\n上記の内容に忠実に、体験談ベースのリアルな記事を生成してください。架空でも構いませんが、リアリティのある具体的な数字・エピソードを入れてください。"

    def stream():
        # Safariは2KB未満だとバッファに溜めて表示しないため冒頭にパディングを送る
        yield ': ' + ' ' * 2048 + '\n\n'
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with client.messages.stream(
                model=model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            ) as s:
                for text in s.text_stream:
                    yield f"data: {json.dumps({'chunk': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'APIキーが無効です。正しいAnthropicのAPIキーを入力してください'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
