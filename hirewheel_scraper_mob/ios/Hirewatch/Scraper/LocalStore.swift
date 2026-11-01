import Foundation

/// Everything Hirewatch knows, kept on the phone.
///
/// One small JSON index holds the scans, the last-seen items per page (the
/// baseline each scan diffs against) and settings. The heavy part — a copy of
/// each page's HTML — is written as its own file, and only when the page's
/// content actually changed. Repeats of the same state cost nothing, so the
/// history shows every state a page has been in without filling the phone.
actor LocalStore {
    static let shared = LocalStore()

    /// Unchanged and failed scans are dropped after this long. Scans that found
    /// something are the interesting history and are kept (up to `maxScans`).
    static let retention: TimeInterval = 3 * 24 * 60 * 60
    static let maxScans = 300
    static let maxSnapshotsPerPage = 60

    struct Status: Sendable {
        var email: String?
        var needsReauth = false
        var lastScanAt: String?
        var mutedPages: [String] = []
    }

    private struct SnapshotRef: Codable {
        let id: Int
        let scanID: Int
        let capturedAt: String
        let label: String
        let itemCount: Int
        let changeCount: Int
    }

    private struct Index: Codable {
        var nextScanID = 1
        var nextSnapshotID = 1
        var scans: [ScanDetail] = []                 // newest first
        var baseline: [String: [Item]] = [:]         // page key -> last good items
        var snapshots: [String: [SnapshotRef]] = [:] // page key -> newest first
        var email: String?
        var needsReauth = false
        var mutedPages: [String] = []
    }

    private var index: Index
    private let root: URL

    private init() {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        root = support.appendingPathComponent("Hirewatch", isDirectory: true)
        try? FileManager.default.createDirectory(at: root.appendingPathComponent("snapshots"), withIntermediateDirectories: true)
        index = (try? Data(contentsOf: root.appendingPathComponent("index.json")))
            .flatMap { try? JSONDecoder().decode(Index.self, from: $0) } ?? Index()
    }

    // MARK: - Reads

    func status() -> Status {
        Status(
            email: index.email,
            needsReauth: index.needsReauth,
            lastScanAt: index.scans.first { $0.status == "ok" }?.startedAt,
            mutedPages: index.mutedPages
        )
    }

    func scans(limit: Int = 50) -> [ScanSummary] {
        index.scans.prefix(limit).map(\.summary)
    }

    func scan(id: Int) -> ScanDetail? {
        index.scans.first { $0.id == id }
    }

    func history(pageKey: String) -> [HistoryEntry] {
        (index.snapshots[pageKey] ?? []).map {
            HistoryEntry(
                snapshotID: $0.id, scanID: $0.scanID, capturedAt: $0.capturedAt,
                label: $0.label, itemCount: $0.itemCount, changeCount: $0.changeCount
            )
        }
    }

    func snapshotItems(id: Int) -> [Item] {
        (try? Data(contentsOf: itemsFile(id)))
            .flatMap { try? JSONDecoder().decode([Item].self, from: $0) } ?? []
    }

    /// The saved HTML for a snapshot, if it is still on disk.
    func snapshotHTML(id: Int) -> String? {
        try? String(contentsOf: htmlFile(id), encoding: .utf8)
    }

    // MARK: - Settings

    func setMutedPages(_ keys: [String]) {
        index.mutedPages = keys.sorted()
        save()
    }

    func setEmail(_ email: String?) {
        index.email = email
        save()
    }

    func setNeedsReauth(_ value: Bool) {
        index.needsReauth = value
        save()
    }

    // MARK: - Scans

    func beginScan() -> Int {
        let id = index.nextScanID
        index.nextScanID += 1
        index.scans.insert(ScanDetail(id: id, startedAt: Format.stamp(), status: "running"), at: 0)
        save()
        return id
    }

    /// Diff a freshly extracted page against its baseline and record the result.
    func recordPage(
        scanID: Int, key: String, label: String, parentKey: String?,
        items: [Item], html: String
    ) {
        let old = index.baseline[key]
        var page = diffPage(key: key, label: label, old: old ?? [], new: items, firstRun: old == nil)
        page.parentKey = parentKey
        page.itemCount = items.count

        // Only a new state is worth a copy of the page.
        if old == nil || page.count > 0 {
            let snapID = index.nextSnapshotID
            index.nextSnapshotID += 1
            do {
                try JSONEncoder().encode(items).write(to: itemsFile(snapID), options: .atomic)
                try Data(html.utf8).write(to: htmlFile(snapID), options: .atomic)
                page.snapshotID = snapID
                index.snapshots[key, default: []].insert(
                    SnapshotRef(
                        id: snapID, scanID: scanID, capturedAt: Format.stamp(),
                        label: label, itemCount: items.count, changeCount: page.count
                    ),
                    at: 0
                )
                trimSnapshots(key)
            } catch {
                print("[store] could not save snapshot for \(key): \(error)")
            }
        }

        index.baseline[key] = items
        append(page, to: scanID)
    }

    /// A page that couldn't be read. Its baseline is left alone, so the next
    /// scan still diffs against the last *good* state — an empty snapshot would
    /// read as "everything was removed".
    func recordPageError(scanID: Int, key: String, label: String, parentKey: String?, error: String) {
        var page = PageDiff(pageKey: key, label: label)
        page.parentKey = parentKey
        page.error = error
        append(page, to: scanID)
    }

    func finishScan(id: Int, status: String, error: String? = nil) {
        if let i = index.scans.firstIndex(where: { $0.id == id }) {
            index.scans[i].status = status
            index.scans[i].error = error
            index.scans[i].finishedAt = Format.stamp()
        }
        prune()
        save()
    }

    /// iOS can end the app mid-scan (most often a background scan running out
    /// of time). Without this the feed would show "Scanning…" forever.
    func closeInterruptedScans() {
        var changed = false
        for i in index.scans.indices where index.scans[i].status == "running" {
            index.scans[i].status = "error"
            index.scans[i].error = "Interrupted before it finished"
            index.scans[i].finishedAt = index.scans[i].finishedAt ?? Format.stamp()
            changed = true
        }
        if changed { save() }
    }

    /// Sign-out keeps history; this is the "delete everything" path.
    func deleteAll() {
        try? FileManager.default.removeItem(at: root)
        try? FileManager.default.createDirectory(at: root.appendingPathComponent("snapshots"), withIntermediateDirectories: true)
        index = Index()
    }

    // MARK: - Internals

    private func append(_ page: PageDiff, to scanID: Int) {
        guard let i = index.scans.firstIndex(where: { $0.id == scanID }) else { return }
        index.scans[i].pages.append(page)
    }

    private func prune() {
        let cutoff = Date().addingTimeInterval(-Self.retention)
        let newest = index.scans.first?.id
        index.scans.removeAll { scan in
            guard scan.id != newest, scan.status != "running" else { return false }
            let old = (Format.date(from: scan.startedAt) ?? .distantPast) < cutoff
            return old && (scan.summary.failed || scan.changeCount == 0)
        }
        if index.scans.count > Self.maxScans {
            index.scans.removeLast(index.scans.count - Self.maxScans)
        }
    }

    private func trimSnapshots(_ key: String) {
        guard var refs = index.snapshots[key], refs.count > Self.maxSnapshotsPerPage else { return }
        for ref in refs[Self.maxSnapshotsPerPage...] {
            try? FileManager.default.removeItem(at: itemsFile(ref.id))
            try? FileManager.default.removeItem(at: htmlFile(ref.id))
        }
        refs.removeLast(refs.count - Self.maxSnapshotsPerPage)
        index.snapshots[key] = refs
    }

    private func save() {
        do {
            let data = try JSONEncoder().encode(index)
            // Readable after first unlock, so background scans can write it
            // while the phone is locked.
            try data.write(
                to: root.appendingPathComponent("index.json"),
                options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication]
            )
        } catch {
            print("[store] save failed: \(error)")
        }
    }

    private func itemsFile(_ id: Int) -> URL {
        root.appendingPathComponent("snapshots/\(id).json")
    }

    private func htmlFile(_ id: Int) -> URL {
        root.appendingPathComponent("snapshots/\(id).html")
    }
}

