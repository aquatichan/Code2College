import BackgroundTasks
import Foundation

/// The no-Apple-account delivery path.
///
/// iOS periodically grants the app a short window; we use it to ask the server
/// for its latest scans and raise a local notification if anything is new since
/// the last one we told the user about. This is strictly worse than real push —
/// iOS decides when (and whether) to wake us, so alerts can lag — but it needs no
/// paid account, and it is a genuine improvement over a Tkinter window on a Mac.
///
/// Once `Me.remotePush` is true, this stops posting notifications and just keeps
/// the local "last seen" marker fresh, so the two paths never double-notify.
enum BackgroundRefresh {
    /// Must match BGTaskSchedulerPermittedIdentifiers in Info.plist.
    static let taskIdentifier = (Bundle.main.bundleIdentifier ?? "com.aaronqin.hirewatch") + ".refresh"

    private static let lastSeenKey = "hw.lastSeenScanID"

    static var lastSeenScanID: Int {
        get { UserDefaults.standard.integer(forKey: lastSeenKey) }
        set { UserDefaults.standard.set(newValue, forKey: lastSeenKey) }
    }

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
            let newCount = await checkForUpdates()
            boxed.task.setTaskCompleted(success: newCount >= 0)
        }
        // `Task` is Sendable, so the system may fire this from any thread safely.
        boxed.task.expirationHandler = { work.cancel() }
    }

    /// Returns how many new scans were found, or -1 on failure.
    @discardableResult
    static func checkForUpdates() async -> Int {
        guard let session = SessionStore.load() else { return -1 }
        let client = APIClient(session: session)

        do {
            let me = try await client.me()
            let scans = try await client.scans(limit: 20)

            let fresh = scans.filter { $0.id > lastSeenScanID && !$0.failed && $0.changeCount > 0 }
            // Move the marker regardless, so a backlog of old scans can't cause a
            // burst of notifications later.
            if let newest = scans.first?.id, newest > lastSeenScanID {
                lastSeenScanID = newest
            }

            // When APNs is live the server already notified; don't double up.
            guard !me.remotePush, let latest = fresh.first else { return fresh.count }

            let total = fresh.reduce(0) { $0 + $1.changeCount }
            let detail = try? await client.scan(id: latest.id)
            let labels = detail?.changedPages.map(\.label) ?? []

            await NotificationManager.shared.postLocal(
                title: "Hirewheel — \(Format.plural(total, "update"))",
                body: labels.isEmpty ? "Tap to see what changed." : labels.joined(separator: ", "),
                scanID: latest.id
            )
            return fresh.count
        } catch {
            print("[bg] refresh failed: \(error)")
            return -1
        }
    }
}
