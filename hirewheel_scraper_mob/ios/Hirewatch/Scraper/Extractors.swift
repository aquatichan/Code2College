import CryptoKit
import Foundation

/// Per-page extractors: turn a page's HTML into structured `Item`s.
///
/// A line-for-line port of the server's `hwcore/extractors`, which were written
/// against the live markup. The selectors and the reasoning behind each one
/// (what counts as signal, what is deliberately ignored) carry over unchanged;
/// when a page's markup moves, fix it in both places.
enum Extractors {
    typealias Extractor = @Sendable (HTMLElement) -> [Item]

    static func extractor(for key: String) -> Extractor? {
        registry[key]
    }

    private static let registry: [String: Extractor] = [
        "notifications": notifications,
        "internship_prep": internshipPrep,
        "marketplace": marketplace,
        "college_pathways": collegePathways,
        "modules": learningModules,
        "surveys": surveys,
        "news": news,
        "program": program,
        "program_assignments": { cardsOrSignature("assignment", "Assignments", "program_assignments", $0) },
        "program_ai_training": { cardsOrSignature("program_track", "AI Training", "program_ai_training", $0) },
        "program_fall": { cardsOrSignature("program_track", "Fall 2026", "program_fall", $0) },
        // Live classes: Zoom links, schedules, syllabus links.
        "program_courses": { cardsOrSignature("course", "Live Courses", "program_courses", $0) },
        // Loads client-side and may render an error state; the signature covers both.
        "program_history": { cardsOrSignature("history", "History", "program_history", $0) },
        "marketplace_examples": marketplaceExamples,
        "special_events": specialEvents,
        "my_projects": myProjects,
        "meetings": meetings,
        ChildPages.newsArticle: newsArticle,
        ChildPages.eventDetail: eventDetail,
    ]

    // MARK: - Pages

    /// `a.notif-item` carries `data-notif-id`, a rock-solid stable id.
    static func notifications(_ doc: HTMLElement) -> [Item] {
        doc.select("a.notif-item, [data-item-type='notification']").map { node in
            let notifID = node.attr("data-notif-id")
            let title = (node.first("p.mb-1") ?? node.first("p"))?.text ?? ""

            let timeEl = node.first(".notif-time")
            let timeText = timeEl?.text ?? ""
            let ts = timeEl?.attr("data-ts")?.nonEmpty ?? timeText

            // Body = the item's text minus the title and the timestamp label.
            var body = node.spacedText
            if !title.isEmpty { body = removingFirst(title, from: body) }
            if !timeText.isEmpty { body = removingFirst(timeText, from: body) }

            return Item.make(
                "notification",
                title.nonEmpty ?? "(untitled notification)",
                uid: notifID?.nonEmpty.map { "notification:\($0)" },
                [
                    "body": .text(clean(body)),
                    "action_url": .text(node.attr("data-action-url")),
                    "ts": .text(ts),
                ]
            )
        }
    }

    /// Each project is an `article.elite102-card`; status changes (Not Started →
    /// In Progress → Completed) are tracked.
    static func internshipPrep(_ doc: HTMLElement) -> [Item] {
        doc.select("article.elite102-card").map { card in
            let href = card.first("a.elite102-card__btn")?.attr("href")
            return Item.make(
                "prep_project",
                text(card, ".elite102-card__title").nonEmpty ?? "(untitled project)",
                uid: href?.nonEmpty.map { "prep_project:\($0)" },
                [
                    "category": .text(text(card, ".elite102-card__category")),
                    "description": .text(text(card, ".elite102-card__description")),
                    "status": .text(text(card, ".elite102-card__status")),
                    "tags": .list(texts(card, ".elite102-card__tag")),
                    "href": .text(href),
                ]
            )
        }
    }

    /// The highest-signal page: a new `a.pj-card` is a fresh paid opportunity.
    /// The "interest window closing in…" countdown is deliberately skipped so a
    /// ticking timer never reads as a change.
    static func marketplace(_ doc: HTMLElement) -> [Item] {
        doc.select("a.pj-card").map { card in
            let href = card.attr("href")
            return Item.make(
                "marketplace_project",
                text(card, ".pj-title, h3, h2").nonEmpty ?? "(untitled project)",
                uid: href?.nonEmpty.map { "marketplace:\($0)" },
                [
                    "goal": .text(text(card, ".goal")),
                    "platforms": .text(text(card, ".platforms")),
                    "xp": .text(text(card, ".xp")),
                    "pills": .list(texts(card, ".pill")),
                    "href": .text(href),
                ]
            )
        }
    }