// MARK: - Diff

/// Diff by stable uid: added = new uids, removed = gone uids, changed = same uid
/// but a different content hash.
///
/// On the very first scan of a page there is nothing to compare against, so it
/// is seeded silently rather than reporting every existing item as new.
func diffPage(key: String, label: String, old: [Item], new: [Item], firstRun: Bool) -> PageDiff {
    var result = PageDiff(pageKey: key, label: label, firstRun: firstRun)
    guard !firstRun else { return result }

    let oldByUID = Dictionary(old.map { ($0.uid, $0) }, uniquingKeysWith: { first, _ in first })
    let newUIDs = Set(new.map(\.uid))
    var seen: Set<String> = []

    for item in new where seen.insert(item.uid).inserted {
        guard let before = oldByUID[item.uid] else {
            result.added.append(item)
            continue
        }
        if before.hash != item.hash {
            result.changed.append(ItemChange(item: item, changedFields: fieldDeltas(before, item)))
        }
    }
    var gone: Set<String> = []
    for item in old where !newUIDs.contains(item.uid) && gone.insert(item.uid).inserted {
        result.removed.append(item)
    }
    return result
}

/// Which fields differ, before vs after (the title counts as a field).
private func fieldDeltas(_ old: Item, _ new: Item) -> [String: [JSONValue]] {
    var deltas: [String: [JSONValue]] = [:]
    if old.title != new.title {
        deltas["title"] = [.string(old.title), .string(new.title)]
    }
    for key in Set(old.fields.keys).union(new.fields.keys) {
        let before = old.fields[key] ?? .null
        let after = new.fields[key] ?? .null
        if before != after { deltas[key] = [before, after] }
    }
    return deltas
}
