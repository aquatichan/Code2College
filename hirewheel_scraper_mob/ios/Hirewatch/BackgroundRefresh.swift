import BackgroundTasks
import Foundation

/// Scanning while the app isn't open.
///
/// iOS periodically grants the app a short window (around 30 seconds) and the
/// whole scan runs in it: pages are fetched in parallel, so it fits. iOS decides
/// when — and whether — that happens, based on how often the app is used, so
/// it is typically every few hours rather than on a fixed schedule. Opening the
/// app also scans if the last one is stale (see `AppState.scanIfStale`).
enum BackgroundRefresh {
    /// Must match BGTaskSchedulerPermittedIdentifiers in Info.plist.
    static let taskIdentifier = (Bundle.main.bundleIdentifier ?? "com.aaronqin.hirewatch") + ".refresh"

    /// `BGAppRefreshTask` predates `Sendable` and isn't marked as such, so Swift 6
    /// refuses to let it reach the async work that eventually completes it. We
    /// register the launch handler on the **main queue** and keep every touch of
    /// the task on the main actor, so it never actually leaves one thread. This box
    /// states that contract explicitly rather than scattering unsafe opt-outs.
    private struct MainActorTask: @unchecked Sendable {
        let task: BGAppRefreshTask
    }

    /// Call once at launch, before the app finishes starting up.
    static func register() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: taskIdentifier,
            using: .main
        ) { task in
            guard let refresh = task as? BGAppRefreshTask else { return }
            handle(MainActorTask(task: refresh))
        }
    }

    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        // A floor, not a promise — iOS will choose the real cadence.
        request.earliestBeginDate = Date(timeIntervalSinceNow: 30 * 60)
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            // Simulators and devices with Background App Refresh disabled reject
            // this; not worth surfacing to the user.
            print("[bg] could not schedule: \(error)")
        }
    }

    private static func handle(_ boxed: MainActorTask) {
        // Always line up the next one, or the chain stops here.
        schedule()

        let work = Task { @MainActor in
            let outcome = await runOnce()
            boxed.task.setTaskCompleted(success: outcome?.status == "ok")
        }
        // Cancelling stops the in-flight fetches; the scan records what it got.
        boxed.task.expirationHandler = { work.cancel() }
    }

    /// One scan, announced. Returns nil if there was nothing to scan with.
    @MainActor
    @discardableResult
    static func runOnce() async -> ScanOutcome? {
        guard let outcome = await Scanner.shared.run() else { return nil }
        await NotificationManager.shared.announce(outcome)
        return outcome
    }
}
