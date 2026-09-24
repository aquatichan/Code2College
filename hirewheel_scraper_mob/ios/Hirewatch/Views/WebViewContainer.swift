import SwiftUI
import WebKit

/// Renders the server's streamed login browser (noVNC) inside the app.
struct WebViewContainer: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // noVNC is a normal web app; it needs JS and its own storage.
        config.websiteDataStore = .nonPersistent()
        let view = WKWebView(frame: .zero, configuration: config)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.bounces = false
        view.load(URLRequest(url: url))
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {
        // Only reload when the target actually changes — otherwise every SwiftUI
        // re-render would restart the login session.
        if view.url != url {
            view.load(URLRequest(url: url))
        }
    }
}
