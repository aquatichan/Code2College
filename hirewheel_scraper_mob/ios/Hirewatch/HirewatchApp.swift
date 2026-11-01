import SwiftUI
import UIKit
import UserNotifications

@main
struct HirewatchApp: App {
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
                // whatever was on screen when you left. Re-read on every return
                // to the foreground, and scan if the last one is stale.
                .onChange(of: scenePhase) { _, phase in
                    guard phase == .active else { return }
                    Task {
                        await app.refresh()
                        await app.scanIfStale()
                    }
                }
                .task {
                    // Wire notification taps to navigation, then ask permission.
                    NotificationManager.shared.onOpenScan = { scanID in
                        app.path = [.scan(scanID)]
                    }
                    NotificationManager.shared.onOpenSignIn = {
                        app.showingSignIn = true
                    }
                    if app.signedIn {
                        await NotificationManager.shared.requestAuthorization()
                    }
                    #if DEBUG
                    // Exercise the background path on demand, since iOS decides
                    // when BGAppRefreshTask really runs and that can't be forced
                    // from a command line:  --setenv HW_DEV_BG_REFRESH=1
                    if ProcessInfo.processInfo.environment["HW_DEV_BG_REFRESH"] == "1" {
                        let outcome = await BackgroundRefresh.runOnce()
                        print("[bg-test] \(outcome.map { "\($0.status), \($0.notifiableChanges) change(s)" } ?? "no session")")
                        await app.refresh()
                    }
                    #endif
                }
        }
    }
}

/// Only exists for what SwiftUI cannot do on its own: registering the
/// background-refresh task before launch ends.
final class AppDelegate: NSObject, UIApplicationDelegate {
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
}