    /// "More coming soon": the signal is a new partner appearing.
    static func collegePathways(_ doc: HTMLElement) -> [Item] {
        doc.select("a.cp-partner-card, .cp-partner-grid .cp-partner-card").map { card in
            let href = card.tag == "a" ? card.attr("href") : nil
            return Item.make(
                "college_partner",
                text(card, ".cp-partner-name").nonEmpty ?? "(unnamed partner)",
                uid: href.flatMap { $0.isEmpty || $0 == "#" ? nil : "college_partner:\($0)" },
                [
                    "tagline": .text(text(card, ".cp-partner-tagline")),
                    "tags": .list(texts(card, ".cp-partner-tag")),
                    "cta": .text(text(card, ".cp-partner-cta")),
                    "href": .text(href),
                ]
            )
        }
    }

    /// New modules and activities. `data-status` and "x / y complete" are
    /// dropped on purpose: they track the student's own progress and would
    /// flood the feed every time they finished an activity.
    static func learningModules(_ doc: HTMLElement) -> [Item] {
        var items: [Item] = []
        for module in doc.select("section.learning-module") {
            let title = text(module, ".learning-module__title").nonEmpty ?? "(untitled module)"
            let moduleSlug = slug(title)
            items.append(Item.make(
                "learning_module", title, uid: "learning_module:\(moduleSlug)",
                ["description": .text(text(module, ".learning-module__description"))]
            ))
            for activity in module.select("li.learning-activity") {
                let actTitle = text(activity, ".learning-activity__title").nonEmpty ?? "(untitled activity)"
                items.append(Item.make(
                    "learning_activity", actTitle,
                    uid: "learning_activity:\(moduleSlug):\(slug(actTitle))",
                    ["xp": .text(text(activity, ".learning-activity__xp")), "module": .text(title)]
                ))
            }
        }
        return items
    }

    /// Surveys grouped under "Available now" / "Completed" headers; each card is
    /// tagged with the section it sits under.
    static func surveys(_ doc: HTMLElement) -> [Item] {
        var items: [Item] = []
        var section: String?
        for el in mainOf(doc).allElements() {
            if el.tag == "h5" && el.hasClass("text-uppercase") {
                section = el.text
            } else if el.tag == "div" && el.hasClass("card") {
                let link = el.first("a[href]") ?? el.ancestor { $0.tag == "a" && $0.hasAttr("href") }
                items.append(Item.make(
                    "survey",
                    text(el, ".fw-semibold").nonEmpty ?? "(untitled survey)",
                    [
                        "section": .text(section),
                        "status": .text(el.first(".text-muted")?.text),
                        "href": .text(link?.attr("href")),
                    ]
                ))
            }
        }
        return items
    }

    /// Every issue is listed as `a.news-sidebar-item`; the id in its href is the uid.
    static func news(_ doc: HTMLElement) -> [Item] {
        doc.select("a.news-sidebar-item").map { link in
            let href = link.attr("href")
            return Item.make(
                "news_issue",
                text(link, ".news-sidebar-item-title").nonEmpty ?? "(untitled issue)",
                uid: href?.nonEmpty.map { "news:\($0)" },
                ["date": .text(text(link, ".news-sidebar-item-date")), "href": .text(href)]
            )
        }
    }

    /// Deliverables are required program tasks, so status changes (a new one,
    /// or one going overdue) are tracked here.
    static func program(_ doc: HTMLElement) -> [Item] {
        doc.select("a[href^='#deliverable-']").map { row in
            let href = row.attr("href") ?? ""
            let title = text(row, ".fw-semibold")
            var detail = text(row, ".text-muted, .small")
            // The sub text repeats the title as a prefix; trim it for a clean line.
            if !title.isEmpty && detail.hasPrefix(title) {
                detail = String(detail.dropFirst(title.count))
                    .trimmingCharacters(in: CharacterSet(charactersIn: " ·"))
            }
            return Item.make(
                "deliverable",
                title.nonEmpty ?? "(deliverable)",
                uid: "deliverable:\(href.drop { $0 == "#" })",
                ["status": .text(row.first(".badge")?.text), "detail": .text(detail)]
            )
        }
    }

    static func marketplaceExamples(_ doc: HTMLElement) -> [Item] {
        let cards = bodyWithoutChrome(doc).select("a.pj-card")
        if !cards.isEmpty {
            return cards.map { cardItem("marketplace_example", $0) }
        }
        return cardsOrSignature("marketplace_example", "Marketplace Examples", "marketplace_examples", doc)
    }

