import SwiftUI

public struct DynamicIslandView: View {
    @ObservedObject var model: DynamicIslandModel = DynamicIslandModel.shared

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            // Main Island Pill Container
            VStack(spacing: 10) {
                // Top Header Row (Always visible & clickable to toggle fold/unfold)
                HStack(alignment: .center, spacing: 10) {
                    // Left: Sophia Branding & Status Dot
                    HStack(spacing: 7) {
                        Circle()
                            .fill(statusColor)
                            .frame(width: 9, height: 9)
                            .shadow(color: statusColor.opacity(0.8), radius: 5)

                        Text("SARAH")
                            .font(.system(size: 12, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                            .tracking(1.1)
                    }

                    Spacer()

                    // Center: Status text when collapsed
                    if !model.isExpanded {
                        Text(model.statusText)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(.white.opacity(0.7))
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }

                    Spacer()

                    // Right: Waveform & Quick Icons
                    HStack(spacing: 8) {
                        WaveformMiniView(state: model.state)
                            .frame(width: 22, height: 12)

                        // Chevron indicating fold/unfold state
                        Image(systemName: model.isExpanded ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
                .padding(.horizontal, 14)
                .frame(height: 36)
                .contentShape(Rectangle())
                .onTapGesture(count: 2) {
                    // Double click: open up & expand, and switch agent voice persona!
                    withAnimation(.spring(response: 0.36, dampingFraction: 0.82)) {
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
                    withAnimation(.spring(response: 0.36, dampingFraction: 0.82)) {
                        model.isExpanded.toggle()
                    }
                    IPCServer.shared.broadcastEvent([
                        "event": "island_toggled",
                        "isExpanded": model.isExpanded
                    ])
                }

                // Expanded / Unfolded Section with all controls and full text
                if model.isExpanded {
                    VStack(alignment: .leading, spacing: 12) {
                        Divider().background(Color.white.opacity(0.18))

                        // Status & Full Transcript Display (Scrollable so text never clips)
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: taskIcon)
                                .font(.system(size: 16))
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
                                    .frame(maxHeight: 75)
                                }
                            }
                        }

                        Divider().background(Color.white.opacity(0.12))

                        // Bottom Control Panel
                        HStack(spacing: 10) {
                            // Model & Voice Tag (Clickable to switch voice)
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
                                        .font(.system(size: 9, weight: .medium))
                                }
                                .padding(.horizontal, 7)
                                .padding(.vertical, 3)
                                .background(Color.white.opacity(0.12))
                                .foregroundColor(.white.opacity(0.88))
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
                                withAnimation(.spring(response: 0.32, dampingFraction: 0.82)) {
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
                    .padding(.horizontal, 14)
                    .padding(.bottom, 12)
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(Color.black.opacity(0.96))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(statusColor.opacity(0.4), lineWidth: 1)
                    )
                    .shadow(color: Color.black.opacity(0.55), radius: 14, x: 0, y: 7)
            )
        }
        .animation(.spring(response: 0.36, dampingFraction: 0.82), value: model.isExpanded)
        .animation(.easeInOut(duration: 0.2), value: model.state)
        .padding(.horizontal, 4)
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
