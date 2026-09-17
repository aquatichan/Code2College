import SwiftUI

/// Every scan, newest first — the mobile answer to the desktop watch window.
struct FeedView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                if app.me?.needsReauth == true {
                    reauthBanner
                }

                statusRow
                pageStrip

                if let error = app.loadError {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(Theme.removed)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 16)
                }

                if app.scans.isEmpty {
                    emptyState
                } else {
                    ForEach(app.scans) { scan in
                        Button {
                            app.path.append(.scan(scan.id))
                        } label: {
                            ScanRow(scan: scan)
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal, 16)
                    }
                }

                Text("Created by Aaron Qin")
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 20)
            }
            .padding(.vertical, 12)
        }
        .background(Theme.bg)
        .navigationTitle("Hirewheel Watch")
        .navigationBarTitleDisplayMode(.inline)
        // Both lines are needed: the first picks the colour, the second stops the
        // bar going transparent at the top of the scroll (which was swallowing
        // the title entirely).
        .toolbarBackground(Theme.surface, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .refreshable { await app.refresh() }
        // Re-read periodically so a scan that runs server-side while the app is
        // open shows up on its own. Cancelled automatically when the view goes away.
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(60))
                if Task.isCancelled { break }
                await app.refresh()
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await app.scanNow() }
                } label: {
                    if app.isRefreshing {
                        ProgressView().controlSize(.small).tint(Theme.accent)
                    } else {
                        Label("Scan now", systemImage: "arrow.clockwise")
                    }
                }
                .disabled(app.isRefreshing || app.me?.needsReauth == true)
            }
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    app.path.append(.settings)
                } label: {
                    Image(systemName: "gearshape")
                }
            }
        }
    }

    // MARK: - Pieces

    private var statusRow: some View {
        // `Format.relative` is evaluated at render time, and nothing about the
        // view changes as minutes pass — so without a periodic redraw the label
        // would read "just now" indefinitely. TimelineView supplies that tick
        // without any network traffic.
        TimelineView(.periodic(from: .now, by: 30)) { _ in
            statusContent
        }
    }

    private var statusContent: some View {
        HStack(spacing: 6) {
            if app.isRefreshing {
                ProgressView().controlSize(.mini).tint(Theme.textMuted)
            }
            Text(statusText)
                .lineLimit(1)
            Spacer(minLength: 8)
            if app.me?.remotePush == false {
                // Be honest about why alerts might be slow.
                Image(systemName: "moon.zzz")
                Text("background")
            }
        }
        .font(.caption)
        .foregroundStyle(Theme.textMuted)
        .padding(.horizontal, 16)
    }

    private var statusText: String {
        let status = app.me?.runnerStatus ?? ""
        if !status.isEmpty && status != "idle" { return status }
        if app.isRefreshing { return "Starting scan…" }
        return "Last scan \(Format.relative(app.me?.lastScanAt))"
    }

    private var reauthBanner: some View {
        Button {
            app.showingSignIn = true
        } label: {
            Text("Session expired — tap to sign in again")
                .font(.footnote.bold())
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(12)
                .background(Theme.removed)
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 16)
    }

    /// Jump straight into any page's timeline without hunting for a scan.
    private var pageStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(app.pages) { page in
                    Button {
                        app.path.append(.history(page.key))
                    } label: {
                        Text(page.label)
                            .font(.caption)
                            .lineLimit(1)
                            .foregroundStyle(Theme.text)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(Theme.surface)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(Theme.border, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    .buttonStyle(.plain)
                }
            }
            // Inside the scroll content, so the first and last chip both clear
            // the screen edge instead of being sliced off.
            .padding(.horizontal, 16)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Text("Watching your Hirewheel pages.")
            Text("New opportunities and updates will appear here.")
        }
        .font(.callout)
        .multilineTextAlignment(.center)
        .foregroundStyle(Theme.textMuted)
        .padding(.horizontal, 16)
        .padding(.top, 60)
    }
}

private struct ScanRow: View {
    let scan: ScanSummary

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(Format.when(scan.startedAt))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.text)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            Spacer(minLength: 8)
            Text(scan.failed ? "!" : "\(scan.changeCount)")
                .font(.subheadline.bold())
                .foregroundStyle(Theme.onAccent)
                .frame(minWidth: 32, minHeight: 32)
                .background(badgeColor)
                .clipShape(Circle())
        }
        .padding(16)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var subtitle: String {
        if scan.status == "auth_needed" { return "Signed out — no scan" }
        if scan.status == "error" { return scan.error ?? "Scan failed" }
        if scan.status == "running" { return "Scanning…" }
        return scan.changeCount > 0 ? Format.plural(scan.changeCount, "change") : "No changes"
    }

    private var badgeColor: Color {
        if scan.failed { return Theme.removed }
        return scan.changeCount > 0 ? Theme.added : Theme.surfaceAlt
    }
}