    /// Both tab panels are in the DOM. Events have no stable id, so the title
    /// plus which panel it came from is the key.
    static func specialEvents(_ doc: HTMLElement) -> [Item] {
        var items: [Item] = []
        for (panelID, status) in [("current-events", "current"), ("past-events", "past")] {
            guard let panel = doc.first("#\(panelID)") else { continue }
            for heading in panel.select("h3.fw-bold") {
                let title = heading.text.nonEmpty ?? "(untitled event)"
                let section = heading.ancestor { $0.tag == "section" } ?? heading.parent
                items.append(Item.make(
                    "event", title, uid: "event:\(status):\(slug(title))",
                    [
                        "status": .text(status),
                        "when": .text(section?.first("p.text-muted")?.text),
                        "badges": .list(section.map { texts($0, ".badge") } ?? []),
                        "href": .text((section?.first("a[href]")?.attr("href")).map(stripQuery)),
                    ]
                ))
            }
        }
        return items
    }

    /// Empty when this was written, so the card selectors are best-effort and the
    /// whole-page signature makes sure a real change is still caught.
    static func myProjects(_ doc: HTMLElement) -> [Item] {
        let main = mainOf(doc)
        if looksEmpty(main, markers: ["no assigned projects"]) { return [] }
        let cards = main.select(".card, article, .list-group-item, .pj-card")
        if !cards.isEmpty {
            return cards.map { cardItem("assigned_project", $0) }
        }
        return [pageSignatureItem("My Assigned Projects", "my_projects", main)]
    }

    /// The empty state is itself a `.meeting-card`, so detect it by its text
    /// before treating `.meeting-card`s as real interviews.
    static func meetings(_ doc: HTMLElement) -> [Item] {
        let main = mainOf(doc)
        if main.spacedText.lowercased().contains("no interviews scheduled") { return [] }
        let cards = main.select(".meeting-card")
        if !cards.isEmpty {
            return cards.map { cardItem("interview", $0) }
        }
        return [pageSignatureItem("My Meetings", "meetings", main)]
    }

    // MARK: - Detail pages

    /// Only the article's own body: the page also lists every other issue in a
    /// sidebar, so hashing the whole page would make every article look changed
    /// the moment a new one is published.
    static func newsArticle(_ doc: HTMLElement) -> [Item] {
        let body = doc.first(".news-reader-body") ?? bodyWithoutChrome(doc, extra: [])
        let meta = doc.first(".news-reader-meta")?.spacedText

        var items: [Item] = []
        // Sections give a diff something specific to point at when an issue is edited.
        for section in body.select(".nl-section-banner, .nl-callout-body") {
            let sectionText = section.spacedText
            let title = String(sectionText.prefix(70))
            guard !title.isEmpty else { continue }
            items.append(Item.make(
                "news_section", title, uid: "news_section:\(signature(title))",
                ["body": .text(String(sectionText.prefix(400)))]
            ))
        }

        // Plus one item covering the whole article, so an edit outside a
        // recognised section is still caught.
        let all = body.spacedText
        items.append(Item.make(
            "news_article",
            meta.map { String($0.prefix(70)) }?.nonEmpty ?? "Article",
            uid: "news_article",
            ["published": .text(meta), "length": .int(all.count), "signature": .text(signature(all))]
        ))
        return items
    }

    static func eventDetail(_ doc: HTMLElement) -> [Item] {
        let body = bodyWithoutChrome(doc, extra: [])
        let all = body.spacedText
        return [Item.make(
            "event_detail", body.first("h1, h2")?.spacedText ?? "Event", uid: "event_detail",
            [
                "badges": .list(texts(body, ".badge")),
                "detail": .text(String(all.prefix(400))),
                "signature": .text(signature(all)),
            ]
        )]
    }

    // MARK: - Shared

    /// The tab strip and breadcrumbs repeat on every Program Hub tab; hashing
    /// them would make every tab look identical and mask real changes.
    private static let chrome = ["nav", "header", "footer", ".navbar", ".breadcrumb"]
    private static let tabChrome = [".nav-tabs", ".nav-pills"]

    /// Real cards become items; an unrecognised layout is hashed into one
    /// `page_change` item, so a change is never silently missed.
    static func cardsOrSignature(_ kind: String, _ label: String, _ pageKey: String, _ doc: HTMLElement) -> [Item] {
        let body = bodyWithoutChrome(doc)
        let cards = body.select(".card")
        if !cards.isEmpty {
            // A card carrying no readable text is noise, not content.
            return cards.map { cardItem(kind, $0) }.filter { !$0.title.isEmpty && $0.title != "(item)" }
        }
        return [pageSignatureItem(label, pageKey, body)]
    }

    /// Best-effort conversion of a generic card/list item into an Item.
    static func cardItem(_ kind: String, _ card: HTMLElement) -> Item {
        let head = card.first("h1, h2, h3, h4, h5") ?? card.first(".fw-semibold, .title")
        let title = head?.text ?? (String(card.text.prefix(60)).nonEmpty ?? "(item)")
        let href = (card.first("a[href]")?.attr("href")).map(stripQuery)

        var sub: String?
        for selector in [".text-muted", ".small", "p"] {
            let candidate = text(card, selector)
            if !candidate.isEmpty && candidate != title {
                sub = candidate
                break
            }
        }

        return Item.make(
            kind, title,
            uid: href.map { "\(kind):\($0)" } ?? "\(kind):\(slug(title))",
            ["status": .text(card.first(".badge")?.text), "detail": .text(sub), "href": .text(href)]
        )
    }

