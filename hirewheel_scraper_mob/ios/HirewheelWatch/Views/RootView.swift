import SwiftUI

struct RootView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        NavigationStack(path: Binding(get: { app.path }, set: { app.path = $0 })) {
            FeedView()
                .navigationDestination(for: AppState.Route.self) { route in
                    switch route {
                    case .scan(let id):
                        ScanDetailView(scanID: id)
                    case .history(let key):
                        PageHistoryView(pageKey: key)
                    case .settings:
                        SettingsView()
                    }
                }
        }
        .tint(Theme.accent)
        // Load here rather than in FeedView: launching straight into a pushed
        // screen (a tapped notification, a deep link) would otherwise leave the
        // app with no data at all.
        .task { await app.refresh() }
        .sheet(isPresented: Binding(get: { app.showingSignIn }, set: { app.showingSignIn = $0 })) {
            SignInView()
        }
    }
}
