import Foundation
import Observation
import WebKit

/// App-wide state: whether we're signed in, what's been found, and where to navigate.
@MainActor
@Observable
final class AppState {
    enum Route: Hashable {
        case scan(Int)
        case history(String)
        case settings
    }

    var signedIn: Bool
    var status = LocalStore.Status()
    var scans: [ScanSummary] = []
    let pages = Hirewheel.pages

    var path: [Route] = []
    var showingSignIn: Bool

    var isScanning = false
    /// What the running scan is doing, for the status line.
    var progress: String?

    /// Opening the app scans if the last scan is older than this.
    static let staleAfter: TimeInterval = 30 * 60

    /// Light/dark preference. `system` (the default) follows the device.
    var appearance: Appearance = .system {
        didSet { UserDefaults.standard.set(appearance.rawValue, forKey: Self.appearanceKey) }
    }

    private static let appearanceKey = "hw.appearance"
    private let store = LocalStore.shared

    init() {
        let hasSession = CookieVault.hasSession
        signedIn = hasSession
        showingSignIn = !hasSession
        if let raw = UserDefaults.standard.string(forKey: Self.appearanceKey),
           let saved = Appearance(rawValue: raw) {
            appearance = saved
        }
        #if DEBUG
        // Open straight to a screen, so it can be inspected without tapping
        // through the app: --setenv HW_DEV_ROUTE=settings
        switch ProcessInfo.processInfo.environment["HW_DEV_ROUTE"] {
        case "settings": path = [.settings]
        case let key? where key.hasPrefix("history:"):
            path = [.history(String(key.dropFirst("history:".count)))]
        default: break
        }
        #endif
    }

    // MARK: - Loading

    func refresh() async {
        await Scanner.shared.closeInterruptedScans()
        signedIn = CookieVault.hasSession
        status = await store.status()
        scans = await store.scans()
    }

    /// Scan now and follow along. Notifications are skipped: the user is
    /// already looking at the result.
    func scanNow() async {
        guard signedIn, !isScanning else { return }
        isScanning = true
        defer {
            isScanning = false
            progress = nil
        }
        progress = "Starting scan…"
        _ = await Scanner.shared.run { [weak self] message in
            await self?.setProgress(message)
        }
        await refresh()
    }

    func scanIfStale() async {
        guard signedIn, !status.needsReauth else { return }
        let last = Format.date(from: scans.first?.startedAt) ?? .distantPast
        if Date().timeIntervalSince(last) > Self.staleAfter {
            await scanNow()
        }
    }

    private func setProgress(_ message: String) {
        progress = message
    }

    // MARK: - Sign-in

    /// Called once Hirewheel's login page has handed over a session. Returns
    /// false if the cookies don't actually work, so the caller keeps waiting.
    func completeSignIn(cookies: [HTTPCookie], userAgent: String?) async -> Bool {
        if let userAgent { HirewheelClient.userAgent = userAgent }
        let client = HirewheelClient(cookies: cookies)
        guard await client.isSignedIn() else { return false }
        client.persistCookies()

        if let html = try? await client.fetch(Hirewheel.accountURL) {
            await store.setEmail(Scanner.loginEmail(in: html))
        }
        await store.setNeedsReauth(false)
        signedIn = true
        showingSignIn = false
        await NotificationManager.shared.requestAuthorization()
        await refresh()
        Task { await scanNow() }
        return true
    }

    /// Forget the Hirewheel session. History stays on the phone.
    func signOut() async {
        CookieVault.clear()
        await Self.clearWebData()
        await store.setEmail(nil)
        await store.setNeedsReauth(false)
        signedIn = false
        path = []
        showingSignIn = true
        await refresh()
    }

    /// Sign out and erase every scan and saved page.
    func deleteEverything() async {
        await store.deleteAll()
        await signOut()
    }

    /// The login web view keeps its own cookies; signing out must clear those
    /// too, or the next sign-in would silently reuse the old session.
    private static func clearWebData() async {
        let data = WKWebsiteDataStore.default()
        await data.removeData(
            ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(),
            modifiedSince: .distantPast
        )
    }
}
