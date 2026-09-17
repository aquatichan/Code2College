import Foundation
import Security

/// Where the server lives and who we are to it.
///
/// The device token is the only credential this app holds. It is issued once at
/// enrollment and grants access to one user's scans. The Hirewheel session itself
/// never reaches the phone — it is created and kept server-side by the hosted
/// login flow, so there is no password here to protect.
struct Session: Sendable, Equatable {
    var baseURL: URL
    var deviceToken: String
}

enum SessionStore {
    private static let service = "com.aaronqin.HirewheelWatch"
    private static let tokenAccount = "deviceToken"
    private static let baseURLKey = "hw.baseURL"

    // MARK: - Public API

    static func load() -> Session? {
        #if DEBUG
        if let injected = developmentSession() { return injected }
        #endif
        guard
            let raw = UserDefaults.standard.string(forKey: baseURLKey),
            let url = URL(string: raw),
            let token = readToken()
        else { return nil }
        return Session(baseURL: url, deviceToken: token)
    }

    #if DEBUG
    /// Start already enrolled, for UI work on the simulator.
    ///
    /// Reinstalling a build clears the Keychain, which otherwise means retyping
    /// the server address and invite code on every run. Launch with:
    ///
    ///     xcrun simctl launch <device> com.aaronqin.HirewheelWatch \
    ///         --setenv HW_DEV_BASE_URL=http://localhost:8000 \
    ///         --setenv HW_DEV_TOKEN=<a device token from the server>
    ///
    /// DEBUG-only, and never consulted in a release build.
    private static func developmentSession() -> Session? {
        let env = ProcessInfo.processInfo.environment
        guard
            let raw = env["HW_DEV_BASE_URL"],
            let url = URL(string: raw),
            let token = env["HW_DEV_TOKEN"], !token.isEmpty
        else { return nil }
        return Session(baseURL: url, deviceToken: token)
    }
    #endif

    static func save(_ session: Session) {
        UserDefaults.standard.set(session.baseURL.absoluteString, forKey: baseURLKey)
        writeToken(session.deviceToken)
    }

    static func clear() {
        UserDefaults.standard.removeObject(forKey: baseURLKey)
        deleteToken()
    }

    // MARK: - Keychain

    private static func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: tokenAccount,
        ]
    }

    private static func readToken() -> String? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data
        else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private static func writeToken(_ token: String) {
        deleteToken()
        var query = baseQuery()
        query[kSecValueData as String] = Data(token.utf8)
        // The token is needed by background refresh, which can run while the
        // device is locked — so it must survive first unlock, not require unlock.
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(query as CFDictionary, nil)
    }

    private static func deleteToken() {
        SecItemDelete(baseQuery() as CFDictionary)
    }
}
