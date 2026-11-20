import SwiftUI

struct SettingsView: View {
    var body: some View {
        List {
            Section("資料來源") {
                Text("公廁資料由環境部環境管理署提供，取自環境衛生管理資訊系統公廁查詢，經本服務整理與彙整。")
                Link("環境衛生管理資訊系統公廁查詢", destination: URL(string: "https://esms.moenv.gov.tw/eco/toilet/FindToilet.aspx?openExternalBrowser=1")!)
                Link("環境部網站資料開放宣告", destination: URL(string: "https://www.moenv.gov.tw/announcement/publicdeclare/913.html")!)
                Link("全國公廁建檔資料", destination: URL(string: "https://data.gov.tw/dataset/30794")!)
                Text("全國公廁建檔資料依政府資料開放授權條款第 1 版釋出。")
                Link("政府資料開放授權條款第 1 版", destination: URL(string: "https://data.gov.tw/license")!)
            }

            Section("服務範圍") {
                Text("臺北市")
                Text("新北市")
            }

            #if DEBUG
            Section("開發用伺服器") {
                Text(RuntimeConfig.apiBaseURL.absoluteString)
                    .textSelection(.enabled)
            }
            #endif
        }
        .navigationTitle("設定")
    }
}
