import Foundation
import Observation

/// App-wide state: who we are, what the server says, and where to navigate.
@MainActor
@Observable
final class AppState {
    enum Route: Hashable {
        case scan(Int)
        case history(String)
        case settings
    }

    var session: Session?
    var me: Me?
    var scans: [ScanSummary] = []
    var pages: [PageInfo] = []

    var path: [Route] = []
    var showingSignIn = false

    var loadError: String?
    var isRefreshing = false

    /// Light/dark preference. `system` (the default) follows the device.
    var appearance: Appearance = .system {
        didSet { UserDefaults.standard.set(appearance.rawValue, forKey: Self.appearanceKey) }
    }

    private static let appearanceKey = "hw.appearance"

    var client: APIClient? {
        session.map { APIClient(session: $0) }
    }

    init() {
        session = SessionStore.load()
        showingSignIn = session == nil
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

    // MARK: - Auth lifecycle

    func signIn(baseURL: URL, deviceToken: String) {
        let new = Session(baseURL: baseURL, deviceToken: deviceToken)
        SessionStore.save(new)
        session = new
        // Keep the sheet up: the next step is signing in to Hirewheel, and that
        // is what links this phone back to any existing history.
    }

    /// Sign this phone out. The account and its scans stay on the server, so
    /// signing back in with the same Hirewheel email brings them back.
    func signOutOfDevice() async {
        if let client {
            // Best-effort: even if the server is unreachable, the user asked to
            // leave, so the local sign-out still happens.
            _ = try? await client.signOutDevice()
        }
        signOut()
    }

    /// Forget the session locally. Used directly when the server has already
    /// rejected our token.
    func signOut() {
        SessionStore.clear()
        session = nil
        me = nil
        scans = []
        pages = []
        path = []
        showingSignIn = true
    }

    // MARK: - Loading

    func refresh() async {
        guard let client else { return }
        do {
            // Fetched together so the feed never renders a half-updated state.
            let me = try await client.me()
            let scans = try await client.scans()
            let pages = self.pages.isEmpty ? try await client.pages() : self.pages

            self.me = me
            self.scans = scans
            self.pages = pages
            loadError = nil

            // Keep the background-refresh marker current so returning to the app
            // doesn't leave a stale notification backlog waiting.
            if let newest = scans.first?.id, newest > BackgroundRefresh.lastSeenScanID {
                BackgroundRefresh.lastSeenScanID = newest
            }
        } catch let error as APIError where error.isUnauthorized {
            // The device token was revoked (most likely the account was deleted).
            signOut()
        } catch {
            loadError = error.localizedDescription
        }
    }

    /// Ask the server to scan right now, then follow it until it finishes.
    ///
    /// A real cycle walks 11 pages and takes tens of seconds, so the old
    /// "sleep two seconds and reload" showed stale results and made the button
    /// look broken. Instead we watch `runner_status` — which reports the page
    /// currently being scanned — until it goes back to idle.
    func scanNow() async {
        guard let client else { return }
        isRefreshing = true
        defer { isRefreshing = false }

        do {
            try await client.scanNow()

            var sawItStart = false
            // ~4 minute ceiling; a healthy cycle is far quicker than this.
            for _ in 0..<120 {
                try? await Task.sleep(for: .seconds(2))
                let status = try await client.me()
                me = status

                if status.runnerStatus != "idle" {
                    sawItStart = true
                } else if sawItStart {
                    break  // started and returned to idle: the cycle is done
                }
            }
            await refresh()
        } catch let error as APIError where error.isUnauthorized {
            signOut()
        } catch {
            loadError = error.localizedDescription
        }
    }

    /// Hand the APNs device token to the server, if we have both.
    func registerPushToken(_ token: String) async {
        guard let client else { return }
        do {
            try await client.registerPushToken(token)
            // remote_push may have flipped now that a token exists.
            me = try? await client.me()
        } catch {
            print("[push] could not register token: \(error)")
        }
    }
}
