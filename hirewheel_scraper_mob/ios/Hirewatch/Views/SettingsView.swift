import SwiftUI

/// Account, appearance, scan schedule, notification mutes, and the two exits.
struct SettingsView: View {
    @Environment(AppState.self) private var app

    @State private var muted: Set<String> = []
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

                signOutButton
                deleteButton

                Text("Everything stays on this phone: your Hirewheel session is in the Keychain, and scans and saved pages are in the app's own storage. Nothing is sent anywhere except Hirewheel itself.")
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
        .task { await load() }
        .alert("Delete everything?", isPresented: $showDeleteConfirm) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) { Task { await deleteAccount() } }
        } message: {
            Text("This signs you out and erases every scan and saved page on this phone. It cannot be undone.")
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
            Text(app.status.email ?? "—")
                .font(.subheadline)
                .foregroundStyle(Theme.text)
                .textSelection(.enabled)
            if app.status.email == nil {
                Text("Your email appears here after the first scan.")
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
            Text("On this phone, in the background")
                .font(.subheadline)
                .foregroundStyle(Theme.text)
            Text("Hirewatch checks when you open it (if it's been 30 minutes) and whenever iOS gives it background time, usually every few hours. iOS gives more time to apps you use often, so opening it now and then helps. Pull down on the main screen to check right now.")
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
                if notify { muted.remove(key) } else { muted.insert(key) }
                Task { await LocalStore.shared.setMutedPages(Array(muted)) }
            }
        )
    }

    private var signOutButton: some View {
        Button {
            Task { await app.signOut() }
        } label: {
            Text("Sign out of Hirewheel")
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
            Text("Sign out and delete all data")
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

    /// Read from the store, not `app.status`, which is only as fresh as the
    /// last refresh and may predate a toggle made a moment ago.
    private func load() async {
        guard !loaded else { return }
        muted = Set(await LocalStore.shared.status().mutedPages)
        loaded = true
    }

    private func deleteAccount() async {
        await app.deleteEverything()
    }
}
