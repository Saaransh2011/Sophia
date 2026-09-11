import SwiftUI

public struct NotchIslandShape: Shape {
    var bottomRadius: CGFloat = 18

    public func path(in rect: CGRect) -> Path {
        var path = Path()
        // Top-left origin: completely flat along the top edge of screen
        path.move(to: CGPoint(x: rect.minX, y: rect.minY))
        // Top edge flush with display bezel
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        // Right edge down to bottom-right corner
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - bottomRadius))
        // Bottom-right smooth arc
        path.addArc(
            center: CGPoint(x: rect.maxX - bottomRadius, y: rect.maxY - bottomRadius),
            radius: bottomRadius,
            startAngle: .degrees(0),
            endAngle: .degrees(90),
            clockwise: false
        )
        // Bottom edge
        path.addLine(to: CGPoint(x: rect.minX + bottomRadius, y: rect.maxY))
        // Bottom-left smooth arc
        path.addArc(
            center: CGPoint(x: rect.minX + bottomRadius, y: rect.maxY - bottomRadius),
            radius: bottomRadius,
            startAngle: .degrees(90),
            endAngle: .degrees(180),
            clockwise: false
        )
        // Left edge up to top-left
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY))
        path.closeSubpath()
        return path
    }
}

public struct NotchBorderShape: Shape {
    var bottomRadius: CGFloat = 18

    public func path(in rect: CGRect) -> Path {
        var path = Path()
        // Trace left side, bottom-left curve, bottom side, bottom-right curve, right side
        // Leaving the top edge unstroked so it seamlessly merges with the physical MacBook notch & bezel
        path.move(to: CGPoint(x: rect.minX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY - bottomRadius))
        path.addArc(
            center: CGPoint(x: rect.minX + bottomRadius, y: rect.maxY - bottomRadius),
            radius: bottomRadius,
            startAngle: .degrees(180),
            endAngle: .degrees(90),
            clockwise: true
        )
        path.addLine(to: CGPoint(x: rect.maxX - bottomRadius, y: rect.maxY))
        path.addArc(
            center: CGPoint(x: rect.maxX - bottomRadius, y: rect.maxY - bottomRadius),
            radius: bottomRadius,
            startAngle: .degrees(90),
            endAngle: .degrees(0),
            clockwise: true
        )
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        return path
    }
}

public struct DynamicIslandView: View {
    @ObservedObject var model: DynamicIslandModel = DynamicIslandModel.shared

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            // Main Top Header Row (Height: 36) - Always visible and clickable
            // Flanked on left and right outside the physical MacBook camera notch dead-zone
            HStack(alignment: .center, spacing: 0) {
                // Left Wing: Always visible left of the MacBook camera notch
                HStack(spacing: 7) {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 8, height: 8)
                        .shadow(color: statusColor.opacity(0.85), radius: 5)

                    Text("SARAH")
                        .font(.system(size: 11.5, weight: .bold, design: .rounded))
                        .foregroundColor(.white)
                        .tracking(1.2)
                }
                .frame(width: 105, alignment: .leading)
                .padding(.leading, 14)

                // Center Spacer: Exact span of the physical MacBook camera notch housing (~190-200pt)
                Spacer(minLength: 190)

                // Right Wing: Always visible right of the MacBook camera notch
                HStack(spacing: 7) {
                    if !model.isExpanded {
                        Text(model.statusText)
                            .font(.system(size: 10.5, weight: .medium))
                            .foregroundColor(.white.opacity(0.75))
                            .lineLimit(1)
                    }

                    WaveformMiniView(state: model.state)
                        .frame(width: 22, height: 12)

                    Image(systemName: model.isExpanded ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                        .font(.system(size: 11))
                        .foregroundColor(.white.opacity(0.65))
                }
                .frame(width: 105, alignment: .trailing)
                .padding(.trailing, 14)
            }
            .frame(height: 36)
            .contentShape(Rectangle())
            .onTapGesture(count: 2) {
                // Double click: unfold and cycle Gemini Live voice persona
                withAnimation(.easeInOut(duration: 0.32)) {
                    model.isExpanded = true
                    let newVoice = model.cycleVoice()
                    model.statusText = "Voice: \(newVoice)"
                }
                IPCServer.shared.broadcastEvent([
                    "event": "voice_changed",
                    "voice": model.currentVoice,
                    "isExpanded": true
                ])
            }
            .onTapGesture(count: 1) {
                // Single click: toggle unfold/fold
                withAnimation(.easeInOut(duration: 0.32)) {
                    model.isExpanded.toggle()
                }
                IPCServer.shared.broadcastEvent([
                    "event": "island_toggled",
                    "isExpanded": model.isExpanded
                ])
            }

