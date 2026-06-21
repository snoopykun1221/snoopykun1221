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
- 抽象論・一般論を避け、必ず「いつ・いくら・何を・何回」など固有の数字と固有名詞で語る
- どこかで読んだような当たり障りのない内容は書かない。生々しいディテールを入れる

【読者に価値を感じさせる工夫】
- 無料部分の最後で「この続きに具体的な方法がある」と期待を持たせる
- 有料部分は「これは有料で読む価値がある」と思える密度にする
- 読者がそのまま真似できるレベルまで具体化する

【図・表を効果的に使う】
情報を整理した方が伝わる箇所では、文章だけでなく以下を積極的に使うこと。
- 比較・一覧はMarkdownの表（| 項目 | 値 |）にする
- 手順やお金の流れは矢印を使った図解にする（例：仕入れ3,000円 → 販売5,000円 → 利益2,000円）
- 画像があると分かりやすい箇所には【画像：◯◯のスクリーンショット】のように具体的な指示を1行で挿入する

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
   - 表や図解を1つ以上含める
   - 「なぜそうするか」の理由も書く
6. ## 失敗談と教訓
   - 具体的な失敗を2〜3個
7. ## まとめ
   - 行動できる一言で締める

【必須要素】
- 具体的な数字を合計10個以上（金額・時間・割合・回数など）
- 失敗談を最低2つ
- 表または図解を1つ以上
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
