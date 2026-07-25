"""
note.comへの自動ログイン用セッション（Cookie）を一度だけ手動で作成するスクリプト。

reCAPTCHAが表示されるため、自動投稿スクリプトでは毎回のログインを自動化せず、
このスクリプトでブラウザを表示し、あなた自身の手でログインしてもらう。
ログイン完了後、セッション情報を note_session.json に保存する。

使い方:
    python note_login_setup.py

セッションの有効期限が切れたら（数週間〜数ヶ月ごと）、再度このスクリプトを実行する。
"""
import asyncio
from playwright.async_api import async_playwright

SESSION_FILE = "note_session.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://note.com/login")

        print("\nブラウザが開きました。")
        print("表示された画面で、ご自身のメールアドレスとパスワードを入力してログインしてください。")
        print("reCAPTCHAが出た場合もそのまま手動で完了してください。")
        input("\nログインが完了したら、このターミナルに戻ってEnterキーを押してください... ")

        await page.goto("https://note.com/", wait_until="networkidle")

        if "login" in page.url:
            print("\n❌ まだログインページにいます。ログインが完了しているか確認してから、もう一度お試しください。")
            await browser.close()
            return

        await context.storage_state(path=SESSION_FILE)
        print(f"\n✅ セッションを {SESSION_FILE} に保存しました。")
        print("このファイルの内容をGitHub Secretsの NOTE_SESSION_STATE に登録してください。")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
