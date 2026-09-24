import Foundation
import UIKit
import UserNotifications

/// Notification permission, APNs registration, and taps.
///
/// Two delivery paths, because a paid Apple Developer account is not yet in play:
///
/// * **Remote push (APNs)** — the real thing. Needs the paid account plus a .p8
///   key on the server. Instant, works with the app closed.
/// * **Background refresh + local notification** — the fallback that works today.
///   iOS wakes the app occasionally, it asks the server what's new, and raises a
///   notification itself. No account needed, but iOS decides the timing, so an
///   alert can lag well behind the scan that produced it.
///
/// The server reports which one is live via `Me.remotePush`, so the app does not
/// have to guess.
@MainActor
final class NotificationManager: NSObject {
    static let shared = NotificationManager()

    /// Set by the app so a tapped notification can route to the right screen.
    var onOpenScan: ((Int) -> Void)?
    var onOpenSignIn: (() -> Void)?

    private override init() { super.init() }

    func configure() {
        UNUserNotificationCenter.current().delegate = self
    }

    /// Ask once, then register with APNs if allowed.
    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            if granted {
                // Harmless when the app has no push entitlement yet: the delegate
                // simply reports a registration failure and the fallback carries on.
                UIApplication.shared.registerForRemoteNotifications()
            }
            return granted
        } catch {
            print("[notify] authorization failed: \(error)")
            return false
        }
    }

    /// Raise a notification locally — the fallback path when APNs isn't wired.
    func postLocal(title: String, body: String, scanID: Int?) async {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.threadIdentifier = "hirewheel-updates"
        if let scanID { content.userInfo = ["type": "cycle", "scan_id": scanID] }

        // nil trigger delivers immediately.
        let request = UNNotificationRequest(
            identifier: scanID.map { "scan-\($0)" } ?? UUID().uuidString,
            content: content,
            trigger: nil
        )
        try? await UNUserNotificationCenter.current().add(request)
    }

    // MARK: - Routing

    fileprivate func route(userInfo: [AnyHashable: Any]) {
        if let type = userInfo["type"] as? String, type == "reauth" {
            onOpenSignIn?()
            return
        }
        if let scanID = userInfo["scan_id"] as? Int {
            onOpenScan?(scanID)
        } else if let raw = userInfo["scan_id"] as? String, let scanID = Int(raw) {
            onOpenScan?(scanID)
        }
    }
}

// UIKit delivers these on the main thread, but the parameter types predate
// Sendable and aren't marked as such. `@preconcurrency` accepts that contract
// rather than making the whole manager nonisolated.
extension NotificationManager: @preconcurrency UNUserNotificationCenterDelegate {
    /// Show the alert even when the app is open, so a scan finishing in the
    /// foreground isn't silently swallowed.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        route(userInfo: response.notification.request.content.userInfo)
    }
}
