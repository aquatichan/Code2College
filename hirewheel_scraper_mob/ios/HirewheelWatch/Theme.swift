import SwiftUI

/// Semantic colours, defined once per role and resolved per appearance.
///
/// Each token is a *role*, not a shade — `text`, `surface`, `added` — so light
/// and dark are two values of the same idea rather than two parallel palettes.
/// Crucially the foreground roles flip too: a design that only swaps container
/// colours ends up with dark grey text on a dark card.
///
/// Resolution happens inside `UIColor`, so views never read `colorScheme` and a
/// token is always correct for wherever it is drawn.
enum Theme {
    /// App background — the ground everything sits on.
    static let bg = Color.dynamic(light: 0xF5F7FA, dark: 0x0F1720)
    /// Cards and raised panels.
    static let surface = Color.dynamic(light: 0xFFFFFF, dark: 0x1B2430)
    /// Quieter fills: inert badges, image placeholders.
    static let surfaceAlt = Color.dynamic(light: 0xE7ECF2, dark: 0x222D3B)
    /// Hairlines and outlines.
    static let border = Color.dynamic(light: 0xD5DDE6, dark: 0x2A3644)

    /// Primary reading text.
    static let text = Color.dynamic(light: 0x10171F, dark: 0xE6EDF3)
    /// Secondary text: timestamps, captions, supporting detail.
    static let textMuted = Color.dynamic(light: 0x56626F, dark: 0x8B98A5)

    /// Interactive accent. Darker in light mode so it stays legible on white.
    static let accent = Color.dynamic(light: 0x0B62D6, dark: 0x4B9FFF)
    /// Text drawn *on top of* a saturated fill (accent, added, removed).
    static let onAccent = Color.dynamic(light: 0xFFFFFF, dark: 0x0F1720)

    /// Diff semantics. The light variants are deepened — mid-tone green and
    /// especially yellow are unreadable on a white card.
    static let added = Color.dynamic(light: 0x15803D, dark: 0x3FB950)
    static let changed = Color.dynamic(light: 0x8A6A00, dark: 0xD2BE22)
    static let removed = Color.dynamic(light: 0xC0322C, dark: 0xF85149)
}

extension Color {
    /// A colour that resolves itself from the surrounding appearance.
    static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            UIColor(rgb: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

extension UIColor {
    fileprivate convenience init(rgb: UInt32) {
        self.init(
            red: CGFloat((rgb >> 16) & 0xFF) / 255,
            green: CGFloat((rgb >> 8) & 0xFF) / 255,
            blue: CGFloat(rgb & 0xFF) / 255,
            alpha: 1
        )
    }
}

/// What the user picked in Settings. `system` follows the device.
enum Appearance: String, CaseIterable, Identifiable {
    case system, light, dark

    var id: String { rawValue }

    var label: String {
        switch self {
        case .system: "System"
        case .light: "Light"
        case .dark: "Dark"
        }
    }

    /// nil hands the decision back to iOS.
    var colorScheme: ColorScheme? {
        switch self {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}
