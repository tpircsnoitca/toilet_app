import SwiftUI

struct ToiletDetailView: View {
    let toilet: ToiletMapItem
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(alignment: .top, spacing: 12) {
                    Text(toilet.name)
                        .font(.title3.weight(.semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ToiletDirectionsButton(toilet: toilet)
                }
                if let records = toilet.sourceRecords, records.count > 1 {
                    Text("各廁所詳情").font(.headline)
                    ForEach(records) { record in
                        VStack(alignment: .leading, spacing: 12) {
                            if toilet.matchingSourceIds?.contains(record.id) == true {
                                Label("符合目前的篩選條件", systemImage: "checkmark.circle")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            ToiletInformationView(toilet: record, showStatus: false)
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
    var showStatus = true

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(toilet.name)
                .font(.title3.weight(.semibold))
            let locationDetails = [toilet.building, toilet.floorLabel].compactMap { $0 }
            if !locationDetails.isEmpty {
                Label(locationDetails.joined(separator: " · "), systemImage: "building.2")
                    .foregroundStyle(.secondary)
            }
            if let distanceDescription {
                Label(distanceDescription, systemImage: "location")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)
            }
            if showStatus {
                Label(toilet.availabilityLabel, systemImage: "clock.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(availabilityColor)
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .background(availabilityColor.opacity(0.1), in: Capsule())
            }
            ToiletFacilitySymbols(toilet: toilet)
            if (toilet.sourceCount ?? 1) == 1 && !toilet.hasMenToiletResolved && !toilet.hasWomenToiletResolved && !toilet.toiletTypes.contains("gender_friendly") {
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
        if let directionsURL {
            Link(destination: directionsURL) {
                Image(systemName: "arrow.triangle.turn.up.right.diamond")
                    .font(.system(size: 18, weight: .medium))
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 36, height: 36)
                    .background(Color.accentColor.opacity(0.15), in: Circle())
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("前往 \(toilet.name) 的步行導航")
        }
    }

    private var directionsURL: URL? {
        guard (-90...90).contains(toilet.lat), (-180...180).contains(toilet.lng) else { return nil }
        return URL(string: "https://www.google.com/maps/dir/?api=1&destination=\(toilet.lat)%2C\(toilet.lng)&travelmode=walking")
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
            if toilet.hasDiaperTable { badge("尿布台", icon: "figure.child") }
            if toilet.hasAccessibleToilet { badge("無障礙廁所", icon: "figure.roll") }
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

    private func badge(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.caption)
            .foregroundStyle(.blue)
            .accessibilityElement(children: .combine)
    }
}
