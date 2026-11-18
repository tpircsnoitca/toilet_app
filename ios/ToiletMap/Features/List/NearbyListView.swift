import MapKit
import SwiftUI

struct NearbyListView: View {
    let toilets: [ToiletMapItem]
    let origin: CLLocationCoordinate2D
    let usesUserLocation: Bool
    let selectedToiletID: String?
    let onSelectToilet: (ToiletMapItem) -> Void
    @State private var detailToilet: ToiletMapItem?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(toilets) { toilet in
                        VStack(alignment: .leading, spacing: 0) {
                            // A standard button cancels its tap when the ScrollView
                            // takes over a drag. Keep directions as a sibling button.
                            Button {
                                onSelectToilet(toilet)
                            } label: {
                                ToiletInformationView(toilet: toilet, distanceDescription: distanceDescription(toilet))
                                    .padding(16)
                                    .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityHint("在地圖上顯示此廁所")
                            if let records = toilet.sourceRecords, records.count > 1 {
                                Button {
                                    detailToilet = toilet
                                } label: {
                                    Label("查看 \(records.count) 筆廁所詳情", systemImage: "building.2")
                                        .font(.subheadline)
                                        .frame(maxWidth: .infinity, minHeight: 44)
                                        .contentShape(Rectangle())
                                }
                                .buttonStyle(.bordered)
                                .padding(.horizontal, 16).padding(.bottom, 12)
                            }
                            ToiletDirectionsButton(toilet: toilet)
                                .padding(.horizontal, 16).padding(.bottom, 16)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18))
                        .overlay {
                            RoundedRectangle(cornerRadius: 18)
                                .stroke(selectedToiletID == toilet.id ? Color.blue : .clear, lineWidth: 2)
                        }
                        .id(toilet.id)
                    }
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .overlay {
                if toilets.isEmpty {
                    ContentUnavailableView("這個區域沒有符合條件的廁所", systemImage: "toilet", description: Text("請移動地圖或調整篩選條件。"))
                }
            }
            .onChange(of: selectedToiletID) {
                if let selectedToiletID {
                    withAnimation(reduceMotion ? nil : .snappy) { proxy.scrollTo(selectedToiletID, anchor: .top) }
                }
            }
            .onAppear {
                if let selectedToiletID { proxy.scrollTo(selectedToiletID, anchor: .top) }
            }
        }
        .sheet(item: $detailToilet) { toilet in
            NavigationStack { ToiletDetailView(toilet: toilet) }
        }
    }

    private func distanceDescription(_ toilet: ToiletMapItem) -> String {
        let meters = CLLocation(latitude: origin.latitude, longitude: origin.longitude)
            .distance(from: CLLocation(latitude: toilet.lat, longitude: toilet.lng))
        return ToiletDistanceText.format(meters: meters, usesUserLocation: usesUserLocation)
    }
}
