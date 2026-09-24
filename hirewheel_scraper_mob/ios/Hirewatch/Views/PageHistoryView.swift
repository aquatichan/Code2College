import SwiftUI

/// One page's timeline — the thing the desktop version could never do.
///
/// Because every scan now appends its own snapshot and screenshot instead of
/// overwriting the last one, this can scrub back through every state the page has
/// been in.
struct PageHistoryView: View {
    let pageKey: String

    @Environment(AppState.self) private var app
    @State private var entries: [HistoryEntry] = []
    @State private var selected: Int = 0
    @State private var items: [ItemDTO]?
    @State private var aspectRatio: CGFloat = 0.75
    @State private var error: String?
    @State private var loaded = false

    private var current: HistoryEntry? {
        entries.indices.contains(selected) ? entries[selected] : nil
    }

    private var title: String {
        app.pages.first { $0.key == pageKey }?.label ?? "History"
    }

    var body: some View {
        VStack(spacing: 0) {
            if !entries.isEmpty {
                scrubber
                Divider().overlay(Theme.border)
            }
            content
        }
        .background(Theme.bg)
        .navigationTitle(title)
        .toolbarBackground(Theme.surface, for: .navigationBar)
        .task { await loadHistory() }
        .task(id: current?.snapshotID) { await loadItems() }
    }

    // MARK: - Pieces

    /// Newest on the left, one tick per stored scan; a dot marks scans that
    /// actually found something.
    private var scrubber: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                    let active = index == selected
                    Button {
                        selected = index
                    } label: {
                        HStack(spacing: 4) {
                            Text(Format.when(entry.capturedAt))
                                .font(.caption)
                                .foregroundStyle(active ? Theme.onAccent : Theme.textMuted)
                                .fontWeight(active ? .bold : .regular)
                            if entry.changeCount > 0 {
                                Circle()
                                    .fill(active ? Theme.onAccent : Theme.added)
                                    .frame(width: 6, height: 6)
                            }
                        }
                        .padding(.horizontal, 12)
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
            }
            .padding(12)
        }
    }

    @ViewBuilder
    private var content: some View {
        if let error {
            Text(error).foregroundStyle(Theme.removed).padding()
            Spacer()
        } else if !loaded {
            Spacer()
            ProgressView().tint(Theme.accent)
            Spacer()
        } else if entries.isEmpty {
            Spacer()
            VStack(spacing: 6) {
                Text("No history for this page yet.")
                Text("It will fill in as scans run.")
            }
            .font(.callout)
            .multilineTextAlignment(.center)
            .foregroundStyle(Theme.textMuted)
            Spacer()
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let current {
                        Text(caption(for: current))
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)

                        if let path = current.screenshotPath {
                            AuthedImage(path: path) { ratio in
                                aspectRatio = ratio
                            }
                            .aspectRatio(aspectRatio, contentMode: .fit)
                            .frame(maxWidth: .infinity)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                        } else {
                            Text("No screenshot stored for this scan.")
                                .font(.caption).italic()
                                .foregroundStyle(Theme.textMuted)
                        }

                        Text("Items at this time")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.text)
                            .padding(.top, 8)

                        if let items {
                            if items.isEmpty {
                                Text("Nothing on the page.")
                                    .font(.caption).italic()
                                    .foregroundStyle(Theme.textMuted)
                            } else {
                                ForEach(items) { item in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.title)
                                            .font(.subheadline)
                                            .foregroundStyle(Theme.text)
                                        if let detail = item.detail {
                                            Text(detail)
                                                .font(.caption)
                                                .foregroundStyle(Theme.textMuted)
                                                .lineLimit(2)
                                        }
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(12)
                                    .background(Theme.surface)
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                                }
                            }
                        } else {
                            ProgressView().tint(Theme.accent)
                        }
                    }
                }
                .padding(16)
            }
        }
    }

    private func caption(for entry: HistoryEntry) -> String {
        var text = Format.plural(entry.itemCount, "item")
        if entry.changeCount > 0 {
            text += " · \(Format.plural(entry.changeCount, "change"))"
        }
        return text
    }

    // MARK: - Loading

    private func loadHistory() async {
        guard let client = app.client, !loaded else { return }
        do {
            entries = try await client.history(pageKey: pageKey)
            selected = 0
        } catch {
            self.error = error.localizedDescription
        }
        loaded = true
    }

    private func loadItems() async {
        guard let client = app.client, let current else { return }
        items = nil
        items = (try? await client.snapshot(id: current.snapshotID))?.items ?? []
    }
}
