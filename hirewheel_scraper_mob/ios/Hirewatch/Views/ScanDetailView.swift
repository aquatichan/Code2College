import SwiftUI

/// One scan in full: what was added, changed and removed on each page.
struct ScanDetailView: View {
    let scanID: Int

    @Environment(AppState.self) private var app
    @State private var detail: ScanDetail?
    @State private var missing = false

    var body: some View {
        ScrollView {
            if let detail {
                VStack(alignment: .leading, spacing: 12) {
                    Text(Format.when(detail.startedAt))
                        .font(.title2.bold())
                        .foregroundStyle(Theme.text)
                    Text(summary(for: detail))
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)

                    ForEach(detail.changedPages) { page in
                        PageCard(page: page) {
                            app.path.append(.history(page.pageKey))
                        }
                    }

                    let failed = detail.pages.filter { $0.error != nil }
                    let quiet = detail.pages.count - detail.changedPages.count - failed.count
                    if quiet > 0 {
                        Text("\(Format.plural(quiet, "page")) unchanged")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                            .frame(maxWidth: .infinity)
                    }

                    if !failed.isEmpty {
                        failures(failed)
                    }
                }
                .padding(16)
            } else if missing {
                Text("This scan is no longer stored.").foregroundStyle(Theme.textMuted).padding()
            } else {
                ProgressView().tint(Theme.accent).padding(.top, 60)
            }
        }
        .background(Theme.bg)
        .navigationTitle("Scan")
        .toolbarBackground(Theme.surface, for: .navigationBar)
        .task { await load() }
    }

    private func summary(for detail: ScanDetail) -> String {
        guard detail.status == "ok" else { return detail.error ?? detail.status }
        let changed = detail.changedPages
        guard !changed.isEmpty else { return "Nothing changed this scan" }
        return "\(Format.plural(detail.changeCount, "change")) across \(Format.plural(changed.count, "page"))"
    }

    /// Pages that couldn't be read. Shown so a page whose markup moved doesn't
    /// just go quiet.
    private func failures(_ pages: [PageDiff]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Couldn't check \(Format.plural(pages.count, "page"))")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Theme.removed)
            ForEach(pages) { page in
                Text("\(page.label): \(page.error ?? "")")
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func load() async {
        detail = await LocalStore.shared.scan(id: scanID)
        missing = detail == nil
    }
}

private struct PageCard: View {
    let page: PageDiff
    let onShowHistory: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Button(action: onShowHistory) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(page.label)
                        .font(.headline)
                        .foregroundStyle(Theme.text)
                    Text("View page →")
                        .font(.caption2)
                        .foregroundStyle(Theme.accent)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)

            ForEach(page.added) { item in
                ItemRow(item: item, tint: Theme.added, label: "NEW")
            }
            ForEach(page.changed) { change in
                ChangedRow(change: change)
            }
            ForEach(page.removed) { item in
                ItemRow(item: item, tint: Theme.removed, label: "GONE")
            }
        }
        .padding(16)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct ItemRow: View {
    let item: Item
    let tint: Color
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 10, weight: .heavy))
                .kerning(0.5)
                .foregroundStyle(tint)
            Text(item.title)
                .font(.subheadline)
                .foregroundStyle(Theme.text)
            if let detail = item.detail {
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                    .lineLimit(3)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.leading, 12)
        .overlay(alignment: .leading) {
            Rectangle().fill(tint).frame(width: 3)
        }
    }
}

private struct ChangedRow: View {
    let change: ItemChange

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("CHANGED")
                .font(.system(size: 10, weight: .heavy))
                .kerning(0.5)
                .foregroundStyle(Theme.changed)
            Text(change.item.title)
                .font(.subheadline)
                .foregroundStyle(Theme.text)
            ForEach(change.deltas, id: \.field) { delta in
                HStack(spacing: 4) {
                    Text("\(delta.field):")
                        .foregroundStyle(Theme.textMuted)
                    Text(delta.before)
                        .strikethrough()
                        .foregroundStyle(Theme.removed)
                    Text("→").foregroundStyle(Theme.textMuted)
                    Text(delta.after).foregroundStyle(Theme.added)
                }
                .font(.caption)
                .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.leading, 12)
        .overlay(alignment: .leading) {
            Rectangle().fill(Theme.changed).frame(width: 3)
        }
    }
}
