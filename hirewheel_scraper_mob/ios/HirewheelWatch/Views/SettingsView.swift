import StoreKit
import SwiftUI

/// Account, appearance, scan cadence, notification mutes, and the two exits.
struct SettingsView: View {
    @Environment(AppState.self) private var app

    @State private var muted: Set<String> = []
    @State private var intervalSeconds: Int = 24 * 3600
    @State private var error: String?
    @State private var showDeleteConfirm = false
    @State private var loaded = false

    /// 24 hours is the standard; the shorter cadences are a paid feature.
    private static let intervals: [(label: String, seconds: Int)] = [
        ("1 hour", 3600),
        ("3 hours", 3 * 3600),
        ("6 hours", 6 * 3600),
        ("12 hours", 12 * 3600),
        ("24 hours", 24 * 3600),
    ]

    private var freeMinimum: Int { app.me?.freeMinIntervalSeconds ?? 24 * 3600 }

    /// The server is the authority on what has been paid for.
    private func requiresPurchase(_ seconds: Int) -> Bool {
        !(app.me?.allows(interval: seconds) ?? (seconds >= freeMinimum))
    }

    private func productID(forInterval seconds: Int) -> String? {
        app.me?.products.first { $0.intervalSeconds == seconds }?.productID
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                sectionTitle("Account")
                accountCard

                sectionTitle("Appearance")
                appearancePicker

                sectionTitle("Scan every")
                intervalPicker
                Text("24 hours is the standard. Each faster interval is a separate one-time purchase — no subscription.")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                if let purchaseError = app.store.purchaseError {
                    Text(purchaseError).font(.caption).foregroundStyle(Theme.removed)
                }
                restoreButton

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
            HStack {
                Text("Signed in as")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Text("every \(intervalSeconds / 3600)h")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(intervalSeconds < freeMinimum ? Theme.onAccent : Theme.textMuted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(intervalSeconds < freeMinimum ? Theme.accent : Theme.surfaceAlt)
                    .clipShape(Capsule())
            }
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

    private var intervalPicker: some View {
        // Five options wrap onto two rows on a phone.
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 8)], spacing: 8) {
            ForEach(Self.intervals, id: \.seconds) { option in
                intervalPill(option)
            }
        }
    }

    private func intervalPill(_ option: (label: String, seconds: Int)) -> some View {
        let locked = requiresPurchase(option.seconds)
        let active = intervalSeconds == option.seconds && !locked
        let product = productID(forInterval: option.seconds).flatMap { app.store.product(for: $0) }

        return Button {
            if locked {
                Task { await buy(interval: option.seconds) }
            } else {
                Task { await setInterval(option.seconds) }
            }
        } label: {
            VStack(spacing: 2) {
                Text(option.label)
                    .font(.caption)
                    .fontWeight(active ? .bold : .regular)
                if locked {
                    // The real localised price — App Review requires showing what
                    // the user will actually be charged. While StoreKit is still
                    // loading (or unavailable) say so, rather than a bare dash
                    // beneath a button that does nothing.
                    Text(priceLabel(for: product))
                        .font(.caption2)
                        .fontWeight(.semibold)
                }
            }
            .foregroundStyle(active ? Theme.onAccent : (locked ? Theme.accent : Theme.textMuted))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(active ? Theme.accent : Theme.surface)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(active ? Theme.accent : Theme.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    private func priceLabel(for product: Product?) -> String {
        if let product { return product.displayPrice }
        return app.store.isLoading ? "…" : "Unavailable"
    }

    private var restoreButton: some View {
        Button {
            Task { await app.store.restore() }
        } label: {
            Text("Restore purchases")
                .font(.caption)
                .foregroundStyle(Theme.accent)
        }
        .buttonStyle(.plain)
    }

    private func buy(interval seconds: Int) async {
        guard let id = productID(forInterval: seconds) else {
            error = "That option isn't offered by your server."
            return
        }

        if app.store.product(for: id) == nil {
            // Most often this is the StoreKit configuration not being active —
            // which happens whenever the app wasn't launched from Xcode.
            await app.store.load()
        }

        guard let product = app.store.product(for: id) else {
            error = app.store.purchaseError ?? "That purchase isn't available right now."
            return
        }

        if await app.store.purchase(product) {
            // The server decides what the purchase unlocked; then apply it.
            await app.refresh()
            await setInterval(seconds)
        }
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
            app.signOut()
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
        intervalSeconds = me.intervalSeconds
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

    private func setInterval(_ seconds: Int) async {
        guard let client = app.client else { return }
        let previous = intervalSeconds
        intervalSeconds = seconds
        do {
            try await client.setInterval(seconds)
            await app.refresh()
        } catch {
            intervalSeconds = previous
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
