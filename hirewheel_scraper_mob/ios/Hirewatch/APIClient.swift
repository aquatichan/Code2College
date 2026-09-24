import Foundation

enum APIError: LocalizedError {
    case badStatus(Int, String)
    case badURL
    case notSignedIn

    var errorDescription: String? {
        switch self {
        case .badStatus(let code, let detail):
            return detail.isEmpty ? "Server returned \(code)" : detail
        case .badURL:
            return "That server address doesn't look valid."
        case .notSignedIn:
            return "Not signed in."
        }
    }

    /// The device token is gone or was revoked — the app must re-enroll.
    var isUnauthorized: Bool {
        if case .badStatus(401, _) = self { return true }
        return false
    }
}

/// Typed client for the hwserver API.
struct APIClient: Sendable {
    let session: Session

    private static let decoder = JSONDecoder()

    // MARK: - Requests

    private func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: (any Encodable & Sendable)? = nil
    ) async throws -> T {
        let data = try await raw(path, method: method, body: body)
        return try Self.decoder.decode(T.self, from: data)
    }

    private func raw(
        _ path: String,
        method: String = "GET",
        body: (any Encodable & Sendable)? = nil
    ) async throws -> Data {
        guard let url = URL(string: path, relativeTo: session.baseURL) else {
            throw APIError.badURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("Bearer \(session.deviceToken)", forHTTPHeaderField: "Authorization")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await URLSession.shared.data(for: req)
        try Self.check(response, data)
        return data
    }

    private static func check(_ response: URLResponse, _ data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.badStatus(http.statusCode, Self.detail(from: data))
        }
    }

    /// FastAPI puts human-readable errors in `detail`; surface those verbatim.
    private static func detail(from data: Data) -> String {
        guard
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let detail = object["detail"]
        else { return "" }
        return String(describing: detail)
    }

    // MARK: - Enrollment (no session yet)

    static func enroll(
        baseURL: URL,
        label: String,
        inviteCode: String,
        pushToken: String?
    ) async throws -> EnrollResponse {
        struct Body: Encodable, Sendable {
            let label: String
            let invite_code: String
            let push_token: String?
            let platform: String
        }
        guard let url = URL(string: "enroll", relativeTo: baseURL) else { throw APIError.badURL }

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(
            Body(label: label, invite_code: inviteCode, push_token: pushToken, platform: "ios")
        )

        let (data, response) = try await URLSession.shared.data(for: req)
        try check(response, data)
        return try decoder.decode(EnrollResponse.self, from: data)
    }

    // MARK: - Reads

    func me() async throws -> Me { try await request("me") }
    func pages() async throws -> [PageInfo] { try await request("pages") }

    func scans(limit: Int = 50) async throws -> [ScanSummary] {
        try await request("scans?limit=\(limit)")
    }

    func scan(id: Int) async throws -> ScanDetail { try await request("scans/\(id)") }

    func history(pageKey: String, limit: Int = 100) async throws -> [HistoryEntry] {
        try await request("pages/\(pageKey)/history?limit=\(limit)")
    }

    func snapshot(id: Int) async throws -> SnapshotDetail { try await request("snapshots/\(id)") }

    /// Screenshots are behind the same bearer token, so they cannot be loaded by
    /// plain `AsyncImage`.
    func screenshot(path: String) async throws -> Data {
        try await raw("media/\(path)")
    }

    // MARK: - Writes

    struct StatusResponse: Codable, Sendable { let status: String }

    @discardableResult
    func scanNow() async throws -> StatusResponse {
        try await request("scan-now", method: "POST")
    }

    func startLogin() async throws -> LoginStart {
        try await request("auth/session", method: "POST")
    }

    func loginStatus(sessionID: String) async throws -> LoginStatus {
        try await request("auth/session/\(sessionID)")
    }

    @discardableResult
    func registerPushToken(_ token: String) async throws -> Data {
        struct Body: Encodable, Sendable {
            let push_token: String
            let environment: String
        }
        return try await raw(
            "devices/push",
            method: "POST",
            body: Body(push_token: token, environment: Self.pushEnvironment)
        )
    }

    /// Which APNs gateway this build's tokens belong to. Tokens only work
    /// against the gateway they were issued for, so one server can serve Debug
    /// builds (sandbox) and TestFlight / App Store builds (production) at once.
    static var pushEnvironment: String {
        #if DEBUG
        "sandbox"
        #else
        "production"
        #endif
    }

    /// The server a fresh install points at, from `HW_DEFAULT_SERVER`.
    static var defaultServer: String {
        (Bundle.main.object(forInfoDictionaryKey: "HWDefaultServerURL") as? String)
            ?? "http://localhost:8000"
    }

    @discardableResult
    func setMutedPages(_ keys: [String]) async throws -> Data {
        struct Body: Encodable, Sendable { let muted_pages: [String] }
        return try await raw("devices/me", method: "PATCH", body: Body(muted_pages: keys))
    }

    /// Forget this device on the server. The account and its history remain,
    /// so signing back in with the same Hirewheel email picks them up again.
    @discardableResult
    func signOutDevice() async throws -> Data {
        try await raw("devices/me", method: "DELETE")
    }

    @discardableResult
    func deleteAccount() async throws -> Data {
        try await raw("me", method: "DELETE")
    }
}
