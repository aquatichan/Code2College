import Foundation

/// What a finished scan means for the person holding the phone.
struct ScanOutcome: Sendable {
    let scanID: Int
    let status: String
    /// Changes on pages the user hasn't muted.
    let notifiableChanges: Int
    let changedLabels: [String]
    /// True only on the scan that discovered the session had expired.
    let becameSignedOut: Bool
}

/// One scan: fetch every watched page → extract → diff → store.
///
/// Pages are fetched in parallel, which is what makes a full scan fit in the
/// few seconds iOS grants a background refresh. Each page fails on its own; one
/// broken page never loses the rest of the scan. A bounce to the login form
/// anywhere means the session is gone, so the scan stops and asks for sign-in.
actor Scanner {
    static let shared = Scanner()

    private var running = false
    private let store = LocalStore.shared

    /// Runs a scan unless one is already going (returns nil) or there is no
    /// session to scan with.
    func run(onProgress: @escaping @Sendable (String) async -> Void = { _ in }) async -> ScanOutcome? {
        guard !running, CookieVault.hasSession else { return nil }
        running = true
        defer { running = false }

        await store.closeInterruptedScans()
        let client = HirewheelClient()
        let scanID = await store.beginScan()
        let wasSignedOut = await store.status().needsReauth
        var signedOut = false
        var firstError: String?

        await onProgress("Checking \(Hirewheel.pages.count) pages…")
        let top = await fetchAll(Hirewheel.pages.map { ($0.key, $0.url) }, client: client)

        var children: [ChildPages.Child] = []
        for page in Hirewheel.pages {
            switch top[page.key] {
            case .success(let html):
                let parsed = Self.parse(html, extractor: page.key, discoverChildren: true)
                children += parsed.children
                await record(parsed, scanID: scanID, key: page.key, label: page.label, parentKey: nil, html: html)
            case .failure(FetchError.signedOut):
                signedOut = true
            case .failure(let error):
                firstError = firstError ?? Self.describe(error)
                await store.recordPageError(scanID: scanID, key: page.key, label: page.label, parentKey: nil, error: Self.describe(error))
            case nil:
                break
            }
        }

        if !signedOut && !children.isEmpty {
            await onProgress("Checking \(Format.plural(children.count, "detail page"))…")
            let fetched = await fetchAll(children.map { ($0.key, $0.url) }, client: client)
            for child in children {
                let parent = child.parentKey
                switch fetched[child.key] {
                case .success(let html):
                    let parsed = Self.parse(html, extractor: child.extractor, discoverChildren: false)
                    await record(parsed, scanID: scanID, key: child.key, label: child.label, parentKey: parent, html: html)
                case .failure(FetchError.signedOut):
                    signedOut = true
                case .failure(let error):
                    await store.recordPageError(scanID: scanID, key: child.key, label: child.label, parentKey: parent, error: Self.describe(error))
                case nil:
                    break
                }
            }
        }

        client.persistCookies()

        if signedOut {
            await store.setNeedsReauth(true)
            await store.finishScan(id: scanID, status: "auth_needed", error: "Signed out of Hirewheel")
            return ScanOutcome(scanID: scanID, status: "auth_needed", notifiableChanges: 0, changedLabels: [], becameSignedOut: !wasSignedOut)
        }

        let anyRead = top.values.contains { if case .success = $0 { true } else { false } }
        if !anyRead {
            // Offline, most likely. Not "no changes" — nothing was checked.
            await store.finishScan(id: scanID, status: "error", error: firstError ?? "Couldn't reach Hirewheel")
            return await outcome(scanID: scanID)
        }
        if Task.isCancelled {
            await store.finishScan(id: scanID, status: "error", error: "Ran out of time; some pages weren't checked")
        } else {
            await store.finishScan(id: scanID, status: "ok")
        }
        if wasSignedOut { await store.setNeedsReauth(false) }

        // Fill the account email in once, if sign-in couldn't.
        if await store.status().email == nil, let html = try? await client.fetch(Hirewheel.accountURL) {
            await store.setEmail(Self.loginEmail(in: html))
        }

        return await outcome(scanID: scanID)
    }

    /// Mark scans the app was killed during as failed. Lives here rather than on
    /// the store so it can never close the scan that is running right now.
    func closeInterruptedScans() async {
        guard !running else { return }
        await store.closeInterruptedScans()
    }

    // MARK: - Steps

    private func fetchAll(_ targets: [(String, URL)], client: HirewheelClient) async -> [String: Result<String, Error>] {
        await withTaskGroup(of: (String, Result<String, Error>).self) { group in
            for (key, url) in targets {
                group.addTask {
                    do {
                        return (key, .success(try await client.fetch(url)))
                    } catch {
                        return (key, .failure(error))
                    }
                }
            }
            var results: [String: Result<String, Error>] = [:]
            for await (key, result) in group { results[key] = result }
            return results
        }
    }

    private struct Parsed: Sendable {
        var items: [Item]?
        var error: String?
        var children: [ChildPages.Child] = []
    }

    /// Parse and extract in one synchronous step, so the (non-Sendable)
    /// document never leaves this function.
    private static func parse(_ html: String, extractor key: String, discoverChildren: Bool) -> Parsed {
        guard let extractor = Extractors.extractor(for: key) else {
            return Parsed(items: nil, error: "No extractor for this page")
        }
        let doc = HTMLElement.parse(html)
        // Discover first: some extractors strip page chrome as they go.
        let children = discoverChildren ? ChildPages.discover(key, doc) : []
        return Parsed(items: extractor(doc), children: children)
    }

    private func record(_ parsed: Parsed, scanID: Int, key: String, label: String, parentKey: String?, html: String) async {
        if let items = parsed.items {
            await store.recordPage(scanID: scanID, key: key, label: label, parentKey: parentKey, items: items, html: html)
        } else {
            await store.recordPageError(scanID: scanID, key: key, label: label, parentKey: parentKey, error: parsed.error ?? "Unknown error")
        }
    }

    private func outcome(scanID: Int) async -> ScanOutcome {
        let muted = Set(await store.status().mutedPages)
        let scan = await store.scan(id: scanID)
        // Muting a listing mutes the detail pages found on it too.
        let loud = (scan?.changedPages ?? []).filter { page in
            !muted.contains(page.pageKey) && !(page.parentKey.map(muted.contains) ?? false)
        }
        return ScanOutcome(
            scanID: scanID,
            status: scan?.status ?? "ok",
            notifiableChanges: loud.reduce(0) { $0 + $1.count },
            changedLabels: loud.map(\.label),
            becameSignedOut: false
        )
    }

    private static func describe(_ error: Error) -> String {
        if error is CancellationError || (error as? URLError)?.code == .cancelled {
            return "Ran out of time"
        }
        return error.localizedDescription
    }

    // MARK: - Account

    /// The account holder's login email from /account markup.
    ///
    /// The page also shows a parent/guardian address. That belongs to someone
    /// who never agreed to use this app, so only the address labelled as the
    /// *current login email* is taken, and the guardian's is never stored.
    static func loginEmail(in html: String) -> String? {
        guard let regex = try? Regex(#"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"#) else { return nil }
        let root = Extractors.mainOf(HTMLElement.parse(html))

        // Every piece of text with an address in it, and the element holding it.
        let found = root.allElements().flatMap { el in
            el.nodes.compactMap { node -> (String, HTMLElement)? in
                guard case .text(let value) = node, let match = value.firstMatch(of: regex) else { return nil }
                return (String(value[match.range]), el)
            }
        }
        for (address, el) in found {
            // Walk up until there's enough surrounding text to read the label.
            var box: HTMLElement? = el
            for _ in 0..<4 {
                guard let current = box, current.parent != nil else { break }
                let context = current.spacedText.lowercased()
                if let label = context.range(of: "current login email") {
                    // Guard against a container so big it swallowed both addresses.
                    if !context[..<label.lowerBound].suffix(60).contains("parent") { return address }
                }
                if context.count > 30 { break }
                box = current.parent
            }
        }
        return nil
    }
}
