import SwiftUI

struct SettingsView: View {
    var body: some View {
        List {
            Section("資料來源") {
                Text("環境部公廁查詢")
                Link("開啟資料來源網站", destination: URL(string: "https://esms.moenv.gov.tw/eco/toilet/FindToilet.aspx?openExternalBrowser=1")!)
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
