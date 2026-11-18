import Foundation
import MapKit

// Run with ios/Tests/check-request-coordination.sh. No server or simulator required.
@MainActor
final class ControlledClient: ToiletFetching {
    var pending: [CheckedContinuation<[ToiletMapItem], Error>] = []
    var regions: [MKCoordinateRegion] = []

    func fetchToilets(filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        // Deliberately ignore cancellation to exercise the stale-response guard.
        try await withCheckedThrowingContinuation { pending.append($0) }
    }

    func fetchNearby(lat: Double, lng: Double, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        try await fetchToilets(filters: filters)
    }

    func fetchToiletsInViewport(region: MKCoordinateRegion, filters: ToiletQueryFilters) async throws -> [ToiletMapItem] {
        regions.append(region)
        return try await fetchToilets(filters: filters)
    }
}

@main
struct RequestCoordinationChecks {
    @MainActor
    static func waitForRequests(_ count: Int, client: ControlledClient) async {
        for _ in 0..<10_000 {
            if client.pending.count >= count { return }
            await Task.yield()
        }
        fatalError("Request did not start")
    }

    static func item(_ id: String, lat: Double = 25, lng: Double = 121) -> ToiletMapItem {
        ToiletMapItem(id: id, name: id, city: "taipei", district: "", address: nil,
                      lat: lat, lng: lng, toiletTypes: [], hasMenToilet: nil,
                      hasWomenToilet: nil, hasDiaperTable: false, openNow: nil,
                      openLabel: "Hours unavailable", distanceM: nil)
    }

