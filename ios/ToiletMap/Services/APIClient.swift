import Foundation
import MapKit

final class APIClient {
    static let shared = APIClient()

    private struct Search: Encodable {
        let aggregate = true
        let keyword: String?
        let gender: [String]
        let toiletTypes: [String]
        let hasDiaperTable: Bool?
        var bbox: String?
        var limit: Int?
        var lat: Double?
        var lng: Double?
        var radiusM: Int?

        init(filters: ToiletQueryFilters) {
            keyword = filters.keyword.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? nil : filters.keyword
            gender = ToiletQueryFilters.Gender.allCases.filter { filters.genders.contains($0) }
                .map(\.rawValue)
            toiletTypes = filters.accessibleOnly ? ["accessible"] : []
            hasDiaperTable = filters.diaperTableOnly ? true : nil
        }
    }

    private let baseURL = RuntimeConfig.apiBaseURL
    private let resultLimit = 200
    private let session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 15
        configuration.timeoutIntervalForResource = 30
        return URLSession(configuration: configuration)
    }()

    private func fetch(_ path: String, search: Search) async throws -> [ToiletMapItem] {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(search)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ToiletsResponse.self, from: data).items
    }

    func fetchToilets(filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        var search = Search(filters: filters)
        search.limit = resultLimit
        return try await fetch("/v1/toilets", search: search)
    }

    func fetchToiletsInViewport(region: MKCoordinateRegion, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        let minLng = region.center.longitude - (region.span.longitudeDelta / 2)
        let maxLng = region.center.longitude + (region.span.longitudeDelta / 2)
        let minLat = region.center.latitude - (region.span.latitudeDelta / 2)
        let maxLat = region.center.latitude + (region.span.latitudeDelta / 2)

        var search = Search(filters: filters)
        search.bbox = "\(minLng),\(minLat),\(maxLng),\(maxLat)"
        search.limit = resultLimit
        return try await fetch("/v1/toilets", search: search)
    }

    func fetchNearby(lat: Double, lng: Double, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        var search = Search(filters: filters)
        search.lat = lat
        search.lng = lng
        search.radiusM = 1500
        return try await fetch("/v1/toilets/nearby", search: search)
    }
}
