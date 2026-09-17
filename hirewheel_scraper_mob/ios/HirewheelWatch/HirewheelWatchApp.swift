import SwiftUI
import UIKit
import UserNotifications

@main
struct HirewheelWatchApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @Environment(\.scenePhase) private var scenePhase
    @State private var app = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .preferredColorScheme(app.appearance.colorScheme)
                // `.task` fires once when the view is first created and never
                // again, so coming back from the background would otherwise show
                // whatever was on screen when you left — stale until the app is
                // force-quit. Re-read on every return to the foreground.
                .onChange(of: scenePhase) { _, phase in
                    guard phase == .active, app.session != nil else { return }
                    Task { await app.refresh() }
                }
                .task {
                    // Wire notification taps to navigation, then ask permission.
                    NotificationManager.shared.onOpenScan = { scanID in
                        app.path = [.scan(scanID)]
                    }
                    NotificationManager.shared.onOpenSignIn = {
                        app.showingSignIn = true
                    }
                    AppDelegate.onPushToken = { token in
                        Task { await app.registerPushToken(token) }
                    }
                    app.store.onEntitlementsChanged = { signed in
                        await app.syncEntitlements(signed)
                    }
                    await app.store.load()
                    if app.session != nil {
                        _ = await NotificationManager.shared.requestAuthorization()
                    }
                    #if DEBUG
                    // Exercise the background-refresh notification path on demand,
                    // since iOS decides when BGAppRefreshTask really runs and that
                    // can't be forced from a command line:
                    //   --setenv HW_DEV_BG_REFRESH=1
                    if ProcessInfo.processInfo.environment["HW_DEV_BG_REFRESH"] == "1" {
                        let settings = await UNUserNotificationCenter.current().notificationSettings()
                        print("[bg-test] authorization: \(settings.authorizationStatus.rawValue) "
                              + "(2 = authorized, 1 = denied, 0 = not asked)")
                        BackgroundRefresh.lastSeenScanID = 0
                        let found = await BackgroundRefresh.checkForUpdates()
                        print("[bg-test] checkForUpdates found \(found) new scan(s) with changes")
                    }
                    #endif
                }
        }
    }
}

/// Only exists for the two things SwiftUI cannot do on its own: receiving the APNs
/// device token, and registering the background-refresh task before launch ends.
final class AppDelegate: NSObject, UIApplicationDelegate {
    /// Set by the app once state exists, so a token arriving early isn't lost.
    nonisolated(unsafe) static var onPushToken: ((String) -> Void)?
    nonisolated(unsafe) private static var pendingToken: String?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        MainActor.assumeIsolated { NotificationManager.shared.configure() }
        // Must happen before launch completes or iOS refuses the registration.
        BackgroundRefresh.register()
        BackgroundRefresh.schedule()
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        if let handler = Self.onPushToken {
            handler(token)
        } else {
            Self.pendingToken = token
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Entirely expected without a paid account or on a simulator. The
        // background-refresh fallback covers this case.
        print("[push] APNs registration unavailable: \(error.localizedDescription)")
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        if let token = Self.pendingToken, let handler = Self.onPushToken {
            Self.pendingToken = nil
            handler(token)
        }
    }
}
