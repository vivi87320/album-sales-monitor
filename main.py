import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import traceback

# ===== 1. GitHub 安全認證設定 =====
def get_gspread_client():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        print("❌ 錯誤：找不到 GOOGLE_CREDENTIALS 環境變數")
        return None
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# ===== 2. 抓取資料邏輯 =====
def fetch_inventory(url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kmonstar.com.tw/"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    quantities = []
    titles = []
    for v in data.get("variants", []):
        titles.append(v.get("title", "無名"))
        quantities.append(v.get("inventory_quantity"))
    return quantities, titles

# ===== 3. 主程式 =====
def main():
    print("🚀 開始執行監測任務...")
    SHEET_ID = "1CIsh1bN92x7DlgHdsfohA2cJk13f5a-lWz2egVonYlk"
    
    try:
        client = get_gspread_client()
        if not client: return
        sh = client.open_by_key(SHEET_ID)
        
        # 讀取 Settings
        settings_ws = sh.worksheet("Settings")
        targets = settings_ws.get_all_records()
        print(f"清單讀取成功，共有 {len(targets)} 個監控目標")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for target in targets:
            api_url = target.get("網址")
            sheet_name = target.get("分頁名稱")
            if not api_url or not sheet_name: continue

            print(f"🔎 正在處理: {sheet_name}")
            quantities, titles = fetch_inventory(api_url)

            # 開啟分頁 (不存在則建立)
            try:
                worksheet = sh.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
                print(f"🆕 建立新分頁: {sheet_name}")

            # 檢查最後一行，決定是否寫入
            all_values = worksheet.get_all_values()
            last_row = all_values[-1][1:] if len(all_values) > 1 else None
            current_data = [str(q) for q in quantities]

            if last_row != current_data:
                worksheet.append_row([now_str] + quantities)
                print(f"✅ 數據已更新: {current_data}")
            else:
                print("⏳ 數據相同，跳過寫入")
            
            time.sleep(2)

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        traceback.print_exc()

# !!! 這兩行絕對不能漏掉，否則程式不會跑 !!!
if __name__ == "__main__":
    main()
