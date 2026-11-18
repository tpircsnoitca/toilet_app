import Foundation

struct ToiletQueryFilters: Equatable {
    enum Gender: String, CaseIterable {
        case men
        case women
        case genderFriendly = "gender_friendly"
    }

    var keyword: String = ""
    var genders: Set<Gender> = []
    var diaperTableOnly = false
    var accessibleOnly = false
}
