import SwiftUI
import Combine

public enum AssistantState: String, Codable {
    case idle
    case listening
    case thinking
    case speaking
    case executing
    case error
}

public class DynamicIslandModel: ObservableObject {
    public static let shared = DynamicIslandModel()

    @Published public var state: AssistantState = .idle
    @Published public var isExpanded: Bool = false
    @Published public var title: String = "Sophia"
    @Published public var statusText: String = "Ready"
    @Published public var transcript: String = ""
    @Published public var isMicMuted: Bool = false
    @Published public var isScreenVisionActive: Bool = true
    @Published public var audioLevel: CGFloat = 0.3

    public func setListening() {
        self.state = .listening
        self.statusText = "Listening..."
        self.isExpanded = true
    }

    public func setThinking(task: String = "Thinking...") {
        self.state = .thinking
        self.statusText = task
        self.isExpanded = true
    }

    public func setSpeaking(response: String) {
        self.state = .speaking
        self.statusText = response
        self.transcript = response
        self.isExpanded = true
    }

    public func setIdle() {
        self.state = .idle
        self.statusText = "Ready"
        // Collapse after brief delay or immediately
        self.isExpanded = false
    }
}
