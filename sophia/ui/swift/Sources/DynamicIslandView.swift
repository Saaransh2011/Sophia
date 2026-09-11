import SwiftUI

public struct DynamicIslandView: View {
    @ObservedObject var model: DynamicIslandModel = DynamicIslandModel.shared

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            // Main Island Pill
            VStack(spacing: 8) {
                // Top Header Row (Always visible)
                HStack(alignment: .center, spacing: 12) {
                    // Left: Sophia Branding & Pulsing Aura
                    HStack(spacing: 8) {
                        Circle()
                            .fill(statusColor)
                            .frame(width: 10, height: 10)
                            .shadow(color: statusColor.opacity(0.8), radius: 6)

                        Text("SOPHIA")
                            .font(.system(size: 13, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                            .tracking(1.2)
                    }

                    Spacer()

                    // Center / Notch area spacer
                    if !model.isExpanded {
                        Text(model.statusText)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(.gray)
                            .lineLimit(1)
                    }

                    Spacer()

                    // Right: Audio waveform indicator & quick mute toggle
                    HStack(spacing: 8) {
                        WaveformMiniView(state: model.state)
                            .frame(width: 24, height: 14)

                        Button(action: {
                            model.isMicMuted.toggle()
                            IPCServer.shared.broadcastEvent(["event": "mic_toggled", "isMuted": model.isMicMuted])
                        }) {
                            Image(systemName: model.isMicMuted ? "mic.slash.fill" : "mic.fill")
                                .font(.system(size: 11))
                                .foregroundColor(model.isMicMuted ? .red : .gray)
                        }
                        .buttonStyle(.plain)

                        Button(action: {
                            model.isScreenVisionActive.toggle()
                            IPCServer.shared.broadcastEvent(["event": "vision_toggled", "isActive": model.isScreenVisionActive])
                        }) {
                            Image(systemName: model.isScreenVisionActive ? "eye.fill" : "eye.slash.fill")
                                .font(.system(size: 11))
                                .foregroundColor(model.isScreenVisionActive ? .cyan : .gray)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
                .frame(height: 34)

                // Expanded Section (When active / speaking / executing)
                if model.isExpanded {
                    VStack(alignment: .leading, spacing: 10) {
                        Divider().background(Color.white.opacity(0.15))

                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: taskIcon)
                                .font(.system(size: 18))
                                .foregroundColor(statusColor)
                                .frame(width: 28, height: 28)
                                .background(statusColor.opacity(0.15))
                                .clipShape(Circle())

                            VStack(alignment: .leading, spacing: 3) {
                                Text(model.statusText)
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundColor(.white)

                                if !model.transcript.isEmpty && model.transcript != model.statusText {
                                    Text(model.transcript)
                                        .font(.system(size: 12, weight: .regular))
                                        .foregroundColor(.white.opacity(0.8))
                                        .lineLimit(2)
                                }
                            }
                            Spacer()
                        }

                        // Bottom Actions
                        HStack {
                            Text(model.state.rawValue.uppercased())
                                .font(.system(size: 9, weight: .bold))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(statusColor.opacity(0.2))
                                .foregroundColor(statusColor)
                                .cornerRadius(6)

                            Spacer()

                            Button("Dismiss") {
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                                    model.setIdle()
                                }
                            }
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(.gray)
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 12)
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(Color.black.opacity(0.94))
                    .overlay(
                        RoundedRectangle(cornerRadius: 20, style: .continuous)
                            .stroke(statusColor.opacity(0.4), lineWidth: 1)
                    )
                    .shadow(color: Color.black.opacity(0.6), radius: 16, x: 0, y: 8)
            )
        }
        .animation(.spring(response: 0.38, dampingFraction: 0.82), value: model.isExpanded)
        .animation(.easeInOut(duration: 0.2), value: model.state)
        .padding(.horizontal, 4)
    }

    private var statusColor: Color {
        switch model.state {
        case .idle:
            return Color(white: 0.4)
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
                RoundedRectangle(cornerRadius: 2)
                    .fill(barColor)
                    .frame(width: 3, height: barHeight(for: i))
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true)) {
                phase = 1.0
            }
        }
    }

    private var barColor: Color {
        state == .listening ? .cyan : (state == .speaking ? .green : .gray.opacity(0.5))
    }

    private func barHeight(for index: Int) -> CGFloat {
        if state == .idle { return 4.0 }
        let heights: [CGFloat] = [6, 12, 9, 14]
        return heights[(index + Int(phase * 2)) % heights.count]
    }
}
