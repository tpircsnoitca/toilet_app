import MapKit
import SwiftUI

struct MapHomeView: View {
    @StateObject private var locationService = LocationService()
    @StateObject private var repository = ToiletRepository()

    private static let initialRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 25.0478, longitude: 121.5170),
        span: MKCoordinateSpan(latitudeDelta: 0.03, longitudeDelta: 0.03)
    )
    @State private var cameraPosition: MapCameraPosition = .region(initialRegion)
    @State private var filters = ToiletQueryFilters()
    @State private var currentVisibleRegion = initialRegion
    @State private var reloadTask: Task<Void, Never>?
    @State private var selectedToiletID: String?
    @State private var selectedGroupIDs: Set<String> = []
    @State private var panelLevel = 1
    @GestureState private var panelDrag: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme
    @State private var hasCenteredOnLocation = false

    private var markerBackground: Color {
        colorScheme == .dark ? Color(red: 0.66, green: 0.79, blue: 1) : Color(red: 0.09, green: 0.23, blue: 0.50)
    }

    private var markerForeground: Color {
        colorScheme == .dark ? Color(red: 0.05, green: 0.14, blue: 0.29) : .white
    }

    var body: some View {
        NavigationStack {
            mapScreen
        }
        .overlay {
            if !repository.hasLoaded && repository.errorMessage == nil {
                ToiletLoadingScreen()
            }
        }
    }

    private var mapScreen: some View {
        mapContent
            .toolbar(.hidden, for: .navigationBar)
            .safeAreaInset(edge: .top) {
                filterControls
            }
            .onChange(of: filters) {
                selectedGroupIDs = []
                selectedToiletID = nil
                scheduleReload()
            }
            .onChange(of: repository.toilets) {
                selectedGroupIDs.formIntersection(Set(repository.toilets.map(\.id)))
                if !repository.toilets.contains(where: { $0.id == selectedToiletID }) {
                    selectedToiletID = nil
                }
            }
            .onDisappear {
                reloadTask?.cancel()
                repository.cancelLoading()
            }
    }

    @ViewBuilder
    private var loadingStatus: some View {
        if let error = repository.errorMessage {
            VStack(alignment: .leading, spacing: 8) {
                Label(error, systemImage: "wifi.exclamationmark")
                if !repository.toilets.isEmpty {
                    Text("目前顯示上次載入的廁所。").font(.caption)
                }
                Button("重試") { scheduleReload() }
                    .buttonStyle(.borderedProminent)
            }
        } else if repository.isLoading {
            ProgressView("正在更新這個區域的廁所…")
        } else if locationService.currentLocation == nil {
            switch locationService.authorizationStatus {
            case .denied, .restricted:
                Label("定位已關閉，拖曳地圖即可尋找廁所。", systemImage: "location.slash")
                    .font(.subheadline)
            case .notDetermined:
                Label("允許定位即可尋找附近的廁所。", systemImage: "location")
                    .font(.subheadline)
            default:
                if locationService.locationUnavailable {
                    VStack(spacing: 8) {
                        Text("目前無法取得定位，仍可拖曳地圖尋找廁所。")
                        Button("重新定位") { locationService.startUpdatingLocation() }
                    }
                } else {
                    ProgressView("正在取得定位…")
                }
            }
        } else if repository.toilets.isEmpty {
            Label("這個區域沒有符合條件的廁所，請移動地圖或調整篩選條件。", systemImage: "toilet")
                .font(.subheadline)
        }
    }

    private var distanceOrigin: CLLocationCoordinate2D {
        locationService.currentLocation?.coordinate ?? currentVisibleRegion.center
    }

    private var visibleToilets: [ToiletMapItem] {
        let origin = CLLocation(latitude: distanceOrigin.latitude, longitude: distanceOrigin.longitude)
        return repository.toilets
            .filter { selectedGroupIDs.isEmpty || selectedGroupIDs.contains($0.id) }
            .sorted {
                let first = origin.distance(from: CLLocation(latitude: $0.lat, longitude: $0.lng))
                let second = origin.distance(from: CLLocation(latitude: $1.lat, longitude: $1.lng))
                return first == second ? $0.id < $1.id : first < second
            }
    }

    private var mapContent: some View {
        GeometryReader { geometry in
            ZStack(alignment: .bottom) {
                Map(position: $cameraPosition) {
                    UserAnnotation()
                    ForEach(ToiletMarkerGroup.groups(
                        repository.toilets,
                        latitudeSpan: currentVisibleRegion.span.latitudeDelta,
                        longitudeSpan: currentVisibleRegion.span.longitudeDelta,
                        width: geometry.size.width, height: geometry.size.height
                    )) { group in
                        Annotation("廁所", coordinate: CLLocationCoordinate2D(latitude: group.lat, longitude: group.lng)) {
                            Button {
                                selectedGroupIDs = group.items.count > 1 ? Set(group.items.map(\.id)) : []
                                selectedToiletID = group.items.sorted { $0.id < $1.id }.first?.id
                                withAnimation(reduceMotion ? nil : .snappy) { panelLevel = 1 }
                            } label: {
                                let selected = group.items.contains { $0.id == selectedToiletID }
                                Image(systemName: "toilet")
                                    .font(.system(size: 20, weight: .bold))
                                    .foregroundStyle(markerForeground)
                                    .frame(width: 36, height: 36)
                                    .background(markerBackground, in: Circle())
                                    .overlay(Circle().strokeBorder(markerForeground, lineWidth: 2))
                                    .overlay {
                                        if selected {
                                            Circle().strokeBorder(Color.accentColor, lineWidth: 2).padding(-3)
                                        }
                                    }
                                    .shadow(color: .black.opacity(0.30), radius: 2, y: 1)
                                    .frame(width: 44, height: 44)
                                    .overlay(alignment: .topTrailing) {
                                        if group.items.count > 1 {
                                            Text("\(group.items.count)")
                                                .font(.system(size: 10, weight: .bold).monospacedDigit())
                                                .foregroundStyle(markerForeground)
                                                .padding(.horizontal, 4)
                                                .frame(minWidth: 16, minHeight: 16)
                                                .background(markerBackground, in: Capsule())
                                                .overlay(Capsule().strokeBorder(markerForeground, lineWidth: 1))
                                        }
                                    }
                                    .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(group.items.count == 1 ? group.items[0].name : "\(group.items.count) 個廁所地點，點一下查看清單")
                        }
                        .annotationTitles(.hidden)
                    }
                }
                .mapControls {
                    MapUserLocationButton()
                        .accessibilityLabel("回到我的位置")
                    MapCompass()
                }
                .onAppear { locationService.requestWhenInUseAuthorization() }
                .task(id: locationService.currentLocation != nil) {
                    if let location = locationService.currentLocation, !hasCenteredOnLocation {
                        hasCenteredOnLocation = true
                        cameraPosition = .region(MKCoordinateRegion(center: location.coordinate, span: Self.initialRegion.span))
                    } else if !repository.hasLoaded {
                        scheduleReload()
                    }
                }
                .onMapCameraChange(frequency: .onEnd) { context in
                    let previous = currentVisibleRegion
                    let next = context.region
                    guard abs(previous.center.latitude - next.center.latitude) > next.span.latitudeDelta * 0.001 ||
                        abs(previous.center.longitude - next.center.longitude) > next.span.longitudeDelta * 0.001 ||
                        abs(previous.span.latitudeDelta - next.span.latitudeDelta) > next.span.latitudeDelta * 0.001 ||
                        abs(previous.span.longitudeDelta - next.span.longitudeDelta) > next.span.longitudeDelta * 0.001 else { return }
                    currentVisibleRegion = next
                    selectedGroupIDs = []
                    scheduleReload()
                }

                nearbyPanel(availableHeight: geometry.size.height)
            }
        }
    }

    private func nearbyPanel(availableHeight: CGFloat) -> some View {
        let heights: [CGFloat] = [min(112, availableHeight * 0.3), availableHeight * 0.46, availableHeight * 0.9]
        let height = min(heights[2], max(heights[0], heights[panelLevel] - panelDrag))
        return VStack(spacing: 0) {
            VStack(spacing: 6) {
                Capsule().fill(.secondary.opacity(0.4)).frame(width: 36, height: 5)
                HStack {
                    Button {
                        withAnimation(reduceMotion ? nil : .snappy) {
                            panelLevel = panelLevel < 2 ? panelLevel + 1 : 0
                        }
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text("附近廁所").font(.headline)
                                Text(selectedGroupIDs.isEmpty ? "地圖範圍內有 \(repository.toilets.count) 個廁所地點" : "所選位置有 \(selectedGroupIDs.count) 個廁所地點")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: panelLevel < 2 ? "chevron.up" : "chevron.down")
                                .accessibilityHidden(true)
                        }
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(panelLevel < 2 ? "展開附近廁所清單" : "收合附近廁所清單")
                    if !selectedGroupIDs.isEmpty {
                        Button("顯示全部") { selectedGroupIDs = [] }
                            .font(.subheadline).frame(minHeight: 44)
                    }
                }
            }
            .padding(.horizontal, 16).padding(.top, 10)
            .contentShape(Rectangle())
            .gesture(DragGesture()
                .updating($panelDrag) { value, state, _ in state = value.translation.height }
                .onEnded { value in
                    let target = heights[panelLevel] - value.predictedEndTranslation.height
                    let nearest = heights.indices.min { abs(heights[$0] - target) < abs(heights[$1] - target) } ?? 1
                    withAnimation(reduceMotion ? nil : .snappy) { panelLevel = nearest }
                })
            .accessibilityAction(named: "展開清單") { panelLevel = min(2, panelLevel + 1) }
            .accessibilityAction(named: "收合清單") { panelLevel = max(0, panelLevel - 1) }

            if repository.errorMessage != nil || repository.isLoading || locationService.currentLocation == nil {
                loadingStatus.font(.caption).padding(.horizontal, 16).padding(.bottom, 8)
            }
            if panelLevel != 0 || panelDrag < 0 {
                Divider()
                NearbyListView(
                    toilets: visibleToilets, origin: distanceOrigin,
                    usesUserLocation: locationService.currentLocation != nil,
                    selectedToiletID: selectedToiletID,
                    onSelectToilet: { toilet in
                        selectedToiletID = toilet.id
                        selectedGroupIDs = []
                        withAnimation(reduceMotion ? nil : .snappy) {
                            panelLevel = 0
                            cameraPosition = .region(MKCoordinateRegion(
                                center: CLLocationCoordinate2D(latitude: toilet.lat, longitude: toilet.lng),
                                span: MKCoordinateSpan(latitudeDelta: 0.004, longitudeDelta: 0.004)))
                        }
                    })
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: height, alignment: .top)
        .background(.regularMaterial, in: UnevenRoundedRectangle(topLeadingRadius: 24, topTrailingRadius: 24))
        .clipShape(UnevenRoundedRectangle(topLeadingRadius: 24, topTrailingRadius: 24))
        .shadow(color: .black.opacity(0.12), radius: 10, y: -3)
    }

    private var filterControls: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                GenderFilterMenu(selection: $filters.genders)
                ToggleChip(title: "無障礙", isOn: $filters.accessibleOnly)
                ToggleChip(title: "尿布台", isOn: $filters.diaperTableOnly)
            }
            .padding(.horizontal)
        }
        .padding(.vertical, 6)
        .background(.thinMaterial)
    }

    private func scheduleReload() {
        reloadTask?.cancel()
        repository.cancelLoading()
        reloadTask = Task {
            try? await Task.sleep(for: .milliseconds(350))
            if Task.isCancelled { return }
            await repository.loadViewport(region: currentVisibleRegion, filters: filters)
        }
    }
}