    /// A single item whose hash covers the whole page — the last-resort net.
    static func pageSignatureItem(_ label: String, _ pageKey: String, _ root: HTMLElement) -> Item {
        Item.make("page_change", "\(label) — page changed", uid: "page:\(pageKey)", ["signature": .text(signature(root.spacedText))])
    }

    static func mainOf(_ doc: HTMLElement) -> HTMLElement {
        doc.first("main") ?? doc
    }

    private static func bodyWithoutChrome(_ doc: HTMLElement, extra: [String] = tabChrome) -> HTMLElement {
        let main = mainOf(doc)
        for selector in chrome + extra {
            for node in main.select(selector) { node.remove() }
        }
        return main
    }

    /// True if an empty-state alert containing one of the marker phrases is present.
    private static func looksEmpty(_ main: HTMLElement, markers: [String]) -> Bool {
        guard main.first(".alert") != nil else { return false }
        let pageText = main.spacedText.lowercased()
        return markers.contains { pageText.contains($0.lowercased()) }
    }

    // MARK: - Helpers

    static func clean(_ text: String?) -> String {
        (text ?? "").split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    static func text(_ root: HTMLElement, _ css: String) -> String {
        root.first(css)?.text ?? ""
    }

    static func texts(_ root: HTMLElement, _ css: String) -> [String] {
        root.select(css).map(\.text)
    }

    static func stripQuery(_ href: String) -> String {
        String(href.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false).first ?? "")
    }

    static func signature(_ text: String) -> String {
        let hex = Insecure.SHA1.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
        return String(hex.prefix(12))
    }

    private static func removingFirst(_ needle: String, from haystack: String) -> String {
        guard let range = haystack.range(of: needle) else { return haystack }
        return haystack.replacingCharacters(in: range, with: "")
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}

// MARK: - Detail pages

/// Detail pages linked from a listing.
///
/// Some content only exists one level down: a newsletter's text lives on
/// `/news/364`, not on the index. This is deliberately *not* a crawler — only
/// listings with a small, useful set of children are followed, and each is
/// capped. (Learning Modules links to ~190 module pages; following those would
/// turn a few-second scan into minutes.)
enum ChildPages {
    static let newsArticle = "_child:news_article"
    static let eventDetail = "_child:event_detail"

    /// Never follow more than this many from one listing, whatever it says.
    static let maxPerPage = 12

    struct Child: Sendable {
        let key: String        // stable across scans, e.g. "news:364"
        let parentKey: String  // the listing it was found on
        let url: URL
        let label: String
        let extractor: String
    }

    static func discover(_ pageKey: String, _ doc: HTMLElement) -> [Child] {
        switch pageKey {
        case "news": return Array(news(doc).prefix(maxPerPage))
        case "special_events": return Array(events(doc).prefix(maxPerPage))
        default: return []
        }
    }

    private static func links(_ doc: HTMLElement, prefix: String) -> [(href: String, ident: String, text: String)] {
        var out: [(String, String, String)] = []
        var seen: Set<String> = []
        for link in Extractors.mainOf(doc).select("a[href^='\(prefix)']") {
            var href = Extractors.stripQuery(link.attr("href") ?? "")
            while href.hasSuffix("/") { href.removeLast() }
            let ident = String(href.split(separator: "/").last ?? "")
            guard !ident.isEmpty, seen.insert(href).inserted else { continue }
            out.append((href, ident, link.spacedText))
        }
        return out
    }

    private static func news(_ doc: HTMLElement) -> [Child] {
        // Only numeric issue ids; skip the index and any category links.
        links(doc, prefix: "/news/").filter { $0.ident.allSatisfy(\.isNumber) }.map { link in
            Child(
                key: "news:\(link.ident)",
                parentKey: "news",
                url: Hirewheel.url(link.href),
                label: "Newsfeed · \(String(link.text.prefix(60)).nonEmpty ?? "Issue \(link.ident)")",
                extractor: newsArticle
            )
        }
    }

    private static func events(_ doc: HTMLElement) -> [Child] {
        links(doc, prefix: "/events/").map { link in
            Child(
                key: "event:\(link.ident)",
                parentKey: "special_events",
                url: Hirewheel.url(link.href),
                label: "Event · \(String(link.text.prefix(60)).nonEmpty ?? link.ident)",
                extractor: eventDetail
            )
        }
    }
}
