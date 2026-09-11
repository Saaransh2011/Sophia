import AppKit
import SwiftUI
import Combine

public class NotchWindow: NSPanel {
    private var cancellables = Set<AnyCancellable>()

    public init() {
        super.init(
            contentRect: NSRect(x: 0, y: 0, width: 420, height: 36),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        self.level = .popUpMenu
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        self.isOpaque = false
        self.backgroundColor = .clear
        self.hasShadow = false
        self.isMovableByWindowBackground = false
        self.titleVisibility = .hidden
        self.titlebarAppearsTransparent = true

        let hostingView = NSHostingView(rootView: DynamicIslandView())
        self.contentView = hostingView

        self.updatePosition(expanded: false, animated: false)

        DynamicIslandModel.shared.$isExpanded
            .receive(on: DispatchQueue.main)
            .sink { [weak self] expanded in
                self?.updatePosition(expanded: expanded, animated: true)
            }
            .store(in: &cancellables)
    }

    public func updatePosition(expanded: Bool, animated: Bool) {
        guard let screen = NSScreen.main else { return }

        let screenFrame = screen.frame
        let targetWidth: CGFloat = expanded ? 520 : 420
        let targetHeight: CGFloat = expanded ? 200 : 36

        // Calculate center X (directly aligned with MacBook notch/camera)
        let targetX = screenFrame.origin.x + (screenFrame.width - targetWidth) / 2.0
        // Top edge flush with screen top
        let targetY = screenFrame.origin.y + screenFrame.height - targetHeight

        let targetFrame = NSRect(x: targetX, y: targetY, width: targetWidth, height: targetHeight)

        if animated {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.32
                context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
                self.animator().setFrame(targetFrame, display: true)
            }
        } else {
            self.setFrame(targetFrame, display: true)
        }
    }
}
