# Each is a *slight* shift from the original navy #0f3856 / sky #0ea3db.
PALETTES = {
    # navy nudged toward indigo; braces take the app's own accent blue
    "A_indigo": dict(cap="#1C2B5A", braces="#4B9FFF", outline="#0B1220", eye="#FFFFFF",
                     pupil="#0B1220", dots="#1C2B5A", bg_top="#FFFFFF", bg_bottom="#EDF2FA"),
    # navy nudged toward deep teal; braces teal
    "B_teal":   dict(cap="#0E3B46", braces="#17B3A3", outline="#0B1220", eye="#FFFFFF",
                     pupil="#0B1220", dots="#0E3B46", bg_top="#FFFFFF", bg_bottom="#ECF6F5"),
    # navy nudged toward violet; braces periwinkle
    "C_violet": dict(cap="#2A2160", braces="#7B8CFF", outline="#0B1220", eye="#FFFFFF",
                     pupil="#0B1220", dots="#2A2160", bg_top="#FFFFFF", bg_bottom="#F0EFFA"),
}
# iOS 18 dark-appearance icon for option A: same art, light cap on the app's dark ground
DARK_A = dict(cap="#DCE5F2", braces="#4B9FFF", outline="#0B1220", eye="#FFFFFF",
              pupil="#0B1220", dots="#DCE5F2", bg_top="#1A2436", bg_bottom="#0F1720")