struct ToiletLoadingScreen: View {
    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 16) {
                ToiletLoadingAnimation()
                Text("正在載入附近廁所…")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct ToiletLoadingAnimation: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var startedAt = Date()

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion)) { context in
            let progress = reduceMotion ? 0.35 :
                context.date.timeIntervalSince(startedAt).truncatingRemainder(dividingBy: 1.8) / 1.8
            ZStack {
                Image(systemName: "toilet.fill")
                    .font(.system(size: 32))
                    .offset(x: 48)
                Image(systemName: "figure.run")
                    .font(.system(size: 28, weight: .medium))
                    .offset(x: -55 + progress * 103,
                            y: reduceMotion ? 0 : -abs(sin(progress * .pi * 10)) * 4)
                    .opacity(progress > 0.8 ? (1 - progress) / 0.2 : 1)
            }
            .foregroundStyle(.blue)
            .frame(width: 160, height: 52)
        }
        .accessibilityHidden(true)
    }
}

private struct ToggleChip: View {
    let title: String
    @Binding var isOn: Bool

    var body: some View {
        Button {
            isOn.toggle()
        } label: {
            Text(title)
                .font(.caption)
                .foregroundStyle(isOn ? .white : .primary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .frame(minHeight: 44)
                .background(isOn ? Color.blue : Color(.systemGray5))
                .clipShape(Capsule())
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isOn ? .isSelected : [])
    }
}

private struct GenderFilterMenu: View {
    @Binding var selection: Set<ToiletQueryFilters.Gender>

