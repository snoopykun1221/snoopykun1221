"""post_to_note を偽のブラウザで最後まで通し、引数の受け渡しミスを検出する。"""
import asyncio, sys, types
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
sys.modules['anthropic'] = types.ModuleType('anthropic')
d = types.ModuleType('dotenv'); d.load_dotenv = lambda *a, **k: None
sys.modules['dotenv'] = d

visited = []

class FakeLocator:
    def __init__(self, sel=""): self.sel = sel
    @property
    def first(self): return self
    def nth(self, i): return self
    async def wait_for(self, **k): pass
    async def click(self, **k): visited.append(f"click:{self.sel}")
    async def fill(self, v): visited.append(f"fill:{self.sel}")
    async def input_value(self):
        import note_auto_poster
        return note_auto_poster.ARTICLE_PRICE
    async def inner_text(self): return "本文"
    async def is_enabled(self): return True

class FakeKeyboard:
    async def type(self, t, delay=None): visited.append(f"type:{t!r}")
    async def insert_text(self, t): pass
    async def press(self, k): pass

class FakePage:
    url = "https://editor.note.com/notes/xxx/edit/"
    keyboard = FakeKeyboard()
    def locator(self, sel): return FakeLocator(sel)
    def on(self, *a): pass
    async def goto(self, *a, **k): pass
    async def wait_for_url(self, *a, **k): pass
    async def wait_for_timeout(self, *a): pass
    async def reload(self, **k): pass
    async def content(self): return "<html></html>"
    async def screenshot(self, **k): pass
    async def evaluate(self, script, *args):
        if "ラインをこの場所に変更" in script and "index" in script:
            return {"index": 9, "candidates": 1, "buttons": 40,
                    "anchorTag": "H2", "anchorText": "数字で見る、いまの実力"}
        if "このラインより先を有料にする" in script:
            return {"ok": True, "freeRatio": 0.35}
        if "is_paid" in script:
            return True
        if "headingTags" in script:
            return {"headingTags": 4, "headingSamples": [], "literalHeadings": 0,
                    "pipeLines": 0, "boldMarks": 0, "paywallLeak": 0, "freeLabel": 0,
                    "titleDup": 0, "headerImage": 1, "chars": 3500, "firstBlocks": []}
        return []

class FakeCtx:
    async def new_page(self): return FakePage()
class FakeBrowser:
    async def new_context(self, **k): return FakeCtx()
    async def close(self): pass
class FakeChromium:
    async def launch(self, **k): return FakeBrowser()
class FakePW:
    chromium = FakeChromium()
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass

pw = types.ModuleType('playwright'); api = types.ModuleType('playwright.async_api')
api.async_playwright = lambda: FakePW()
sys.modules['playwright'] = pw; sys.modules['playwright.async_api'] = api

import note_auto_poster as n
open('/tmp/sess.json','w').write('{}')

stock = n.pick_stock_of_the_day(__import__('datetime').date(2026,7,26))
title = n.build_title(stock, __import__('datetime').date(2026,7,26))
body = (
    "## 結論から言うと\n要するにこういう会社です。\n\n"
    "## そもそも、どんな会社なのか\n売上高：1兆円\n\n"
    "## 数字で見る、いまの実力\n増収です。\n\n"
    "## まとめ\n以上です。"
)

n.PUBLISH_MODE = "publish"
ok = asyncio.run(n.post_to_note('/tmp/sess.json', stock, title, body))
print("\n投稿処理の結果:", ok)
assert ok, "投稿処理が完走しなかった"
assert any("投稿する" in v for v in visited), "公開ボタンが押されていない"
print("通しテスト成功: 引数の受け渡しに問題なし")
