import Foundation

// MARK: - JSON values

/// An extractor's `fields` dictionary is deliberately open-ended on the server —
/// a notification carries a body and timestamp, a survey carries a status, and so
/// on. This models that without forcing every page into one shape.
enum JSONValue: Codable, Sendable, Hashable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "unsupported JSON value"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    /// A human-readable rendering, or nil when there is nothing worth showing.
    var display: String? {
        switch self {
        case .string(let value):
            return value.isEmpty ? nil : value
        case .number(let value):
            return value == value.rounded() ? String(Int(value)) : String(value)
        case .bool(let value):
            return value ? "yes" : "no"
        case .array(let values):
            let parts = values.compactMap(\.display)
            return parts.isEmpty ? nil : parts.joined(separator: ", ")
        case .object:
            return nil
        case .null:
            return nil
        }
    }
}

// MARK: - API payloads

struct Me: Codable, Sendable {
    let userID: String
    let label: String
    /// The Hirewheel login email, read from the account page at sign-in.
    let email: String?
    let needsReauth: Bool
    let intervalSeconds: Int
    let lastScanAt: String?
    let runnerStatus: String
    let mutedPages: [String]
    let loginMode: String
    /// False when the server has no APNs credentials, which is the app's cue to
    /// run its own background-refresh fallback instead of waiting for push.
    let remotePush: Bool

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case label
        case email
        case needsReauth = "needs_reauth"
        case intervalSeconds = "interval_seconds"
        case lastScanAt = "last_scan_at"
        case runnerStatus = "runner_status"
        case mutedPages = "muted_pages"
        case loginMode = "login_mode"
        case remotePush = "remote_push"
    }
}

struct EnrollResponse: Codable, Sendable {
    let userID: String
    let deviceID: String
    let deviceToken: String

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case deviceID = "device_id"
        case deviceToken = "device_token"
    }
}

struct PageInfo: Codable, Sendable, Identifiable, Hashable {
    let key: String
    let label: String
    let url: String

    var id: String { key }
}

struct ScanSummary: Codable, Sendable, Identifiable, Hashable {
    let id: Int
    let startedAt: String
    let finishedAt: String?
    let status: String
    let error: String?
    let changeCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case startedAt = "started_at"
        case finishedAt = "finished_at"
        case status
        case error
        case changeCount = "change_count"
    }

    var failed: Bool { status == "error" || status == "auth_needed" }
}

struct ItemDTO: Codable, Sendable, Hashable, Identifiable {
    let uid: String
    let kind: String
    let title: String
    let fields: [String: JSONValue]
    let hash: String

    var id: String { uid }

    /// The single most useful supporting line for this item, if it has one.
    var detail: String? {
        for key in ["body", "detail", "status", "ts"] {
            if let value = fields[key]?.display { return value }
        }
        return nil
    }
}

struct ChangedItemDTO: Codable, Sendable, Hashable, Identifiable {
    let item: ItemDTO
    let changedFields: [String: [JSONValue]]

    var id: String { item.uid }

    enum CodingKeys: String, CodingKey {
        case item
        case changedFields = "changed_fields"
    }

    /// (field, before, after) triples, ordered so the UI is stable across renders.
    var deltas: [(field: String, before: String, after: String)] {
        changedFields.keys.sorted().map { key in
            let pair = changedFields[key] ?? []
            return (
                field: key,
                before: pair.first?.display ?? "—",
                after: pair.count > 1 ? (pair[1].display ?? "—") : "—"
            )
        }
    }
}

struct PageDiffDTO: Codable, Sendable, Hashable, Identifiable {
    let pageKey: String
    let label: String
    let added: [ItemDTO]
    let removed: [ItemDTO]
    let changed: [ChangedItemDTO]
    let count: Int
    let firstRun: Bool
    let screenshotPath: String?

    var id: String { pageKey }