    private var title: LocalizedStringKey {
        selection.isEmpty ? "性別" : "性別（\(selection.count)）"
    }

    var body: some View {
        Menu {
            Button {
                selection.removeAll()
            } label: {
                Label("所有性別", systemImage: selection.isEmpty ? "checkmark.circle.fill" : "circle")
            }
            Divider()
            Toggle("男廁", isOn: binding(for: .men))
            Toggle("女廁", isOn: binding(for: .women))
            Toggle("性別友善", isOn: binding(for: .genderFriendly))
        } label: {
            HStack(spacing: 5) {
                Text(title)
                Image(systemName: "chevron.down")
                    .accessibilityHidden(true)
            }
            .font(.caption)
            .foregroundStyle(selection.isEmpty ? Color.primary : Color.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .frame(minHeight: 44)
            .background(selection.isEmpty ? Color(.systemGray5) : .blue)
            .clipShape(Capsule())
            .contentShape(Rectangle())
        }
        .menuActionDismissBehavior(.disabled)
        .buttonStyle(.plain)
        .accessibilityLabel("性別")
        .accessibilityValue(selection.isEmpty ? Text("所有性別") : Text("已選 \(selection.count) 項"))
    }

    private func binding(for gender: ToiletQueryFilters.Gender) -> Binding<Bool> {
        Binding {
            selection.contains(gender)
        } set: { isOn in
            if isOn {
                selection.insert(gender)
            } else {
                selection.remove(gender)
            }
        }
    }
}
