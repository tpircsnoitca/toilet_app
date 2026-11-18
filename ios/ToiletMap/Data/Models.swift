import Foundation

struct ToiletMapItem: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let city: String
    let district: String
    let address: String?
    let lat: Double
    let lng: Double
    let toiletTypes: [String]
    let hasMenToilet: Bool?
    let hasWomenToilet: Bool?
    let hasDiaperTable: Bool
    let openNow: Bool?
    let openLabel: String
    let distanceM: Int?
    var sourceCount: Int? = nil
    var groupKind: String? = nil
    var aggregationVersion: String? = nil
    var sourceRecords: [ToiletMapItem]? = nil
    var matchingSourceIds: [String]? = nil
    var symbolSources: [String: [String]]? = nil
    var building: String? = nil
    var floor: String? = nil
}

struct ToiletsResponse: Codable {
    let items: [ToiletMapItem]
    let total: Int
}

extension ToiletMapItem {
    var hasAccessibleToilet: Bool {
        toiletTypes.contains("accessible")
    }

    var availabilityLabel: String {
        switch openNow {
        case true: return (sourceCount ?? 1) > 1 ? "目前有廁所開放" : "目前開放"
        case false: return "目前未開放"
        default: return "開放狀態不明"
        }
    }

    var todayHoursLabel: String {
        ToiletHoursText.format(openLabel)
    }

    var floorLabel: String? {
        guard let floor else { return nil }
        let code = floor.uppercased()
        if code.range(of: #"^B\d+F?$"#, options: .regularExpression) != nil {
            let number = code.dropFirst().prefix(while: \.isNumber)
            return "地下 \(number) 樓"
        }
        if code.range(of: #"^\d+F$"#, options: .regularExpression) != nil {
            return "\(code.dropLast()) 樓"
        }
        return floor
    }

    var hasMenToiletResolved: Bool {
        if let hasMenToilet {
            return hasMenToilet
        }
        return toiletTypes.contains("male")
    }

    var hasWomenToiletResolved: Bool {
        if let hasWomenToilet {
            return hasWomenToilet
        }
        return toiletTypes.contains("female")
    }

    var toiletTypeLabels: [String] {
        toiletTypes.map {
            switch $0 {
            case "male":
                return "男廁"
            case "female":
                return "女廁"
            case "family":
                return "親子廁所"
            case "accessible":
                return "無障礙廁所"
            case "mixed":
                return "男女共用"
            case "gender_friendly":
                return "性別友善"
            default:
                return "類型不明"
            }
        }
    }

    var menWomenIndicator: String {
        switch (hasMenToiletResolved, hasWomenToiletResolved) {
        case (true, true):
            return "有男廁及女廁"
        case (true, false):
            return "僅男廁"
        case (false, true):
            return "僅女廁"
        default:
            return toiletTypes.contains("gender_friendly") ? "性別友善" : "未標示性別"
        }
    }
}

// A viewport-sized grid keeps annotation work bounded without changing the API
// results. Same-coordinate records stay selectable in the panel at every zoom.
struct ToiletMarkerGroup: Identifiable {
    let items: [ToiletMapItem]
    var id: String { items.map(\.id).sorted().joined(separator: "|") }
    var lat: Double { items.map(\.lat).reduce(0, +) / Double(items.count) }
    var lng: Double { items.map(\.lng).reduce(0, +) / Double(items.count) }

    private struct Cell: Hashable {
        let row: Int
        let column: Int
    }

    static func groups(_ items: [ToiletMapItem], latitudeSpan: Double, longitudeSpan: Double,
                       width: Double, height: Double) -> [ToiletMarkerGroup] {
        guard latitudeSpan > 0, longitudeSpan > 0, width > 0, height > 0 else {
            return items.sorted { $0.id < $1.id }.map { ToiletMarkerGroup(items: [$0]) }
        }
        let latitudeStep = max(latitudeSpan * 52 / height, 0.0000001)
        let longitudeStep = max(longitudeSpan * 52 / width, 0.0000001)
        let buckets = Dictionary(grouping: items) {
            Cell(row: Int(floor($0.lat / latitudeStep)), column: Int(floor($0.lng / longitudeStep)))
        }
        return buckets.values.map { ToiletMarkerGroup(items: $0.sorted { $0.id < $1.id }) }
            .sorted { $0.id < $1.id }
    }
}

enum ToiletHoursText {
    static func format(_ label: String) -> String {
        switch label {
        case "Open 24 hours": return "全天開放"
        case "Hours vary by toilet": return "各廁所開放時間不同"
        default:
            let overnightSuffix = " (next day)"
            let overnight = label.hasSuffix(overnightSuffix)
            let range = overnight ? String(label.dropLast(overnightSuffix.count)) : label
            guard range.range(of: #"^\d{2}:\d{2}–\d{2}:\d{2}$"#, options: .regularExpression) != nil else {
                return "未提供開放時間"
            }
            return overnight ? "\(range)（跨日）" : range
        }
    }
}

enum ToiletDistanceText {
    static func format(meters: Double, usesUserLocation: Bool,
                       language: String = "zh-Hant-TW") -> String {
        let locale = Locale(identifier: language)
        let traditionalChinese = locale.language.languageCode?.identifier == "zh" &&
            locale.language.script?.identifier == "Hant"
        let distance: String
        if meters < 1000 {
            distance = "\(Int(meters.rounded())) \(traditionalChinese ? "公尺" : "m")"
        } else {
            distance = String(format: "%.1f", locale: Locale(identifier: "en_US_POSIX"), meters / 1000) +
                " \(traditionalChinese ? "公里" : "km")"
        }
        if traditionalChinese {
            return usesUserLocation ? "距離 \(distance)" : "距離地圖中心 \(distance)"
        }
        return "\(distance) \(usesUserLocation ? "away" : "from map center")"
    }
}
