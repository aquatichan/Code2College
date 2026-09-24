import SwiftUI

/// Account, appearance, scan schedule, notification mutes, and the two exits.
struct SettingsView: View {
    @Environment(AppState.self) private var app

    @State private var muted: Set<String> = []
    @State private var error: String?
    @State private var showDeleteConfirm = false
    @State private var loaded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                sectionTitle("Account")
                accountCard

                sectionTitle("Appearance")
                appearancePicker

                sectionTitle("Scanning")
                scheduleCard

                sectionTitle("Notify me about")
                mutesCard

                if app.me?.remotePush == false {
                    Text("Remote push isn't configured on your server, so this app checks for updates in the background instead. iOS decides when that happens, so alerts can arrive late.")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }

                if let error {
                    Text(error).font(.caption).foregroundStyle(Theme.removed)
                }

                signOutButton
                deleteButton

                Text("Your Hirewheel session is stored encrypted on your server so it can scan while your phone is asleep. Deleting your account removes it immediately.")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                    .padding(.top, 4)

                legalLinks
            }
            .padding(16)
        }
        .background(Theme.bg)
        .navigationTitle("Settings")
        .toolbarBackground(Theme.surface, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .task { load() }
        .alert("Delete everything?", isPresented: $showDeleteConfirm) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) { Task { await deleteAccount() } }
        } message: {
            Text("This erases your stored Hirewheel session, every scan, and every screenshot. It cannot be undone.")
        }
    }

    // MARK: - Pieces

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Theme.text)
            .padding(.top, 8)
    }

    private var accountCard: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Signed in as")
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
            Text(app.me?.email ?? "—")
                .font(.subheadline)
                .foregroundStyle(Theme.text)
                .textSelection(.enabled)
            if app.me?.email == nil {
                Text("Your email appears here after signing in to Hirewheel.")
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var appearancePicker: some View {
        Picker("Appearance", selection: Binding(
            get: { app.appearance },
            set: { app.appearance = $0 }
        )) {
            ForEach(Appearance.allCases) { option in
                Text(option.label).tag(option)
            }
        }
        .pickerStyle(.segmented)
    }

    private var scheduleCard: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Every \((app.me?.intervalSeconds ?? 3 * 3600) / 3600) hours")
                .font(.subheadline)
                .foregroundStyle(Theme.text)
            Text("Your pages are checked on this schedule automatically. Tap the refresh button on the main screen to scan right now.")
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var mutesCard: some View {
        VStack(spacing: 0) {
            ForEach(app.pages) { page in
                Toggle(isOn: binding(for: page.key)) {
                    Text(page.label)
                        .font(.subheadline)
                        .foregroundStyle(Theme.text)
                }
                .tint(Theme.accent)
                .padding(.vertical, 12)

                if page.key != app.pages.last?.key {
                    Divider().overlay(Theme.border)
                }
            }
        }
        .padding(.horizontal, 16)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    /// The toggle reads as "notify me", which is the inverse of the stored mute.
    private func binding(for key: String) -> Binding<Bool> {
        Binding(
            get: { !muted.contains(key) },
            set: { notify in
                let previous = muted
                if notify { muted.remove(key) } else { muted.insert(key) }
                Task { await saveMutes(rollbackTo: previous) }
            }
        )
    }

    private var signOutButton: some View {
        Button {
            Task { await app.signOutOfDevice() }
        } label: {
            Text("Sign out of this device")
                .font(.subheadline)
                .foregroundStyle(Theme.text)
                .frame(maxWidth: .infinity)
                .padding(12)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.border, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .padding(.top, 8)
    }

    private var deleteButton: some View {
        Button {
            showDeleteConfirm = true
        } label: {
            Text("Delete my account and all data")
                .font(.subheadline.bold())
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(12)
                .background(Theme.removed)
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }

    /// App Store Connect requires a reachable privacy policy, and an app that
    /// reads a third party's platform should say plainly that it is unofficial.
    private var legalLinks: some View {
        VStack(spacing: 6) {
            HStack(spacing: 14) {
                Link("Terms of Service", destination: Self.termsURL)
                Text("·").foregroundStyle(Theme.textMuted)
                Link("Privacy Policy", destination: Self.privacyURL)
            }
            .font(.caption)
            .tint(Theme.accent)

            Text("Unofficial. Not affiliated with or endorsed by Code2College.")
                .font(.caption2)
                .foregroundStyle(Theme.textMuted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 12)
    }

    private static let termsURL = URL(
        string: "https://github.com/aquatichan/Code2College/blob/main/hirewheel_scraper_mob/TERMS.md"
    )!
    private static let privacyURL = URL(
        string: "https://github.com/aquatichan/Code2College/blob/main/hirewheel_scraper_mob/PRIVACY.md"
    )!

    // MARK: - Actions

    private func load() {
        guard !loaded, let me = app.me else { return }
        muted = Set(me.mutedPages)
        loaded = true
    }

    private func saveMutes(rollbackTo previous: Set<String>) async {
        guard let client = app.client else { return }
        do {
            try await client.setMutedPages(Array(muted))
        } catch {
            // Put the switch back where the server still believes it is.
            muted = previous
            self.error = error.localizedDescription
        }
    }


    private func deleteAccount() async {
        if let client = app.client {
            // Even if the call fails, sign out locally — the user asked to leave.
            _ = try? await client.deleteAccount()
        }
        app.signOut()
    }
}