    @MainActor
    static func main() async {
        precondition(ToiletDistanceText.format(meters: 125, usesUserLocation: true, language: "zh-Hant-TW") == "距離 125 公尺")
        precondition(ToiletDistanceText.format(meters: 125, usesUserLocation: false, language: "zh-TW") == "距離地圖中心 125 公尺")
        precondition(ToiletDistanceText.format(meters: 1250, usesUserLocation: true, language: "zh-Hant") == "距離 1.2 公里")
        precondition(ToiletDistanceText.format(meters: 125, usesUserLocation: true, language: "en-US") == "125 m away")
        precondition(ToiletDistanceText.format(meters: 1500, usesUserLocation: false, language: "en") == "1.5 km from map center")
        precondition(ToiletDistanceText.format(meters: 125, usesUserLocation: true) == "距離 125 公尺")
        print("PASS: Traditional Chinese/English distance units and location fallback")

        let fixtureURL = URL(fileURLWithPath: "ios/Tests/Fixtures/aggregated-hospital.json")
        let response = try! JSONDecoder().decode(ToiletsResponse.self, from: Data(contentsOf: fixtureURL))
        let hospital = response.items[0]
        precondition(hospital.sourceCount == 10 && hospital.sourceRecords?.count == 10)
        precondition(hospital.hasMenToiletResolved && hospital.hasWomenToiletResolved)
        precondition(hospital.symbolSources?["female"]?.count == 5)
        precondition(hospital.sourceRecords?.contains { $0.building == "第二棟" && $0.floor == "2樓" } == true)
        precondition(hospital.openNow == nil, "Unknown government hours must stay unknown")
        precondition(hospital.availabilityLabel == "開放狀態不明")
        precondition(hospital.todayHoursLabel == "未提供開放時間")
        precondition(hospital.sourceRecords?.contains { $0.floor == "1F" && $0.floorLabel == "1 樓" } == true)
        precondition(ToiletHoursText.format("Open 24 hours") == "全天開放")
        precondition(ToiletHoursText.format("Hours vary by toilet") == "各廁所開放時間不同")
        precondition(ToiletHoursText.format("09:00–18:00") == "09:00–18:00")
        precondition(ToiletHoursText.format("22:00–02:00 (next day)") == "22:00–02:00（跨日）")
        let original = item("legacy")
        let legacy = try! JSONDecoder().decode(ToiletMapItem.self, from: JSONEncoder().encode(original))
        precondition(legacy.sourceRecords == nil, "Ungrouped responses must still decode")
        print("PASS: backend hospital fixture, original floor/building records, symbol provenance, legacy decoding")

        let markers = [item("a"), item("b"), item("c", lat: 25.0001, lng: 121.0001),
                       item("far", lat: 25.1, lng: 121.1)]
        let grouped = ToiletMarkerGroup.groups(markers, latitudeSpan: 0.03, longitudeSpan: 0.03, width: 390, height: 700)
        precondition(grouped.flatMap(\.items).map(\.id).sorted() == markers.map(\.id).sorted(),
                     "Clustering must retain every government record exactly once")
        precondition(grouped.contains { Set($0.items.map(\.id)) == ["a", "b", "c"] },
                     "Nearby markers should group at a wide zoom")
        let reversed = ToiletMarkerGroup.groups(Array(markers.reversed()), latitudeSpan: 0.03, longitudeSpan: 0.03, width: 390, height: 700)
        precondition(grouped.map(\.id) == reversed.map(\.id), "Marker identities must be independent of API order")
        let close = ToiletMarkerGroup.groups(markers, latitudeSpan: 0.0002, longitudeSpan: 0.0002, width: 390, height: 700)
        precondition(close.count > grouped.count, "Zooming in should separate nearby locations")
        precondition(close.contains { Set($0.items.map(\.id)) == ["a", "b"] },
                     "Same-coordinate toilets must remain available through a counted marker")
        precondition(ToiletMarkerGroup.groups([], latitudeSpan: 0.03, longitudeSpan: 0.03, width: 390, height: 700).isEmpty)
        precondition(ToiletMarkerGroup.groups(markers, latitudeSpan: 0, longitudeSpan: 0, width: 0, height: 0).count == markers.count)
        print("PASS: marker grouping, stable identities, zoom separation, co-located records, empty/zero-size layout")

        let client = ControlledClient()
        let repository = ToiletRepository(client: client)
        precondition(!repository.hasLoaded, "Startup must distinguish loading from empty results")
        let filters = ToiletQueryFilters()
        let old = Task { await repository.loadList(filters: filters) }
        await waitForRequests(1, client: client)
        let latest = Task { await repository.loadNearby(lat: 25, lng: 121, filters: filters) }
        await waitForRequests(2, client: client)
        client.pending[1].resume(returning: [item("latest")])
        await latest.value
        precondition(repository.hasLoaded)
        client.pending[0].resume(returning: [item("old")])
        await old.value
        precondition(repository.toilets.map(\.id) == ["latest"], "Stale results replaced latest results")

        let staleFailure = Task { await repository.loadList(filters: filters) }
        await waitForRequests(3, client: client)
        let newest = Task { await repository.loadList(filters: filters) }
        await waitForRequests(4, client: client)
        client.pending[2].resume(throwing: URLError(.timedOut))
        await staleFailure.value
        precondition(repository.isLoading, "Old request cleared the new loading state")
        precondition(repository.errorMessage == nil, "Old failure displayed an error")
        precondition(repository.toilets.map(\.id) == ["latest"], "Refresh cleared existing results")
        client.pending[3].resume(returning: [item("newest")])
        await newest.value
        precondition(!repository.isLoading)

        let canceled = Task { await repository.loadList(filters: filters) }
        await waitForRequests(5, client: client)
        repository.cancelLoading()
        client.pending[4].resume(returning: [item("canceled")])
        await canceled.value
        precondition(repository.toilets.map(\.id) == ["newest"], "Canceled request published results")
        precondition(!repository.isLoading)

        let failure = Task { await repository.loadList(filters: filters) }
        await waitForRequests(6, client: client)
        client.pending[5].resume(throwing: URLError(.notConnectedToInternet))
        await failure.value
        precondition(repository.errorMessage != nil, "Current failures must remain visible")
        precondition(!repository.isLoading)
        print("PASS: stale success, stale failure, overlapping loading, retained results, cancellation, current failure")

        let cacheClient = ControlledClient()
        var clock = Date()
        let cached = ToiletRepository(client: cacheClient, now: { clock })
        let region = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 25, longitude: 121),
                                        span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02))
        let first = Task { await cached.loadViewport(region: region, filters: filters) }
        await waitForRequests(1, client: cacheClient)
        precondition(cacheClient.regions[0].span.latitudeDelta == 0.03)
        cacheClient.pending[0].resume(returning: [item("cached")])
        await first.value
        var shifted = region
        shifted.center.latitude += 0.004
        await cached.loadViewport(region: shifted, filters: filters)
        precondition(cacheClient.pending.count == 1, "Small pan should reuse buffered results")
        precondition(cached.toilets.map(\.id) == ["cached"])
        shifted.center.latitude += 0.01
        let outside = Task { await cached.loadViewport(region: shifted, filters: filters) }
        await waitForRequests(2, client: cacheClient)
        cacheClient.pending[1].resume(returning: [item("outside")])
        await outside.value
        precondition(cached.toilets.isEmpty, "Buffered toilets outside visible area must not appear in list")
        var changedFilters = filters
        changedFilters.genders = [.women, .genderFriendly]
        let changed = Task { await cached.loadViewport(region: shifted, filters: changedFilters) }
        await waitForRequests(3, client: cacheClient)
        cacheClient.pending[2].resume(returning: [])
        await changed.value
        precondition(cached.hasLoaded && cached.toilets.isEmpty, "Successful empty results must finish startup")
        clock = clock.addingTimeInterval(31)
        let expired = Task { await cached.loadViewport(region: shifted, filters: changedFilters) }
        await waitForRequests(4, client: cacheClient)
        cacheClient.pending[3].resume(returning: [])
        await expired.value
        let capped = Task { await cached.loadViewport(region: region, filters: filters) }
        await waitForRequests(5, client: cacheClient)
        cacheClient.pending[4].resume(returning: (0..<200).map { item("\($0)") })
        await waitForRequests(6, client: cacheClient)
        precondition(cacheClient.regions[5].span.latitudeDelta == region.span.latitudeDelta,
                     "Capped buffer must fall back to exact viewport")
        cacheClient.pending[5].resume(returning: [item("exact")])
        await capped.value
        precondition(cached.toilets.map(\.id) == ["exact"])
        print("PASS: buffered reuse, coverage miss, visible-area filtering, filter change, expiration, capped-response fallback")

        let startupClient = ControlledClient()
        let startup = ToiletRepository(client: startupClient)
        let failedStart = Task { await startup.loadList(filters: filters) }
        await waitForRequests(1, client: startupClient)
        precondition(startup.isLoading && !startup.hasLoaded)
        startupClient.pending[0].resume(throwing: URLError(.timedOut))
        await failedStart.value
        precondition(!startup.isLoading && !startup.hasLoaded && startup.errorMessage != nil)
        let retry = Task { await startup.loadList(filters: filters) }
        await waitForRequests(2, client: startupClient)
        precondition(startup.errorMessage == nil && startup.isLoading)
        startupClient.pending[1].resume(returning: [])
        await retry.value
        precondition(startup.hasLoaded && !startup.isLoading && startup.errorMessage == nil)
        print("PASS: initial loading, startup failure, retry recovery, successful empty state")
    }
}
