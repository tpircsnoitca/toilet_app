import Foundation

enum RuntimeConfig {
    // Set this in Info.plist as API_BASE_URL.
    // Example: http://192.168.1.88:8000
    static var apiBaseURL: URL {
        if let value = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
           let url = URL(string: value),
           !value.isEmpty {
            return url
        }

        // Safe fallback for local simulator if key is missing.
        return URL(string: "http://127.0.0.1:8000")!
    }
}
