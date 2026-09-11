// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SophiaNotchOverlay",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "SophiaNotchOverlay", targets: ["SophiaNotchOverlay"])
    ],
    targets: [
        .executableTarget(
            name: "SophiaNotchOverlay",
            path: "Sources"
        )
    ]
)
