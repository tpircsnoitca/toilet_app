import MapKit
import SwiftUI

struct ToiletDetailView: View {
    let toilet: ToiletMapItem
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                ToiletInformationView(toilet: toilet)
                ToiletDirectionsButton(toilet: toilet)
                if let records = toilet.sourceRecords, records.count > 1 {
                    Text("各廁所詳情").font(.headline)
                    ForEach(records) { record in
                        VStack(alignment: .leading, spacing: 12) {
                            if toilet.matchingSourceIds?.contains(record.id) == true {
                                Label("符合目前的篩選條件", systemImage: "checkmark.circle")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            ToiletInformationView(toilet: record)
                        }
                        .padding()
                        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
                    }
                }
            }
            .padding()
        }
        .navigationTitle("廁所詳情")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
    }
}

struct ToiletInformationView: View {
    let toilet: ToiletMapItem
    var distanceDescription: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(toilet.name)
                .font(.title3.weight(.semibold))
            Text(toilet.address ?? "未提供地址")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            let locationDetails = [toilet.building, toilet.floorLabel].compactMap { $0 }
            if !locationDetails.isEmpty {
                Label(locationDetails.joined(separator: " · "), systemImage: "building.2")
                    .foregroundStyle(.secondary)
            }
            if let distanceDescription {
                Label(distanceDescription, systemImage: "location")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)
            } else if let distance = toilet.distanceM {
                Text(ToiletDistanceText.format(meters: Double(distance), usesUserLocation: true))
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Label(toilet.availabilityLabel, systemImage: "clock.fill")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(availabilityColor)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(availabilityColor.opacity(0.1), in: Capsule())
            Text("今日開放時間：\(toilet.todayHoursLabel)")
                .font(.subheadline)
            Divider()
            ToiletFacilitySymbols(toilet: toilet)
            if (toilet.sourceCount ?? 1) > 1 {
                Text("各廁所設施可能不同，請查看詳情確認樓層及開放狀態。")
                    .font(.caption).foregroundStyle(.secondary)
            } else if !toilet.hasMenToiletResolved && !toilet.hasWomenToiletResolved && !toilet.toiletTypes.contains("gender_friendly") {
                Text("未標示性別").font(.caption).foregroundStyle(.secondary)
            }
        }
        .font(.subheadline)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var availabilityColor: Color {
        switch toilet.openNow {
        case true: return .green
        case false: return .red
        default: return .secondary
        }
    }
}

struct ToiletDirectionsButton: View {
    let toilet: ToiletMapItem

    var body: some View {
        Button {
            let coordinate = CLLocationCoordinate2D(latitude: toilet.lat, longitude: toilet.lng)
            let item = MKMapItem(placemark: MKPlacemark(coordinate: coordinate))
            item.name = toilet.name
            item.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeWalking])
        } label: {
            Label("開啟步行導航", systemImage: "arrow.triangle.turn.up.right.diamond.fill")
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderedProminent)
        .accessibilityHint("查看前往 \(toilet.name) 的步行路線")
    }
}

struct ToiletFacilitySymbols: View {
    let toilet: ToiletMapItem

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 105), alignment: .leading)], alignment: .leading, spacing: 10) {
            if toilet.hasWomenToiletResolved { gender("♀", title: "女廁") }
            if toilet.hasMenToiletResolved { gender("♂", title: "男廁") }
            if toilet.toiletTypes.contains("gender_friendly") { badge("性別友善", icon: "person.2.fill") }
            if toilet.toiletTypes.contains("family") { badge("親子廁所", icon: "figure.and.child.holdinghands") }
            badge(toilet.hasDiaperTable ? "有尿布台" : "無尿布台", icon: "figure.child", available: toilet.hasDiaperTable)
            badge(toilet.hasAccessibleToilet ? "有無障礙廁所" : "無無障礙廁所", icon: "figure.roll", available: toilet.hasAccessibleToilet)
        }
    }

    private func gender(_ symbol: String, title: String) -> some View {
        HStack(spacing: 6) {
            Text(symbol).font(.title2.weight(.semibold)).accessibilityHidden(true)
            Text(title).font(.caption)
        }
        .foregroundStyle(.blue)
        .accessibilityElement(children: .combine)
    }

    private func badge(_ title: String, icon: String, available: Bool = true) -> some View {
        Label(title, systemImage: icon)
            .font(.caption)
            .foregroundStyle(available ? Color.blue : .secondary)
            .accessibilityElement(children: .combine)
    }
}
