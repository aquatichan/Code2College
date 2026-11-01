import Foundation
import Security

/// The site, the pages watched on it, and how a signed-in session is kept.
enum Hirewheel {
    static let baseURL = URL(string: "https://www.hirewheel.ai")!
    /// A protected page. Being served it, rather than bounced to the login form,
    /// is the whole sign-in signal.
    static let probeURL = url("/intern/notifications")
    static let accountURL = url("/account")
    static let loginMarkers = ["/login", "/accounts/login", "/sign-in"]

    static func url(_ path: String) -> URL {
        URL(string: path, relativeTo: baseURL)!.absoluteURL
    }

    static func isLoginPage(_ url: URL?) -> Bool {
        guard let path = url?.path else { return false }
        return loginMarkers.contains { path.hasPrefix($0) }
    }

    static func isHirewheel(_ url: URL?) -> Bool {
        url?.host?.hasSuffix("hirewheel.ai") == true
    }

    /// The pages a signed-in student account is scanned for.
    static let pages: [PageInfo] = [
        PageInfo(key: "modules", label: "Learning Modules", url: url("/learning/modules")),
        PageInfo(key: "internship_prep", label: "Internship Prep Projects", url: url("/internship-prep/")),
        PageInfo(key: "college_pathways", label: "College Pathways", url: url("/college-pathways/")),
        PageInfo(key: "marketplace", label: "Marketplace · Open", url: url("/marketplace/browse?tab=open")),
        PageInfo(key: "marketplace_examples", label: "Marketplace · Examples", url: url("/marketplace/browse?tab=examples")),
        PageInfo(key: "my_projects", label: "My Projects", url: url("/intern/my_projects")),
        PageInfo(key: "meetings", label: "My Interviews", url: url("/intern/meetings")),
        PageInfo(key: "surveys", label: "My Surveys", url: url("/surveys/my")),
        // The Program Hub's tabs are separate server-rendered URLs, so each one
        // is genuinely a different page.
        PageInfo(key: "program", label: "Program Hub · Deliverables", url: url("/program/dashboard?tab=deliverables")),
        PageInfo(key: "program_assignments", label: "Program Hub · Assignments", url: url("/program/dashboard?tab=assignments")),
        PageInfo(key: "program_ai_training", label: "Program Hub · AI Training", url: url("/program/dashboard?tab=summer_2026")),
        PageInfo(key: "program_fall", label: "Program Hub · Fall 2026", url: url("/program/dashboard?tab=fall_2026")),
        PageInfo(key: "program_courses", label: "Program Hub · Live Courses", url: url("/program/dashboard?tab=courses")),
        PageInfo(key: "program_history", label: "Program Hub · History", url: url("/program/dashboard?tab=history")),
        PageInfo(key: "special_events", label: "Special Events", url: url("/special-events")),
        PageInfo(key: "notifications", label: "Notifications", url: url("/intern/notifications")),
        PageInfo(key: "news", label: "Newsfeed", url: url("/news/")),
    ]

    static func label(for key: String) -> String? {
        pages.first { $0.key == key }?.label
    }
}

// MARK: - Cookies

/// The Hirewheel session, as cookies, kept in the Keychain.
///
/// The password never touches the app: it is typed into Hirewheel's own login
/// page in a web view, and only the cookies that page sets are kept. They are
/// the only credential Hirewatch holds.
enum CookieVault {
    private struct StoredCookie: Codable {
        let name: String
        let value: String
        let domain: String
        let path: String
        let expires: Date?
        let secure: Bool
        let httpOnly: Bool

        init(_ cookie: HTTPCookie) {
            name = cookie.name
            value = cookie.value
            domain = cookie.domain
            path = cookie.path
            expires = cookie.expiresDate
            secure = cookie.isSecure
            httpOnly = cookie.isHTTPOnly
        }

        var cookie: HTTPCookie? {
            var props: [HTTPCookiePropertyKey: Any] = [
                .name: name, .value: value, .domain: domain, .path: path,
            ]
            if let expires { props[.expires] = expires }
            if secure { props[.secure] = "TRUE" }
            if httpOnly { props[HTTPCookiePropertyKey("HttpOnly")] = "TRUE" }
            return HTTPCookie(properties: props)
        }
    }

    private static let service = "com.aaronqin.hirewatch"
    private static let account = "hirewheelCookies"

    static func load() -> [HTTPCookie] {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data,
              let stored = try? JSONDecoder().decode([StoredCookie].self, from: data)
        else { return [] }
        return stored.compactMap(\.cookie)
    }

    static var hasSession: Bool { !load().isEmpty }

    static func save(_ cookies: [HTTPCookie]) {
        let relevant = cookies.filter { $0.domain.hasSuffix("hirewheel.ai") }
        clear()
        guard !relevant.isEmpty,
              let data = try? JSONEncoder().encode(relevant.map(StoredCookie.init))
        else { return }
        var query = baseQuery()
        query[kSecValueData as String] = data
        // Background scans can run while the phone is locked, so the session
        // must be readable after first unlock, not only while unlocked.
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(query as CFDictionary, nil)
    }

    static func clear() {
        SecItemDelete(baseQuery() as CFDictionary)
    }

    private static func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

// MARK: - Fetching

enum FetchError: LocalizedError {
    case signedOut
    case badStatus(Int)

    var errorDescription: String? {
        switch self {
        case .signedOut: return "Signed out of Hirewheel."
        case .badStatus(let code): return "Hirewheel returned \(code)."
        }
    }
}

/// Fetches pages with the stored session, outside any web view.
///
/// Hirewheel's pages are server-rendered, so their HTML already holds
/// everything the extractors read — no browser is needed to scan them, which is
/// what lets a scan run in the few seconds iOS grants in the background.
final class HirewheelClient: Sendable {
    private let session: URLSession
    private let cookieStorage: HTTPCookieStorage

    /// The web view's own user agent, saved at sign-in, so scans look like the
    /// browser the session was created in.
    static var userAgent: String? {
        get { UserDefaults.standard.string(forKey: "hw.userAgent") }
        set { UserDefaults.standard.set(newValue, forKey: "hw.userAgent") }
    }

    init(cookies: [HTTPCookie] = CookieVault.load()) {
        // Ephemeral: a private cookie jar holding only this session, nothing
        // written to disk behind our back.
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 30
        config.httpCookieAcceptPolicy = .always
        if let agent = Self.userAgent {
            config.httpAdditionalHeaders = ["User-Agent": agent]
        }
        let storage = config.httpCookieStorage ?? HTTPCookieStorage()
        for cookie in cookies { storage.setCookie(cookie) }
        config.httpCookieStorage = storage
        cookieStorage = storage
        session = URLSession(configuration: config)
    }

    /// The page's HTML. Throws `.signedOut` if Hirewheel bounced to its login form.
    func fetch(_ url: URL) async throws -> String {
        let (data, response) = try await session.data(from: url)
        if Hirewheel.isLoginPage(response.url) { throw FetchError.signedOut }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw FetchError.badStatus(http.statusCode)
        }
        return String(decoding: data, as: UTF8.self)
    }

    func isSignedIn() async -> Bool {
        do {
            _ = try await fetch(Hirewheel.probeURL)
            return true
        } catch {
            return false
        }
    }

    /// Write the jar back to the Keychain.
    ///
    /// Hirewheel rotates its session cookie, so throwing the refreshed one away
    /// is the classic cause of a session that "randomly" expires early.
    func persistCookies() {
        let cookies = cookieStorage.cookies ?? []
        if !cookies.isEmpty { CookieVault.save(cookies) }
    }
}
