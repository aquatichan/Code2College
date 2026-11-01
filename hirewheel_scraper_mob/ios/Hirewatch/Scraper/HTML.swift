import Foundation
import libxml2

/// A small HTML DOM with CSS selectors, built on the libxml2 parser that ships
/// with iOS.
///
/// The extractors need only a narrow slice of what a browser or BeautifulSoup
/// offers: parse forgiving real-world HTML, select by simple CSS, read text and
/// attributes. libxml2 does the hard part (tolerating broken markup); this file
/// turns its tree into plain Swift objects and matches selectors against them.
/// No third-party code, nothing to download.
///
/// Supported selectors: `tag`, `*`, `.class`, `#id`, `[attr]`, `[attr=v]`,
/// `[attr^=v]`, `[attr$=v]`, `[attr*=v]`, `[attr~=v]` (values quoted or not),
/// compounds of those, the descendant (space) and child (`>`) combinators, and
/// comma-separated groups. That covers every extractor; add more here if one
/// ever needs it.
final class HTMLElement {
    enum Node {
        case element(HTMLElement)
        case text(String)
    }

    let tag: String
    let attributes: [String: String]
    fileprivate(set) var nodes: [Node] = []
    fileprivate(set) weak var parent: HTMLElement?

    fileprivate init(tag: String, attributes: [String: String]) {
        self.tag = tag
        self.attributes = attributes
    }

    // MARK: - Parsing

    /// Parse a whole page. The returned root is a synthetic document node, so
    /// `select` from it reaches every element, `<html>` included.
    static func parse(_ html: String) -> HTMLElement {
        _ = initialized
        let root = HTMLElement(tag: "#document", attributes: [:])
        let options = Int32(HTML_PARSE_RECOVER.rawValue | HTML_PARSE_NOERROR.rawValue
            | HTML_PARSE_NOWARNING.rawValue | HTML_PARSE_NONET.rawValue)
        let utf8 = Array(html.utf8)
        let doc = utf8.withUnsafeBufferPointer { buffer in
            buffer.baseAddress?.withMemoryRebound(to: CChar.self, capacity: buffer.count) {
                htmlReadMemory($0, Int32(buffer.count), nil, "UTF-8", options)
            }
        }
        guard let doc else { return root }
        defer { xmlFreeDoc(doc) }
        root.adopt(children: doc.pointee.children)
        return root
    }

    private static let initialized: Void = { xmlInitParser() }()

    /// Text inside these never reaches `text`: it is code, not content.
    private static let opaque: Set<String> = ["script", "style", "template", "noscript"]

    private func adopt(children first: xmlNodePtr?) {
        var cursor = first
        while let node = cursor {
            switch node.pointee.type {
            case XML_ELEMENT_NODE:
                let child = HTMLElement(tag: Self.string(node.pointee.name).lowercased(), attributes: Self.attributes(of: node))
                child.parent = self
                nodes.append(.element(child))
                if !Self.opaque.contains(child.tag) {
                    child.adopt(children: node.pointee.children)
                }
            case XML_TEXT_NODE, XML_CDATA_SECTION_NODE:
                nodes.append(.text(Self.string(node.pointee.content)))
            default:
                break  // comments, processing instructions, DTDs
            }
            cursor = node.pointee.next
        }
    }

    private static func attributes(of node: xmlNodePtr) -> [String: String] {
        var out: [String: String] = [:]
        var attr = node.pointee.properties
        while let current = attr {
            var value = ""
            var piece = current.pointee.children
            while let text = piece {
                value += string(text.pointee.content)
                piece = text.pointee.next
            }
            out[string(current.pointee.name).lowercased()] = value
            attr = current.pointee.next
        }
        return out
    }

    private static func string(_ chars: UnsafePointer<xmlChar>?) -> String {
        guard let chars else { return "" }
        return String(cString: UnsafeRawPointer(chars).assumingMemoryBound(to: CChar.self))
    }

    private static func string(_ chars: UnsafeMutablePointer<xmlChar>?) -> String {
        string(UnsafePointer(chars))
    }

    // MARK: - Reading

    var children: [HTMLElement] {
        nodes.compactMap { if case .element(let el) = $0 { el } else { nil } }
    }

    /// All text inside, whitespace collapsed: BeautifulSoup's `get_text()`
    /// followed by the extractors' `clean`. `<b>Fri</b>day` reads "Friday".
    var text: String { joinedText(separator: "") }

