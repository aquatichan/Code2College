import SwiftUI

/// Loads a screenshot from the server's token-guarded `/media` endpoint.
///
/// `AsyncImage` can't do this: it takes a bare URL and has nowhere to put the
/// Authorization header. The images are WebP, which iOS decodes natively.
struct AuthedImage: View {
    let path: String
    var contentMode: ContentMode = .fit
    /// Reports the image's aspect ratio once known, so callers can size a tall
    /// full-page screenshot correctly instead of guessing.
    var onAspectRatio: ((CGFloat) -> Void)?

    @Environment(AppState.self) private var app
    @State private var image: UIImage?
    @State private var failed = false

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else if failed {
                placeholder(icon: "exclamationmark.triangle", text: "Screenshot unavailable")
            } else {
                placeholder(icon: nil, text: nil)
            }
        }
        .task(id: path) { await load() }
    }

    @ViewBuilder
    private func placeholder(icon: String?, text: String?) -> some View {
        ZStack {
            Theme.surfaceAlt
            VStack(spacing: 6) {
                if let icon {
                    Image(systemName: icon).foregroundStyle(Theme.textMuted)
                } else {
                    ProgressView().tint(Theme.textMuted)
                }
                if let text {
                    Text(text).font(.caption2).foregroundStyle(Theme.textMuted)
                }
            }
        }
    }

    private func load() async {
        guard let client = app.client else { return }
        image = nil
        failed = false
        do {
            let data = try await client.screenshot(path: path)
            guard let decoded = UIImage(data: data) else {
                failed = true
                return
            }
            image = decoded
            if decoded.size.height > 0 {
                onAspectRatio?(decoded.size.width / decoded.size.height)
            }
        } catch {
            failed = true
        }
    }
}
