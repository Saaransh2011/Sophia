import AppKit
import Foundation

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NotchWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        IPCServer.shared.start()

        let win = NotchWindow()
        win.makeKeyAndOrderFront(nil)
        self.window = win

        print("[Sophia] Dynamic Island Notch UI initialized.")
    }
}

let delegate = AppDelegate()
let app = NSApplication.shared
app.delegate = delegate
app.run()
