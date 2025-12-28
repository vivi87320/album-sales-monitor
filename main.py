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
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # 從 GitHub Secrets 讀取憑證內容
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError("❌ 錯誤：找不到 GOOGLE_CREDENTIALS，請檢查 GitHub Secrets 設定！")
    
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# ===== 2. 抓取 Kmonstar 資料邏輯 =====
def fetch_inventory(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.kmonstar.com.tw/"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()

    quantities = []
    titles = []

    for v in data.get("variants", []):
        titles.append(v.get("title", "無名"))
        quantities.append(v.get("inventory_quantity"))

    return quantities, titles

# ===== 3. 主程式邏輯 (GitHub Actions 模式) =====
def main():
    SHEET_ID = "1CIsh1bN92x7DlgHdsfohA2cJk13f5a-lWz2egVonYlk" # 你的試算表 ID
    client = get_gspread_client()
    sh = client.open_by_key(SHEET_ID)

    # A. 從 Settings 分頁讀取要監測的網址清單
    try:
        settings_ws = sh.worksheet("Settings")
        targets = settings_ws.get_all_records() # 抓取所有列，欄位需為「網址」和「分頁名稱」
    except Exception as e:
        print(f"❌ 無法讀取 Settings 分頁: {e}")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for target in targets:
        api_url = target.get("網址")
        sheet_name = target.get("分頁名稱")

        if not api_url or not sheet_name:
            continue

        print(f"🚀 正在處理: {sheet_name}")

        try:
            # 1. 抓取數據
            quantities, titles = fetch_inventory(api_url)
            
            # 2. 開啟或建立對應的分頁
            try:
                worksheet = sh.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                # 如果分頁不存在，就自動建立一個
                worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
                print(f"🆕 已建立新分頁: {sheet_name}")

            # 3. 檢查並建立表頭 (如果第一格是空的)
            first_row = worksheet.row_values(1)
            if not first_row or first_row[0] != "時間":
                worksheet.insert_row(["時間"] + titles, 1)

            # 4. 判斷是否需要寫入 (比對最後一行數據)
            all_values = worksheet.get_all_values()
            last_row = all_values[-1] if len(all_values) > 1 else None
            
            # 將目前數據轉為字串方便比對
            current_data_strings = [str(q) for q in quantities]
            
            # 只有當數據與最後一行不同時，才寫入 (GitHub Actions 本身就一小時跑一次，不需強制寫入判斷)
            if last_row is None or last_row[1:] != current_data_strings:
                worksheet.append_row([now_str] + quantities)
                print(f"✅ [{sheet_name}] 數據已更新：{quantities}")
            else:
                print(f"⏳ [{sheet_name}] 數據無變動，跳過")

            # 禮貌性休息，避免被封鎖
            time.sleep(2)

        except Exception as e:
            print(f"❌ 處理 {sheet_name} 時發生錯誤: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
