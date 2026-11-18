import Foundation
import MapKit

final class APIClient {
    static let shared = APIClient()

    private let baseURL = RuntimeConfig.apiBaseURL
    private let resultLimit = "200"
    private let session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 15
        configuration.timeoutIntervalForResource = 30
        return URLSession(configuration: configuration)
    }()

    private func buildCommonQueryItems(filters: ToiletQueryFilters) -> [URLQueryItem] {
        var queryItems = [URLQueryItem(name: "aggregate", value: "true")]

        if !filters.keyword.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            queryItems.append(URLQueryItem(name: "keyword", value: filters.keyword))
        }
        for gender in ToiletQueryFilters.Gender.allCases where filters.genders.contains(gender) {
            queryItems.append(URLQueryItem(name: "gender", value: gender.rawValue))
        }
        if filters.diaperTableOnly {
            queryItems.append(URLQueryItem(name: "has_diaper_table", value: "true"))
        }
        if filters.accessibleOnly {
            queryItems.append(URLQueryItem(name: "toilet_types", value: "accessible"))
        }

        return queryItems
    }

    func fetchToilets(filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("/v1/toilets"),
            resolvingAgainstBaseURL: false
        )
        var queryItems = buildCommonQueryItems(filters: filters)
        queryItems.append(URLQueryItem(name: "limit", value: resultLimit))
        components?.queryItems = queryItems

        guard let url = components?.url else {
            throw URLError(.badURL)
        }

        let (data, _) = try await session.data(from: url)
        let decoded = try JSONDecoder().decode(ToiletsResponse.self, from: data)
        return decoded.items
    }

    func fetchToiletsInViewport(region: MKCoordinateRegion, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("/v1/toilets"),
            resolvingAgainstBaseURL: false
        )
        var queryItems = buildCommonQueryItems(filters: filters)

        let minLng = region.center.longitude - (region.span.longitudeDelta / 2)
        let maxLng = region.center.longitude + (region.span.longitudeDelta / 2)
        let minLat = region.center.latitude - (region.span.latitudeDelta / 2)
        let maxLat = region.center.latitude + (region.span.latitudeDelta / 2)
        let bbox = "\(minLng),\(minLat),\(maxLng),\(maxLat)"
        queryItems.append(URLQueryItem(name: "bbox", value: bbox))
        queryItems.append(URLQueryItem(name: "limit", value: resultLimit))
        components?.queryItems = queryItems

        guard let url = components?.url else {
            throw URLError(.badURL)
        }

        let (data, _) = try await session.data(from: url)
        let decoded = try JSONDecoder().decode(ToiletsResponse.self, from: data)
        return decoded.items
    }

    func fetchNearby(lat: Double, lng: Double, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/toilets/nearby"), resolvingAgainstBaseURL: false)
        var queryItems = [
            URLQueryItem(name: "lat", value: String(lat)),
            URLQueryItem(name: "lng", value: String(lng)),
            URLQueryItem(name: "radius_m", value: "1500")
        ]
        queryItems.append(contentsOf: buildCommonQueryItems(filters: filters))
        components?.queryItems = queryItems

        guard let url = components?.url else {
            throw URLError(.badURL)
        }

        let (data, _) = try await session.data(from: url)
        let decoded = try JSONDecoder().decode(ToiletsResponse.self, from: data)
        return decoded.items
    }
}
