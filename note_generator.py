import json
import os
from flask import Flask, render_template, request, Response, stream_with_context
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SYSTEM_PROMPT = """あなたはnoteで有料記事（1,000円）を月20本以上販売している実力派ライターです。
体験談ベースの文体で、読者が「お金を払ってよかった」と感じる記事を書いてください。

【絶対に守るルール】
- 一人称は「自分」で統一
- 文末は「〜だった」「〜した」「〜だと思う」の体験談調
- 「！」「✓」「🎉」などの記号・絵文字は使わない
- 「〜しましょう」「〜ください」という上から目線は避ける

【構造（必ずこの順番で）】
1. # タイトル（与えられたタイトルをそのまま使う）
2. ## 読む前に（無料部分）
   - 「よくある話じゃないですよ」という掴み
   - 失敗・挫折エピソードで共感を作る
   - 「それでも読んでくれるなら全部書く」で締める
3. ## [全体像を示すセクション名]（無料部分）
   - 何を自動化/達成したかの概要
   - 具体的な数字（金額・時間・件数など）を必ず入れる
4. ＝＝＝＝＝ ここから有料エリア ＝＝＝＝＝
5. ## [具体的な手順セクション]（有料部分）×3〜5個
   - 各セクションに具体的な数字・コード・手順を含める
   - 「なぜそうするか」の理由も書く
6. ## 失敗談と教訓
   - 具体的な失敗を2〜3個
7. ## まとめ
   - 行動できる一言で締める

【必須要素】
- 具体的な数字を合計10個以上（金額・時間・割合・回数など）
- 失敗談を最低2つ
- 「自分はこうだった」という実体験の描写
- 分量：3500〜5000文字

キーワードに関連する具体的なツール名・サービス名・金額を入れると説得力が増します。"""

@app.route('/')
def index():
    has_api_key = bool(os.environ.get('ANTHROPIC_API_KEY'))
    return render_template('note_generator.html', has_api_key=has_api_key)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    title = (data.get('title') or '').strip()
    keywords = [k.strip() for k in data.get('keywords', []) if k.strip()]
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
    user_prompt = f"""以下の条件でnote有料記事（1,000円）を書いてください。

記事タイトル：{title}
関連キーワード・テーマ：{keywords_str}

タイトルとキーワードに忠実に、体験談ベースのリアルな記事を生成してください。
架空でも構いませんが、リアリティのある具体的な数字・エピソードを入れてください。"""

    def stream():
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
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
        }
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