            // Expanded Lower Panel: Appears below the camera notch when unfolded / active
            if model.isExpanded {
                VStack(alignment: .leading, spacing: 10) {
                    Divider().background(Color.white.opacity(0.18))

                    // Status & Full Transcript Display (Scrollable so text never clips)
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: taskIcon)
                            .font(.system(size: 15))
                            .foregroundColor(statusColor)
                            .frame(width: 26, height: 26)
                            .background(statusColor.opacity(0.16))
                            .clipShape(Circle())

                        VStack(alignment: .leading, spacing: 4) {
                            Text(model.statusText)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(.white)
                                .fixedSize(horizontal: false, vertical: true)

                            if !model.transcript.isEmpty && model.transcript != model.statusText {
                                ScrollView(.vertical, showsIndicators: true) {
                                    Text(model.transcript)
                                        .font(.system(size: 11, weight: .regular))
                                        .foregroundColor(.white.opacity(0.88))
                                        .lineSpacing(2)
                                        .fixedSize(horizontal: false, vertical: true)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                .frame(maxHeight: 78)
                            }
                        }
                    }

                    Divider().background(Color.white.opacity(0.12))

                    // Bottom Interactive Control Panel
                    HStack(spacing: 8) {
                        // Voice Switcher button
                        Button(action: {
                            let newVoice = model.cycleVoice()
                            model.statusText = "Voice: \(newVoice)"
                            IPCServer.shared.broadcastEvent([
                                "event": "voice_changed",
                                "voice": newVoice,
                                "isExpanded": true
                            ])
                        }) {
                            HStack(spacing: 4) {
                                Image(systemName: "sparkle")
                                    .font(.system(size: 9))
                                Text("Gemini Live • \(model.currentVoice)")
                                    .font(.system(size: 9.5, weight: .medium))
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.white.opacity(0.12))
                            .foregroundColor(.white.opacity(0.9))
                            .cornerRadius(5)
                        }
                        .buttonStyle(.plain)

                        Spacer()

                        // Interactive Mute Toggle Button
                        Button(action: {
                            model.isMicMuted.toggle()
                            IPCServer.shared.broadcastEvent(["event": "mic_toggled", "isMuted": model.isMicMuted])
                        }) {
                            HStack(spacing: 4) {
                                Image(systemName: model.isMicMuted ? "mic.slash.fill" : "mic.fill")
                                Text(model.isMicMuted ? "Muted" : "Active")
                                    .font(.system(size: 10, weight: .medium))
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(model.isMicMuted ? Color.red.opacity(0.25) : Color.white.opacity(0.12))
                            .foregroundColor(model.isMicMuted ? .red : .white)
                            .cornerRadius(6)
                        }
                        .buttonStyle(.plain)

                        // Interactive Vision Toggle Button
                        Button(action: {
                            model.isScreenVisionActive.toggle()
                            IPCServer.shared.broadcastEvent(["event": "vision_toggled", "isActive": model.isScreenVisionActive])
                        }) {
                            HStack(spacing: 4) {
                                Image(systemName: model.isScreenVisionActive ? "eye.fill" : "eye.slash.fill")
                                Text("Vision")
                                    .font(.system(size: 10, weight: .medium))
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(model.isScreenVisionActive ? Color.cyan.opacity(0.25) : Color.white.opacity(0.12))
                            .foregroundColor(model.isScreenVisionActive ? .cyan : .gray)
                            .cornerRadius(6)
                        }
                        .buttonStyle(.plain)

                        // Dismiss / Collapse Button
                        Button(action: {
                            withAnimation(.easeInOut(duration: 0.32)) {
                                model.setIdle()
                            }
                            IPCServer.shared.broadcastEvent(["event": "dismiss_clicked"])
                        }) {
                            Text("Close")
                                .font(.system(size: 10, weight: .medium))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.white.opacity(0.12))
                                .foregroundColor(.gray)
                                .cornerRadius(6)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 12)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(
            NotchIslandShape(bottomRadius: model.isExpanded ? 22 : 18)
                .fill(Color.black.opacity(0.97))
                .overlay(
                    NotchBorderShape(bottomRadius: model.isExpanded ? 22 : 18)
                        .stroke(statusColor.opacity(0.4), lineWidth: 1)
                )
                .shadow(color: Color.black.opacity(0.55), radius: 14, x: 0, y: 7)
        )
        .animation(.easeInOut(duration: 0.32), value: model.isExpanded)
        .animation(.easeInOut(duration: 0.2), value: model.state)
        .ignoresSafeArea()
    }

    private var statusColor: Color {
        switch model.state {
        case .idle:
            return Color(white: 0.45)
        case .listening:
            return Color.cyan
        case .thinking:
            return Color.purple
        case .speaking:
            return Color.green
        case .executing:
            return Color.orange
        case .error:
            return Color.red
        }
    }

    private var taskIcon: String {
        switch model.state {
        case .idle: return "sparkles"
        case .listening: return "waveform"
        case .thinking: return "brain.head.profile"
        case .speaking: return "speaker.wave.2.fill"
        case .executing: return "gearshape.arrow.triangle.2.circlepath"
        case .error: return "exclamationmark.triangle.fill"
        }
    }
}

struct WaveformMiniView: View {
    let state: AssistantState
    @State private var phase: CGFloat = 0.0

    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<4) { i in
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(barColor)
                    .frame(width: 2.5, height: barHeight(for: i))
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true)) {
                phase = 1.0
            }
        }
    }

    private var barColor: Color {
        state == .listening ? .cyan : (state == .speaking ? .green : .white.opacity(0.4))
    }

    private func barHeight(for index: Int) -> CGFloat {
        if state == .idle { return 3.0 }
        let heights: [CGFloat] = [5, 11, 8, 13]
        return heights[(index + Int(phase * 2)) % heights.count]
    }
}
