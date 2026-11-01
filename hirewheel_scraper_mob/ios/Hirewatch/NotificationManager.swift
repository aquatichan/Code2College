import Foundation
import UIKit
import UserNotifications

/// Notification permission, posting, and taps.
///
/// Every notification is local: the phone runs the scan itself, so it already
/// knows what changed and has nobody to wait on. No push server, no Apple
/// push key, no paid account.
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

    @discardableResult
    func requestAuthorization() async -> Bool {
        do {
            return try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            print("[notify] authorization failed: \(error)")
            return false
        }
    }

    /// Tell the user what a scan found, if it found anything they want to hear about.
    func announce(_ outcome: ScanOutcome) async {
        if outcome.becameSignedOut {
            await post(
                title: "Hirewatch is signed out",
                body: "Your Hirewheel session expired. Tap to sign in again.",
                userInfo: ["type": "reauth"],
                id: "reauth"
            )
        } else if outcome.notifiableChanges > 0 {
            await post(
                title: "Hirewheel — \(Format.plural(outcome.notifiableChanges, "update"))",
                body: outcome.changedLabels.isEmpty
                    ? "Tap to see what changed."
                    : outcome.changedLabels.joined(separator: ", "),
                userInfo: ["type": "cycle", "scan_id": outcome.scanID],
                id: "scan-\(outcome.scanID)"
            )
        }
    }

    private func post(title: String, body: String, userInfo: [String: Any], id: String) async {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.threadIdentifier = "hirewheel-updates"
        content.userInfo = userInfo

        // nil trigger delivers immediately.
        let request = UNNotificationRequest(identifier: id, content: content, trigger: nil)
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
