import SwiftUI

/// Two stages in one screen:
///
///  1. Enrollment — point the app at your server and redeem an invite code.
///  2. Hirewheel sign-in — the server opens a real browser on Hirewheel's own
///     login page and streams it here. We poll until the session is live.
///
/// The password is typed into Hirewheel's own form. Neither this app nor the
/// server's code ever reads it.
struct SignInView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss

    @State private var baseURLText = APIClient.defaultServer
    @State private var showServerField = false
    @State private var inviteCode = ""
    @State private var busy = false
    @State private var error: String?

    @State private var loginSessionID: String?
    @State private var loginURL: URL?
    @State private var statusText: String?

    var body: some View {
        NavigationStack {
            Group {
                if app.session == nil {
                    enrollForm
                } else if let loginURL {
                    streamedBrowser(url: loginURL)
                } else {
                    hirewheelPrompt
                }
            }
            .background(Theme.bg)
            .navigationTitle(app.session == nil ? "Connect" : "Sign in")
            .toolbarBackground(Theme.surface, for: .navigationBar)
            .toolbar {
                if app.session != nil {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Close") { dismiss() }
                    }
                }
            }
        }
    }

    // MARK: - Stage 1

    private var enrollForm: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Welcome to Hirewatch")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.text)
                Text("Enter the invite code you were given.")
                    .font(.callout)
                    .foregroundStyle(Theme.textMuted)

                field("Invite code", text: $inviteCode)

                // Friends never need this; it's for pointing a build at a
                // different server (a local one while developing).
                if showServerField {
                    field("https://your-server", text: $baseURLText, keyboard: .URL)
                } else {
                    Button("Use a different server") { showServerField = true }
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }

                errorText

                primaryButton("Connect", busy: busy) { await enroll() }
            }
            .padding(16)
        }
    }

    // MARK: - Stage 2a

    private var hirewheelPrompt: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Sign in to Hirewheel")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.text)
                Text("Hirewatch will open Hirewheel's own login page. Your password goes straight into that page — the watcher only stores the session it creates.")
                    .font(.callout)
                    .foregroundStyle(Theme.textMuted)

                if let statusText {
                    Text(statusText)
                        .font(.callout)
                        .foregroundStyle(Theme.textMuted)
                }

                errorText

                primaryButton("Start sign-in", busy: busy) { await startLogin() }
            }
            .padding(16)
        }
    }

    // MARK: - Stage 2b

    private func streamedBrowser(url: URL) -> some View {
        VStack(spacing: 0) {
            Text("Sign in to Hirewheel below. This is a real browser running on the Hirewatch server.")
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
                .multilineTextAlignment(.center)
                .padding(12)

            WebViewContainer(url: url)

            HStack(spacing: 8) {
                ProgressView().controlSize(.small).tint(Theme.accent)
                Text(statusText ?? "Waiting for sign-in…")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            .padding(12)
            .frame(maxWidth: .infinity)
            .background(Theme.surface)
        }
    }

    // MARK: - Reusable bits

    private func field(
        _ placeholder: String,
        text: Binding<String>,
        keyboard: UIKeyboardType = .default
    ) -> some View {
        TextField(placeholder, text: text)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .keyboardType(keyboard)
            .foregroundStyle(Theme.text)
            .padding(12)
            .background(Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    @ViewBuilder
    private var errorText: some View {
        if let error {
            Text(error).font(.caption).foregroundStyle(Theme.removed)
        }
    }

    private func primaryButton(
        _ title: String,
        busy: Bool,
        action: @escaping () async -> Void
    ) -> some View {
        Button {
            Task { await action() }
        } label: {
            Group {
                if busy {
                    ProgressView().tint(Theme.onAccent)
                } else {
                    Text(title).font(.callout.bold()).foregroundStyle(Theme.onAccent)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(12)
            .background(Theme.accent)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .disabled(busy)
        .opacity(busy ? 0.7 : 1)
    }

    // MARK: - Actions

    private func enroll() async {
        error = nil
        let trimmed = baseURLText.trimmingCharacters(in: .whitespaces)
        // URL(string:) happily accepts nonsense; require a real scheme and host.
        guard
            let url = URL(string: trimmed.hasSuffix("/") ? trimmed : trimmed + "/"),
            url.scheme?.hasPrefix("http") == true,
            url.host != nil
        else {
            error = APIError.badURL.localizedDescription
            return
        }

        busy = true
        defer { busy = false }
        do {
            let resp = try await APIClient.enroll(
                baseURL: url,
                label: "student",
                inviteCode: inviteCode.trimmingCharacters(in: .whitespaces),
                pushToken: nil
            )
            app.signIn(baseURL: url, deviceToken: resp.deviceToken)
            _ = await NotificationManager.shared.requestAuthorization()
            await app.refresh()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func startLogin() async {
        guard let client = app.client else { return }
        error = nil
        busy = true
        defer { busy = false }

        do {
            let started = try await client.startLogin()
            loginSessionID = started.sessionID
            if started.loginURL.isEmpty {
                // local mode: the browser opened on the server machine.
                statusText = "A browser window has opened on the server machine. Finish signing in there."
            } else {
                loginURL = URL(string: started.loginURL)
            }
            await poll(sessionID: started.sessionID, client: client)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func poll(sessionID: String, client: APIClient) async {
        // The server holds the login browser open for HW_LOGIN_TIMEOUT; poll for
        // roughly that long, then give up gracefully.
        for _ in 0..<300 {
            try? await Task.sleep(for: .seconds(2))
            if Task.isCancelled { return }

            guard let status = try? await client.loginStatus(sessionID: sessionID) else { continue }
            if status.isAuthenticated {
                await app.refresh()
                dismiss()
                return
            }
            if !status.isPending {
                loginURL = nil
                error = status.detail ?? "Sign-in \(status.status)."
                return
            }
        }
        loginURL = nil
        error = "Sign-in timed out. Try again."
    }
}
