import SwiftUI

@main
struct ToiletMapApp: App {
    @State private var showMap = false

    var body: some Scene {
        WindowGroup {
            Group {
                if showMap {
                    MapHomeView()
                } else {
                    ToiletLoadingScreen()
                }
            }
            .environment(\.locale, Locale(identifier: "zh-Hant-TW"))
            .task {
                // Give the lightweight app shell an opportunity to render before constructing MapKit.
                await Task.yield()
                showMap = true
            }
        }
    }
}
