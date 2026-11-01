import SwiftUI
import UIKit
import WebKit

/// Hirewheel's own login page, in the app.
///
/// The password is typed into Hirewheel's form and goes straight to Hirewheel;
/// the app never reads it. Once a page loads that *isn't* the login form, the
/// session cookies are handed to `onSession`, which checks they really work.
struct HirewheelLoginView: UIViewRepresentable {
    /// Returns true if the session was accepted; false keeps the page waiting.
    let onSession: @MainActor (_ cookies: [HTTPCookie], _ userAgent: String?) async -> Bool

    func makeCoordinator() -> Coordinator { Coordinator(onSession: onSession) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // The default store persists, so signing in again after the session
        // expires can be as quick as one tap.
        config.websiteDataStore = .default()
        let view = WKWebView(frame: .zero, configuration: config)
        view.navigationDelegate = context.coordinator
        view.load(URLRequest(url: Hirewheel.probeURL))
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {}

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        let onSession: @MainActor ([HTTPCookie], String?) async -> Bool
        private var checking = false

        init(onSession: @escaping @MainActor ([HTTPCookie], String?) async -> Bool) {
            self.onSession = onSession
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            // Hirewheel bounces signed-out visitors to its login form, so
            // landing anywhere else on the site is the cue to check.
            guard !checking, Hirewheel.isHirewheel(webView.url), !Hirewheel.isLoginPage(webView.url) else { return }
            checking = true
            Task {
                let cookies = await webView.configuration.websiteDataStore.httpCookieStore.allCookies()
                let agent = try? await webView.evaluateJavaScript("navigator.userAgent") as? String
                if await onSession(cookies, agent) { return }
                // Not actually signed in (a public page, say). Back to the form.
                checking = false
                webView.load(URLRequest(url: Hirewheel.probeURL))
            }
        }
    }
}

/// A saved copy of a page, rendered as it looked when it was captured.
///
/// The page's own scripts are switched off — this is a record, not a live
/// session — and hidden tabs and collapsed sections are forced open so their
/// content is visible. Tapping a link opens the real page in Safari.
struct SnapshotPageView: UIViewRepresentable {
    let snapshotID: Int
    let html: String

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // Shares the login's cookies, so images behind sign-in still load.
        config.websiteDataStore = .default()
        config.defaultWebpagePreferences.allowsContentJavaScript = false
        let view = WKWebView(frame: .zero, configuration: config)
        view.navigationDelegate = context.coordinator
        view.isOpaque = false
        view.backgroundColor = .clear
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {
        // Only reload when the snapshot changes, not on every SwiftUI re-render.
        guard context.coordinator.loaded != snapshotID else { return }
        context.coordinator.loaded = snapshotID
        view.loadHTMLString(Self.prepared(html), baseURL: Hirewheel.baseURL)
    }

    private static let revealCSS = """
    <style>
    *, *::before, *::after { animation: none !important; transition: none !important; }
    .tab-pane { display: block !important; opacity: 1 !important; }
    .collapse:not(.navbar-collapse) { display: block !important; height: auto !important; }
    [class*="fade"]:not(.modal), [class*="reveal"], [class*="animate"], [class*="skeleton"],
    [data-aos], [data-animate] {
        opacity: 1 !important; transform: none !important; visibility: visible !important;
    }
    </style>
    """

    private static func prepared(_ html: String) -> String {
        if let head = html.range(of: "<head>", options: .caseInsensitive) {
            var out = html
            out.insert(contentsOf: revealCSS, at: head.upperBound)
            return out
        }
        return revealCSS + html
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        var loaded: Int?

        func webView(
            _ webView: WKWebView,
            decidePolicyFor action: WKNavigationAction
        ) async -> WKNavigationActionPolicy {
            if action.navigationType == .linkActivated, let url = action.request.url {
                await UIApplication.shared.open(url)
                return .cancel
            }
            return .allow
        }
    }
}
