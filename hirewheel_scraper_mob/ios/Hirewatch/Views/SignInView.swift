import SwiftUI

/// Signing in to Hirewheel, on Hirewheel's own login page.
///
/// The password is typed into Hirewheel's form. Hirewatch keeps only the
/// session that sign-in creates, in the phone's Keychain.
struct SignInView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var showingBrowser = Self.openBrowserOnLaunch
    @State private var verifying = false

    /// Open straight onto Hirewheel's login page, so it can be checked without
    /// tapping through: --setenv HW_DEV_SIGNIN=browser (DEBUG only).
    private static var openBrowserOnLaunch: Bool {
        #if DEBUG
        ProcessInfo.processInfo.environment["HW_DEV_SIGNIN"] == "browser"
        #else
        false
        #endif
    }

    var body: some View {
        NavigationStack {
            Group {
                if showingBrowser {
                    browser
                } else {
                    intro
                }
            }
            .background(Theme.bg)
            .navigationTitle("Sign in")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.surface, for: .navigationBar)
            .toolbar {
                // Signing in again after a session expired can be put off;
                // the very first sign-in can't, there's nothing to show yet.
                if app.signedIn {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Close") { dismiss() }
                    }
                }
            }
        }
        .interactiveDismissDisabled(!app.signedIn)
    }

    private var intro: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(app.status.needsReauth ? "Sign in again" : "Welcome to Hirewatch")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.text)
                Text("Hirewatch checks your Hirewheel pages and tells you when something new shows up.")
                    .font(.callout)
                    .foregroundStyle(Theme.textMuted)
                Text("Sign in on Hirewheel's own login page. Your password goes straight to Hirewheel. Hirewatch only keeps the session it creates, on this phone, and nothing is sent anywhere else.")
                    .font(.callout)
                    .foregroundStyle(Theme.textMuted)

                Button {
                    showingBrowser = true
                } label: {
                    Text("Sign in to Hirewheel")
                        .font(.callout.bold())
                        .foregroundStyle(Theme.onAccent)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
                .padding(.top, 8)
            }
            .padding(16)
        }
    }

    private var browser: some View {
        VStack(spacing: 0) {
            HirewheelLoginView { cookies, agent in
                verifying = true
                defer { verifying = false }
                return await app.completeSignIn(cookies: cookies, userAgent: agent)
            }

            HStack(spacing: 8) {
                if verifying {
                    ProgressView().controlSize(.small).tint(Theme.accent)
                }
                Text(verifying ? "Checking your session…" : "Sign in above. This is Hirewheel's real site.")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            .padding(12)
            .frame(maxWidth: .infinity)
            .background(Theme.surface)
        }
    }
}
