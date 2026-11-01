import SwiftUI

/// One page's timeline: every distinct state it has been in, newest first.
///
/// A copy of the page is saved only when its content changes, so each stop on
/// the scrubber is a real change, and it can be viewed as the page looked then.
struct PageHistoryView: View {
    let pageKey: String

    @Environment(AppState.self) private var app
    @State private var entries: [HistoryEntry] = []
    @State private var selected: Int = 0
    @State private var items: [Item]?
    @State private var html: String?
    @State private var snapshotLoaded = false
    @State private var tab: Tab = .page
    @State private var loaded = false

    private enum Tab: String, CaseIterable {
        case page = "Page"
        case items = "Items"
    }

    private var current: HistoryEntry? {
        entries.indices.contains(selected) ? entries[selected] : nil
    }

    private var title: String {
        entries.first?.label ?? Hirewheel.label(for: pageKey) ?? "History"
    }

    var body: some View {
        VStack(spacing: 0) {
            if !entries.isEmpty {
                scrubber
                Picker("View", selection: $tab) {
                    ForEach(Tab.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
                Divider().overlay(Theme.border)
            }
            content
        }
        .background(Theme.bg)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.surface, for: .navigationBar)
        .task { await loadHistory() }
        .task(id: current?.snapshotID) { await loadSnapshot() }
    }

    // MARK: - Pieces

    /// Newest on the left; a dot marks states that were a change from the one
    /// before (the oldest is just where watching started).
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
        if !loaded {
            Spacer()
            ProgressView().tint(Theme.accent)
            Spacer()
        } else if entries.isEmpty {
            Spacer()
            VStack(spacing: 6) {
                Text("No history for this page yet.")
                Text("It fills in as scans run.")
            }
            .font(.callout)
            .multilineTextAlignment(.center)
            .foregroundStyle(Theme.textMuted)
            Spacer()
        } else if let current {
            switch tab {
            case .page:
                if let html {
                    SnapshotPageView(snapshotID: current.snapshotID, html: html)
                } else if !snapshotLoaded {
                    Spacer()
                    ProgressView().tint(Theme.accent)
                    Spacer()
                } else {
                    Spacer()
                    Text("This copy of the page is no longer stored.")
                        .font(.caption).italic()
                        .foregroundStyle(Theme.textMuted)
                    Spacer()
                }
            case .items:
                itemList(current)
            }
        }
    }

    private func itemList(_ entry: HistoryEntry) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(caption(for: entry))
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)

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
            .padding(16)
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
        guard !loaded else { return }
        entries = await LocalStore.shared.history(pageKey: pageKey)
        selected = 0
        loaded = true
    }

    private func loadSnapshot() async {
        guard let current else { return }
        items = nil
        html = nil
        snapshotLoaded = false
        items = await LocalStore.shared.snapshotItems(id: current.snapshotID)
        html = await LocalStore.shared.snapshotHTML(id: current.snapshotID)
        snapshotLoaded = true
    }
}