    /// The same, with a space between every piece of text: `get_text(" ")`.
    /// `<b>Fri</b>day` reads "Fri day". The extractors use this where the
    /// originals did, mostly for whole-page text.
    var spacedText: String { joinedText(separator: " ") }

    private func joinedText(separator: String) -> String {
        var parts: [String] = []
        collectText(into: &parts)
        return parts.joined(separator: separator).split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    private func collectText(into parts: inout [String]) {
        for node in nodes {
            switch node {
            case .text(let value): parts.append(value)
            case .element(let el): el.collectText(into: &parts)
            }
        }
    }

    /// The attribute's value, or nil if it isn't there.
    func attr(_ name: String) -> String? { attributes[name] }

    func hasAttr(_ name: String) -> Bool { attributes[name] != nil }

    var classes: [String] {
        (attributes["class"] ?? "").split(whereSeparator: \.isWhitespace).map(String.init)
    }

    func hasClass(_ name: String) -> Bool { classes.contains(name) }

    /// This element and everything under it, in document order.
    func allElements() -> [HTMLElement] {
        var out = [self]
        for child in children { out += child.allElements() }
        return out
    }

    func ancestor(where match: (HTMLElement) -> Bool) -> HTMLElement? {
        var node = parent
        while let current = node {
            if match(current) { return current }
            node = current.parent
        }
        return nil
    }

    /// Detach from the tree (BeautifulSoup's `decompose`).
    func remove() {
        guard let parent else { return }
        parent.nodes.removeAll { if case .element(let el) = $0 { el === self } else { false } }
        self.parent = nil
    }

    // MARK: - Selecting

    /// Descendants matching the selector, in document order. Like
    /// BeautifulSoup, never the element itself.
    func select(_ css: String) -> [HTMLElement] {
        let groups = CSSSelector.parse(css)
        guard !groups.isEmpty else { return [] }
        return allElements().dropFirst().filter { el in groups.contains { $0.matches(el) } }
    }

    func first(_ css: String) -> HTMLElement? {
        let groups = CSSSelector.parse(css)
        guard !groups.isEmpty else { return nil }
        return allElements().dropFirst().first { el in groups.contains { $0.matches(el) } }
    }
}

// MARK: - Selectors

/// One comma-separated group: compounds joined by combinators, matched right to left.
private struct CSSSelector {
    enum Combinator { case descendant, child }

    struct AttributeTest {
        enum Op { case exists, equals, prefix, suffix, contains, word }
        let name: String
        let op: Op
        let value: String

        func matches(_ el: HTMLElement) -> Bool {
            guard let actual = el.attr(name) else { return false }
            switch op {
            case .exists: return true
            case .equals: return actual == value
            case .prefix: return !value.isEmpty && actual.hasPrefix(value)
            case .suffix: return !value.isEmpty && actual.hasSuffix(value)
            case .contains: return !value.isEmpty && actual.contains(value)
            case .word: return actual.split(whereSeparator: \.isWhitespace).contains { $0 == value }
            }
        }
    }

    struct Compound {
        var tag: String?
        var id: String?
        var classes: [String] = []
        var attributes: [AttributeTest] = []

        func matches(_ el: HTMLElement) -> Bool {
            if let tag, tag != el.tag { return false }
            if let id, el.attr("id") != id { return false }
            if !classes.isEmpty {
                let have = el.classes
                if !classes.allSatisfy(have.contains) { return false }
            }
            return attributes.allSatisfy { $0.matches(el) }
        }
    }

    /// `parts[i]` is joined to `parts[i - 1]` by `combinators[i - 1]`.
    var parts: [Compound] = []
    var combinators: [Combinator] = []

    func matches(_ el: HTMLElement) -> Bool {
        match(el, at: parts.count - 1)
    }

    private func match(_ el: HTMLElement, at index: Int) -> Bool {
        guard parts[index].matches(el) else { return false }
        if index == 0 { return true }
        switch combinators[index - 1] {
        case .child:
            return el.parent.map { match($0, at: index - 1) } ?? false
        case .descendant:
            var node = el.parent
            while let current = node {
                if match(current, at: index - 1) { return true }
                node = current.parent
            }
            return false
        }
    }

    // MARK: Parsing

    /// Selectors are fixed strings in the extractors, so parsed once and cached.
    nonisolated(unsafe) private static var cache: [String: [CSSSelector]] = [:]
    private static let lock = NSLock()

    static func parse(_ css: String) -> [CSSSelector] {
        lock.lock()
        defer { lock.unlock() }
        if let hit = cache[css] { return hit }
        let parsed = split(css, on: ",").compactMap(parseGroup)
        cache[css] = parsed
        return parsed
    }

