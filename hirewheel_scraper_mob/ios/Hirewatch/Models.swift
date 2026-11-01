import CryptoKit
import Foundation

// MARK: - JSON values

/// An extractor's `fields` dictionary is deliberately open-ended — a
/// notification carries a body and timestamp, a survey carries a status, and so
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

    // Field builders for extractors. Each returns nil for an empty value, and
    // `Item.make` drops nils, so "no body" and "empty body" hash the same.
    static func text(_ value: String?) -> JSONValue? {
        guard let value, !value.isEmpty else { return nil }
        return .string(value)
    }

    static func list(_ values: [String]) -> JSONValue? {
        values.isEmpty ? nil : .array(values.map(JSONValue.string))
    }

    static func int(_ value: Int) -> JSONValue? { .number(Double(value)) }
}

// MARK: - Items

/// One thing on a page: a notification, a project card, a survey row, etc.
///
/// `uid` is the stable identity used to tell items apart across scans. Prefer a
/// real id from the page (data-notif-id, an href); otherwise one is derived from
/// the title.
///
/// `fields` holds the meaningful, human-visible content. Its hash decides
/// whether an item *changed* between scans, so only signal goes in — never
/// volatile noise like "2 minutes ago".
struct Item: Codable, Sendable, Hashable, Identifiable {
    let uid: String
    let kind: String
    let title: String
    let fields: [String: JSONValue]
    let hash: String

    var id: String { uid }

    static func make(
        _ kind: String,
        _ title: String,
        uid: String? = nil,
        _ fields: [String: JSONValue?] = [:]
    ) -> Item {
        let clean = fields.compactMapValues { $0 }
        return Item(
            uid: uid ?? "\(kind):\(slug(title))",
            kind: kind,
            title: title,
            fields: clean,
            hash: contentHash(title: title, fields: clean)
        )
    }

    /// The single most useful supporting line for this item, if it has one.
    var detail: String? {
        for key in ["body", "detail", "status", "ts"] {
            if let value = fields[key]?.display { return value }
        }
        return nil
    }

    private static let hashEncoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }()

    private static func contentHash(title: String, fields: [String: JSONValue]) -> String {
        let payload = (try? hashEncoder.encode(fields)) ?? Data()
        var hasher = Insecure.SHA1()
        hasher.update(data: payload)
        hasher.update(data: Data("||\(title)".utf8))
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

/// A stable, URL-safe id derived from text (the fallback when no real id exists).
func slug(_ text: String) -> String {
    let lowered = text.split(whereSeparator: \.isWhitespace).joined(separator: " ").lowercased()
    var out = ""
    var pendingDash = false
    for scalar in lowered.unicodeScalars {
        if ("a"..."z").contains(scalar) || ("0"..."9").contains(scalar) {
            if pendingDash && !out.isEmpty { out.append("-") }
            out.unicodeScalars.append(scalar)
            pendingDash = false
        } else {
            pendingDash = true
        }
    }
    let capped = String(out.prefix(80))
    return capped.isEmpty ? "item" : capped
}

struct ItemChange: Codable, Sendable, Hashable, Identifiable {
    let item: Item
    /// field -> [before, after]
    let changedFields: [String: [JSONValue]]

    var id: String { item.uid }

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

// MARK: - Scans

/// What one scan found on one page.
struct PageDiff: Codable, Sendable, Hashable, Identifiable {
    let pageKey: String
    let label: String
    /// The listing a detail page was found on ("news" for "news:364").
    var parentKey: String?
    var added: [Item] = []
    var removed: [Item] = []
    var changed: [ItemChange] = []
    var itemCount = 0
    /// No earlier copy of this page existed, so this scan recorded it silently.
    var firstRun = false
    /// The stored copy of the page, saved whenever its content changed.
    var snapshotID: Int?
    var error: String?

    var id: String { pageKey }
    var count: Int { added.count + removed.count + changed.count }
}

struct ScanSummary: Sendable, Identifiable, Hashable {
    let id: Int
    let startedAt: String
    let finishedAt: String?
    let status: String
    let error: String?
    let changeCount: Int

    var failed: Bool { status == "error" || status == "auth_needed" }
}

/// One scan in full, as stored on the phone.
struct ScanDetail: Codable, Sendable, Identifiable {
    let id: Int
    let startedAt: String
    var finishedAt: String?
    var status: String
    var error: String?
    var pages: [PageDiff] = []

    var changeCount: Int { pages.reduce(0) { $0 + $1.count } }
    var changedPages: [PageDiff] { pages.filter { $0.count > 0 } }

    var summary: ScanSummary {
        ScanSummary(
            id: id, startedAt: startedAt, finishedAt: finishedAt,
            status: status, error: error, changeCount: changeCount
        )
    }
}

/// One distinct state a page has been in. A new one is recorded only when the
/// page's content changes, so the timeline shows real changes, not repeats.
struct HistoryEntry: Sendable, Identifiable, Hashable {
    let snapshotID: Int
    let scanID: Int
    let capturedAt: String
    let label: String
    let itemCount: Int
    let changeCount: Int

    var id: Int { snapshotID }
}

struct PageInfo: Sendable, Identifiable, Hashable {
    let key: String
    let label: String
    let url: URL

    var id: String { key }
}

// MARK: - Date helpers

enum Format {
    /// Stored timestamps are ISO 8601. Fractional seconds and a colon in the
    /// offset are both accepted, in case an older value carries them.
    ///
    /// `ISO8601DateFormatter` would be the obvious tool but it is a non-Sendable
    /// class, which Swift 6 refuses to let us share as a static. `ISO8601FormatStyle`
    /// is a Sendable value type and parses the same thing.
    private static let parseStrategies: [Date.ISO8601FormatStyle] = [
        .init(includingFractionalSeconds: false),
        .init(includingFractionalSeconds: true),
        .init(timeZoneSeparator: .colon, includingFractionalSeconds: true),
        .init(timeZoneSeparator: .colon, includingFractionalSeconds: false),
    ]

    static func stamp(_ date: Date = .now) -> String {
        date.formatted(.iso8601)
    }

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
