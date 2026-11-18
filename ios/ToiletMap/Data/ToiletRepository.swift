import Combine
import Foundation
import MapKit

protocol ToiletFetching {
    func fetchNearby(lat: Double, lng: Double, filters: ToiletQueryFilters) async throws -> [ToiletMapItem]
    func fetchToilets(filters: ToiletQueryFilters) async throws -> [ToiletMapItem]
    func fetchToiletsInViewport(region: MKCoordinateRegion, filters: ToiletQueryFilters) async throws -> [ToiletMapItem]
}

extension APIClient: ToiletFetching {}

@MainActor
final class ToiletRepository: ObservableObject {
    @Published private(set) var toilets: [ToiletMapItem] = []
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?
    @Published private(set) var hasLoaded = false

    private let client: any ToiletFetching
    private var requestTask: Task<[ToiletMapItem], Error>?
    private var requestID = UUID()
    private let now: () -> Date
    private var viewportCache: ViewportCache?

    private struct ViewportCache {
        let region: MKCoordinateRegion
        let filters: ToiletQueryFilters
        let items: [ToiletMapItem]
        let createdAt: Date
    }

    init(client: any ToiletFetching = APIClient.shared, now: @escaping () -> Date = Date.init) {
        self.client = client
        self.now = now
    }

    func dismissError() {
        errorMessage = nil
    }

    // Invalidate immediately, including while the next map request is being debounced.
    func cancelLoading() {
        requestID = UUID()
        requestTask?.cancel()
        requestTask = nil
        isLoading = false
    }

    func loadNearby(lat: Double, lng: Double, filters: ToiletQueryFilters) async {
        await load(error: "無法載入附近廁所。") {
            try await self.client.fetchNearby(lat: lat, lng: lng, filters: filters)
        }
    }

    func loadList(filters: ToiletQueryFilters) async {
        await load(error: "無法載入廁所資料。") {
            try await self.client.fetchToilets(filters: filters)
        }
    }

    func loadViewport(region: MKCoordinateRegion, filters: ToiletQueryFilters) async {
        guard !Task.isCancelled else { return }
        if let cache = viewportCache, cache.filters == filters,
           now().timeIntervalSince(cache.createdAt) < 30,
           Self.contains(cache.region, region) {
            cancelLoading()
            errorMessage = nil
            toilets = cache.items.filter { Self.contains(region, $0) }
            hasLoaded = true
            return
        }

        // Fetch a 25% margin on each side, within valid coordinate bounds.
        let buffered = MKCoordinateRegion(
            center: region.center,
            span: MKCoordinateSpan(
                latitudeDelta: min(region.span.latitudeDelta * 1.5, 2 * (90 - abs(region.center.latitude))),
                longitudeDelta: min(region.span.longitudeDelta * 1.5, 2 * (180 - abs(region.center.longitude)))
            )
        )
        var completeBuffer: [ToiletMapItem]?
        await load(error: "無法載入這個區域的廁所。") {
            let items = try await self.client.fetchToiletsInViewport(region: buffered, filters: filters)
            try Task.checkCancellation()
            // A capped response cannot establish coverage of the visible area.
            if items.count >= 200 {
                return try await self.client.fetchToiletsInViewport(region: region, filters: filters)
            }
            completeBuffer = items
            return items.filter { Self.contains(region, $0) }
        } onSuccess: {
            if let items = completeBuffer {
                self.viewportCache = ViewportCache(region: buffered, filters: filters, items: items, createdAt: self.now())
            }
        }
    }

    private static func contains(_ outer: MKCoordinateRegion, _ inner: MKCoordinateRegion) -> Bool {
        abs(outer.center.latitude - inner.center.latitude) + inner.span.latitudeDelta / 2 <= outer.span.latitudeDelta / 2 &&
        abs(outer.center.longitude - inner.center.longitude) + inner.span.longitudeDelta / 2 <= outer.span.longitudeDelta / 2
    }

    private static func contains(_ region: MKCoordinateRegion, _ item: ToiletMapItem) -> Bool {
        abs(region.center.latitude - item.lat) <= region.span.latitudeDelta / 2 &&
        abs(region.center.longitude - item.lng) <= region.span.longitudeDelta / 2
    }

    private func load(error message: String, fetch: @escaping @MainActor () async throws -> [ToiletMapItem], onSuccess: @MainActor () -> Void = {}) async {
        guard !Task.isCancelled else { return }
        cancelLoading()
        let id = requestID
        isLoading = true
        errorMessage = nil
        let task = Task { try await fetch() }
        requestTask = task

        defer {
            if requestID == id {
                requestTask = nil
                isLoading = false
            }
        }

        do {
            let items = try await task.value
            guard requestID == id, !Task.isCancelled, !task.isCancelled else { return }
            onSuccess()
            toilets = items
            hasLoaded = true
        } catch {
            guard requestID == id, !Task.isCancelled, !task.isCancelled else { return }
            errorMessage = message
        }
    }
}