    private static func parseGroup(_ text: String) -> CSSSelector? {
        var selector = CSSSelector()
        var pending: Combinator?
        for token in tokens(text) {
            if token == ">" {
                pending = .child
                continue
            }
            guard let compound = parseCompound(token) else { return nil }
            if !selector.parts.isEmpty {
                selector.combinators.append(pending ?? .descendant)
            }
            selector.parts.append(compound)
            pending = nil
        }
        return selector.parts.isEmpty ? nil : selector
    }

    /// Whitespace-separated tokens, with `>` as its own token, ignoring
    /// whitespace inside `[...]`.
    private static func tokens(_ text: String) -> [String] {
        var out: [String] = []
        var current = ""
        var depth = 0
        var quote: Character?
        func flush() {
            if !current.isEmpty { out.append(current) }
            current = ""
        }
        for ch in text {
            if let q = quote {
                current.append(ch)
                if ch == q { quote = nil }
            } else if ch == "'" || ch == "\"" {
                quote = ch
                current.append(ch)
            } else if ch == "[" {
                depth += 1
                current.append(ch)
            } else if ch == "]" {
                depth -= 1
                current.append(ch)
            } else if depth == 0 && ch == ">" {
                flush()
                out.append(">")
            } else if depth == 0 && ch.isWhitespace {
                flush()
            } else {
                current.append(ch)
            }
        }
        flush()
        return out
    }

    private static func parseCompound(_ token: String) -> Compound? {
        var compound = Compound()
        var rest = Substring(token)

        let nameEnd = rest.firstIndex { ".#[".contains($0) } ?? rest.endIndex
        let tag = rest[..<nameEnd]
        if !tag.isEmpty && tag != "*" { compound.tag = tag.lowercased() }
        rest = rest[nameEnd...]

        while let marker = rest.first {
            rest = rest.dropFirst()
            switch marker {
            case ".", "#":
                let end = rest.firstIndex { ".#[".contains($0) } ?? rest.endIndex
                let name = String(rest[..<end])
                guard !name.isEmpty else { return nil }
                if marker == "." { compound.classes.append(name) } else { compound.id = name }
                rest = rest[end...]
            case "[":
                guard let close = closingBracket(in: rest) else { return nil }
                guard let test = parseAttribute(String(rest[..<close])) else { return nil }
                compound.attributes.append(test)
                rest = rest[rest.index(after: close)...]
            default:
                return nil  // unsupported syntax (pseudo-classes etc.)
            }
        }
        return compound
    }

    private static func closingBracket(in text: Substring) -> Substring.Index? {
        var quote: Character?
        for i in text.indices {
            let ch = text[i]
            if let q = quote {
                if ch == q { quote = nil }
            } else if ch == "'" || ch == "\"" {
                quote = ch
            } else if ch == "]" {
                return i
            }
        }
        return nil
    }

    private static func parseAttribute(_ body: String) -> AttributeTest? {
        let ops: [(String, AttributeTest.Op)] = [("^=", .prefix), ("$=", .suffix), ("*=", .contains), ("~=", .word), ("=", .equals)]
        for (symbol, op) in ops {
            guard let range = body.range(of: symbol) else { continue }
            let name = body[..<range.lowerBound].trimmingCharacters(in: .whitespaces).lowercased()
            var value = body[range.upperBound...].trimmingCharacters(in: .whitespaces)
            if let q = value.first, (q == "'" || q == "\""), value.count >= 2, value.last == q {
                value = String(value.dropFirst().dropLast())
            }
            return name.isEmpty ? nil : AttributeTest(name: name, op: op, value: value)
        }
        let name = body.trimmingCharacters(in: .whitespaces).lowercased()
        return name.isEmpty ? nil : AttributeTest(name: name, op: .exists, value: "")
    }

    /// Split on a separator that isn't inside brackets or quotes.
    private static func split(_ text: String, on separator: Character) -> [String] {
        var out: [String] = []
        var current = ""
        var depth = 0
        var quote: Character?
        for ch in text {
            if let q = quote {
                if ch == q { quote = nil }
            } else if ch == "'" || ch == "\"" {
                quote = ch
            } else if ch == "[" {
                depth += 1
            } else if ch == "]" {
                depth -= 1
            } else if ch == separator && depth == 0 {
                out.append(current)
                current = ""
                continue
            }
            current.append(ch)
        }
        out.append(current)
        return out.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }
}