    enum CodingKeys: String, CodingKey {
        case pageKey = "page_key"
        case label
        case added
        case removed
        case changed
        case count
        case firstRun = "first_run"
        case screenshotPath = "screenshot_path"
    }
}

struct ScanDetail: Codable, Sendable {
    let id: Int
    let startedAt: String
    let finishedAt: String?
    let status: String
    let error: String?
    let changeCount: Int
    let pages: [PageDiffDTO]

    enum CodingKeys: String, CodingKey {
        case id
        case startedAt = "started_at"
        case finishedAt = "finished_at"
        case status
        case error
        case changeCount = "change_count"
        case pages
    }

    var changedPages: [PageDiffDTO] { pages.filter { $0.count > 0 } }
}

struct HistoryEntry: Codable, Sendable, Identifiable, Hashable {
    let snapshotID: Int
    let scanID: Int
    let capturedAt: String
    let itemCount: Int
    let changeCount: Int
    let screenshotPath: String?

    var id: Int { snapshotID }

    enum CodingKeys: String, CodingKey {
        case snapshotID = "snapshot_id"
        case scanID = "scan_id"
        case capturedAt = "captured_at"
        case itemCount = "item_count"
        case changeCount = "change_count"
        case screenshotPath = "screenshot_path"
    }
}

struct SnapshotDetail: Codable, Sendable {
    let snapshotID: Int
    let items: [ItemDTO]

    enum CodingKeys: String, CodingKey {
        case snapshotID = "snapshot_id"
        case items
    }
}

struct LoginStart: Codable, Sendable {
    let sessionID: String
    let loginURL: String
    let mode: String

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case loginURL = "login_url"
        case mode
    }
}

struct LoginStatus: Codable, Sendable {
    let sessionID: String
    let status: String
    let detail: String?
    let loginURL: String?

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case status
        case detail
        case loginURL = "login_url"
    }

    var isPending: Bool { status == "pending" }
    var isAuthenticated: Bool { status == "authenticated" }
}

// MARK: - Date helpers

enum Format {
    /// The server emits Python's `datetime.isoformat()`, which looks like
    /// `2026-09-12T21:02:33.371011+00:00` — a colon in the UTC offset, and
    /// fractional seconds only when they happen to be non-zero. So both shapes
    /// have to be accepted.
    ///
    /// `ISO8601DateFormatter` would be the obvious tool but it is a non-Sendable
    /// class, which Swift 6 refuses to let us share as a static. `ISO8601FormatStyle`
    /// is a Sendable value type and parses the same thing.
    private static let parseStrategies: [Date.ISO8601FormatStyle] = [
        .init(timeZoneSeparator: .colon, includingFractionalSeconds: true),
        .init(timeZoneSeparator: .colon, includingFractionalSeconds: false),
        .init(includingFractionalSeconds: true),
        .init(includingFractionalSeconds: false),
    ]

    static func date(from string: String?) -> Date? {
        guard let string else { return nil }
        for strategy in parseStrategies {
            if let date = try? strategy.parse(string) { return date }
        }
        return nil
    }

    static func when(_ string: String) -> String {
        guard let date = date(from: string) else { return string }
        return date.formatted(.dateTime.month(.abbreviated).day().hour().minute())
    }

    static func relative(_ string: String?) -> String {
        guard let date = date(from: string) else { return "never" }
        let seconds = max(0, Date().timeIntervalSince(date))
        if seconds < 90 { return "just now" }
        let minutes = Int((seconds / 60).rounded())
        if minutes < 60 { return "\(minutes)m ago" }
        let hours = Int((Double(minutes) / 60).rounded())
        if hours < 24 { return "\(hours)h ago" }
        return "\(Int((Double(hours) / 24).rounded()))d ago"
    }

    static func plural(_ n: Int, _ one: String, _ many: String? = nil) -> String {
        "\(n) \(n == 1 ? one : (many ?? one + "s"))"
    }
}
