import Foundation

public class IPCServer {
    public static let shared = IPCServer()

    private var serverSource: DispatchSourceRead?
    private var clientFileDescriptor: Int32 = -1
    private let socketPath: String

    private init() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let dir = "\(home)/.sophia"
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        self.socketPath = "\(dir)/sophia_notch.sock"
    }

    public func start() {
        unlink(socketPath)

        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else {
            print("[IPC] Error creating unix socket")
            return
        }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)

        withUnsafeMutablePointer(to: &addr.sun_path.0) { ptr in
            socketPath.withCString { cstr in
                _ = strncpy(ptr, cstr, 103)
            }
        }

        let addrLen = socklen_t(MemoryLayout<sockaddr_un>.size)
        let bindResult = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                bind(fd, $0, addrLen)
            }
        }

        guard bindResult == 0 else {
            print("[IPC] Error binding socket: \(errno)")
            close(fd)
            return
        }

        listen(fd, 5)
        print("[IPC] Sophia Dynamic Island listening on \(socketPath)")

        let source = DispatchSource.makeReadSource(fileDescriptor: fd, queue: DispatchQueue.global(qos: .userInitiated))
        source.setEventHandler { [weak self] in
            var clientAddr = sockaddr_un()
            var clientAddrLen = socklen_t(MemoryLayout<sockaddr_un>.size)
            let clientFd = withUnsafeMutablePointer(to: &clientAddr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    accept(fd, $0, &clientAddrLen)
                }
            }
            if clientFd >= 0 {
                self?.handleClient(clientFd)
            }
        }
        source.resume()
        self.serverSource = source
    }

    private func handleClient(_ clientFd: Int32) {
        self.clientFileDescriptor = clientFd
        let clientSource = DispatchSource.makeReadSource(fileDescriptor: clientFd, queue: DispatchQueue.global(qos: .userInitiated))
        var buffer = Data()

        clientSource.setEventHandler { [weak self] in
            var temp = [UInt8](repeating: 0, count: 2048)
            let bytesRead = read(clientFd, &temp, temp.count)
            if bytesRead <= 0 {
                clientSource.cancel()
                close(clientFd)
                if self?.clientFileDescriptor == clientFd {
                    self?.clientFileDescriptor = -1
                }
                return
            }

            buffer.append(temp, count: bytesRead)
            while let newlineIndex = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                let lineData = buffer.subdata(in: 0..<newlineIndex)
                buffer.removeSubrange(0...newlineIndex)
                if let lineStr = String(data: lineData, encoding: .utf8) {
                    self?.processMessage(lineStr)
                }
            }
        }

        clientSource.setCancelHandler {
            close(clientFd)
        }
        clientSource.resume()
    }

    private func processMessage(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let action = json["action"] as? String else {
            return
        }

        DispatchQueue.main.async {
            let model = DynamicIslandModel.shared
            switch action {
            case "set_state":
                if let stateStr = json["state"] as? String,
                   let state = AssistantState(rawValue: stateStr) {
                    model.state = state
                    if state != .idle {
                        model.isExpanded = true
                    } else {
                        model.isExpanded = false
                    }
                }
            case "set_status":
                if let text = json["text"] as? String {
                    model.statusText = text
                }
            case "set_transcript":
                if let text = json["text"] as? String {
                    model.transcript = text
                }
            case "expand":
                model.isExpanded = true
            case "collapse":
                model.isExpanded = false
            default:
                break
            }
        }
    }

    public func broadcastEvent(_ eventDict: [String: Any]) {
        guard clientFileDescriptor >= 0,
              let data = try? JSONSerialization.data(withJSONObject: eventDict),
              var line = String(data: data, encoding: .utf8) else {
            return
        }
        line.append("\n")
        line.withCString { ptr in
            _ = write(clientFileDescriptor, ptr, strlen(ptr))
        }
    }
}
