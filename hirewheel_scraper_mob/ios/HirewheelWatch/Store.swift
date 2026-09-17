import Foundation
import StoreKit
import Observation

/// One-time purchases that unlock faster scan intervals.
///
/// These are **non-consumables**, so Apple owns the record of what was bought:
/// `Transaction.currentEntitlements` returns it on any device the Apple ID signs
/// into, survives reinstalls, and is restorable for free. There is no
/// subscription and no "plan" — owning a product simply unlocks its interval,
/// and a faster one implies every slower one.
///
/// StoreKit verifies transactions on the device, but the device is exactly what
/// the server cannot trust, so every entitlement is forwarded to the server as
/// its signed representation and re-verified there.
@MainActor
@Observable
final class Store {
    /// Products, fastest (most expensive) first.
    private(set) var products: [Product] = []
    private(set) var ownedProductIDs: Set<String> = []
    private(set) var isLoading = false
    private(set) var purchaseError: String?

    /// Set by the app so a new entitlement can be pushed to the server.
    var onEntitlementsChanged: (([String]) async -> Void)?

    private var updatesTask: Task<Void, Never>?

    static let productIDs = [
        "com.aaronqin.HirewheelWatch.interval1h",
        "com.aaronqin.HirewheelWatch.interval3h",
        "com.aaronqin.HirewheelWatch.interval6h",
        "com.aaronqin.HirewheelWatch.interval12h",
    ]

    /// Scan interval each product unlocks, in seconds.
    static let intervalForProduct: [String: Int] = [
        "com.aaronqin.HirewheelWatch.interval1h": 3600,
        "com.aaronqin.HirewheelWatch.interval3h": 3 * 3600,
        "com.aaronqin.HirewheelWatch.interval6h": 6 * 3600,
        "com.aaronqin.HirewheelWatch.interval12h": 12 * 3600,
    ]

    init() {
        // Purchases can also arrive from outside the app: Ask to Buy approvals,
        // another device, a restore. Listen for the whole life of the app.
        updatesTask = Task { [weak self] in
            for await update in Transaction.updates {
                guard case .verified(let transaction) = update else { continue }
                await transaction.finish()
                await self?.refreshEntitlements()
            }
        }
    }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let loaded = try await Product.products(for: Self.productIDs)
            // Cheapest interval is the slowest; show fastest first.
            products = loaded.sorted {
                (Self.intervalForProduct[$0.id] ?? 0) < (Self.intervalForProduct[$1.id] ?? 0)
            }
            if loaded.isEmpty {
                // StoreKit answers "no such products" rather than throwing when
                // no configuration is active, so an empty result is the normal
                // symptom of the test config not being applied — not an error.
                print("[store] 0 products returned for \(Self.productIDs)")
            } else {
                purchaseError = nil
                print("[store] loaded \(loaded.count) products: \(loaded.map(\.id))")
            }
        } catch {
            purchaseError = "Couldn't load prices: \(error.localizedDescription)"
            print("[store] load failed: \(error)")
        }
        await refreshEntitlements()
    }

    func product(for id: String) -> Product? {
        products.first { $0.id == id }
    }

    /// Buy one interval. Returns true when the purchase completed.
    @discardableResult
    func purchase(_ product: Product) async -> Bool {
        purchaseError = nil
        do {
            switch try await product.purchase() {
            case .success(let verification):
                guard case .verified(let transaction) = verification else {
                    // StoreKit itself couldn't vouch for it; never trust it.
                    purchaseError = "That purchase couldn't be verified."
                    return false
                }
                await transaction.finish()
                await refreshEntitlements()
                return true

            case .userCancelled:
                return false

            case .pending:
                // Ask to Buy: a parent still has to approve. Transaction.updates
                // will deliver it later, which matters here since many C2C
                // students are minors with managed Apple IDs.
                purchaseError = "Waiting for approval. It'll unlock once approved."
                return false

            @unknown default:
                return false
            }
        } catch {
            purchaseError = error.localizedDescription
            return false
        }
    }

    /// Re-download what this Apple ID owns. Free, and required by App Review.
    func restore() async {
        do {
            try await AppStore.sync()
        } catch {
            purchaseError = error.localizedDescription
        }
        await refreshEntitlements()
    }

    /// Collect current entitlements and hand their signed forms to the server.
    func refreshEntitlements() async {
        var owned: Set<String> = []
        var signed: [String] = []

        for await entitlement in Transaction.currentEntitlements {
            guard case .verified(let transaction) = entitlement else { continue }
            guard transaction.revocationDate == nil else { continue }
            owned.insert(transaction.productID)
            // The signed form lives on the verification wrapper, and it is what
            // the server re-checks against Apple's certificate chain.
            signed.append(entitlement.jwsRepresentation)
        }

        ownedProductIDs = owned
        await onEntitlementsChanged?(signed)
    }
}
