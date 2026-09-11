# SOPHIA

> **SOPHIA**: **S**ophisticated **O**pen **P**latform, **H**ighly **I**ntegrated **A**pplication.  
> An autonomous multimodal personal AI assistant natively integrated into macOS with Dynamic Island notch visualization, dual-world execution (Host Mac + Isolated UTM Virtual Machines), and Google Cloud Gemini Live intelligence.

---

## Architecture Overview

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                                   SOPHIA CLIENT & UI                                                    |
|                                                                                                                         |
|  +--------------------------------------------------+        +-------------------------------------------------------+  |
|  |     macOS Dynamic Island Floating Notch Overlay  |        |             Always-Listening Wake Word Engine         |  |
|  |     - Native Swift/AppKit borderless notch pill  |        |             - Local "Sophia" spotter (zero latency)   |  |
|  |     - Smooth notch expansion & wave visualization|        |             - Natural chime & vocal acknowledgments   |  |
|  |     - Quick toggles: Mic, Camera, Mute, Status   |        |             - Computer-triggered synthetic test mode  |  |
|  +--------------------------------------------------+        +-------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------------------+
                                                                 |
                                                                 v
+-------------------------------------------------------------------------------------------------------------------------+
|                                                   SOPHIA CORE RUNTIME                                                   |
|                                                                                                                         |
|  +---------------------------+  +-------------------------------+  +-----------------------------+  +----------------+  |
|  |   Gemini Live Voice &     |  |     Perception & Vision       |  |  Context & Semantic Memory  |  | Self-Testing & |  |
|  |   Multimodal Agent Loop   |  |  - Screen stream / OCR        |  |  - Local vector store       |  | Recursive Loop |  |
|  |  - Bidirectional WebSockets|  |  - Webcam object / face       |  |  - System-wide file indexer |  | - Auto-verifier|  |
|  |  - Charming female persona|  |  - Emotion & context detector |  |  - SQLite metadata graph    |  | - Self-healing |  |
|  +---------------------------+  +-------------------------------+  +-----------------------------+  +----------------+  |
|                                                                |                                                        |
|                                                                v                                                        |
|                                            +--------------------------------------+                                     |
|                                            |    Dual-World Execution Dispatcher   |                                     |
|                                            +--------------------------------------+                                     |
+-------------------------------------------------------------------------------------------------------------------------+
                                    |                                                  |
                    [Host / Interactive Tasks]                         [Isolated / Background / Heavy Tasks]
                                    |                                                  |
                                    v                                                  v
+-------------------------------------------------------+  +-----------------------------------------------------------+
|                   HOST WORLD (macOS)                  |  |             BACKGROUND VIRTUAL WORLD (UTM VMs)            |
|                                                       |  |                                                           |
| - Root / Terminal command execution (zsh)             |  | - UTM headless VM controller (`utmctl` / QEMU)           |
| - System Accessibility & Window Management            |  | - Guest OS instances (Kali Linux, Windows, macOS)         |
| - App Control (Blender, Spotify, Safari, Terminal)    |  | - Background 3D rendering, security tools, long builds    |
| - Local communication bridges (WhatsApp, Mail, etc.)  |  | - Zero screen interruption while user works / watches vid |
+-------------------------------------------------------+  +-----------------------------------------------------------+
```

---

## Key Features

1. **Native Dynamic Island Notch UI (`SophiaNotchOverlay`)**:
   - Written in pure Swift 6.2 and AppKit/SwiftUI.
   - Anchors flush against the MacBook Pro camera notch.
   - Non-activating panel that floats above all apps, full-screen spaces, and video players.
   - Fluid spring animations expanding from notch to pill, showing live waveforms, task state, and interactive controls (mic mute, vision toggles).

2. **Dual-World Execution**:
   - **Host Mac**: Native application control, AppleScript, volume/media control, terminal commands, and headless Blender rendering.
   - **Background UTM Virtual Machines**: Automatically routes long-running, resource-intensive, or security workloads (e.g. ethical hacking tools, code compilation, 3D assets) to headless VMs via `utmctl`. Your main screen remains 100% free.

3. **Perception Engine**:
   - **Screen Vision**: Real-time screenshot capture and active window/app analysis via Gemini Vision.
   - **Camera Vision**: Physical webcam frame processing for object identification and user expression/emotional context.

4. **Deep Filesystem Semantic Memory**:
   - Embedded SQLite FTS5 database (`~/.sophia/cache/file_index.db`) providing instant (< 5ms) full-text search across documents, source code, scripts, and media.

5. **Autonomous Recursive Self-Testing & Self-Healing**:
   - Dual execution paths:
     - **Manual mode**: Natural voice and wake-word trigger ("Sophia").
     - **Computer-triggered synthetic mode**: Injects programmatic wake events, mock commands, and verifies every subsystem autonomously before real-world tasks.
   - Auto-healing loop that diagnoses failures and recovers automatically.

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Saaransh2011/Sophia.git
cd Sophia

# Run setup (creates venv and installs dependencies)
make setup

# Build the native Swift Dynamic Island overlay
make build-ui
```

### 2. Run Autonomous Subsystem Verification

```bash
# Run the automated self-testing suite
make test

# Or run with recursive self-healing enabled
make heal
```

### 3. Bootstrap Google Cloud Platform

Connect Sophia to your Google Cloud project with billing enabled:

```bash
./.venv/bin/sophia setup-gcp --project-id <YOUR_GCP_PROJECT_ID>
```
*This command automatically verifies billing, enables Vertex AI, Gemini Multimodal Live, Cloud Speech, and Cloud Vision APIs, and configures the service account.*

### 4. Start Sophia Assistant Daemon

```bash
make run
# Or directly:
./.venv/bin/sophia start
```
*Say **"Sophia"** to activate her anytime from anywhere on your Mac!*

---

## Docker & Container Deployment

To run Sophia in a containerized environment (for testing, cloud hosting, or serverless VM dispatchers):

```bash
# Build Docker image
make docker-build

# Run self-test inside container
make docker-run

# Or run with Docker Compose
docker compose up --build
```

---

## GitHub Repository Setup

To preserve and sync your code to your GitHub account (`Saaransh2011`):

```bash
# 1. Create a new repository on GitHub named 'Sophia'
# 2. Link your local repository:
git remote add origin https://github.com/Saaransh2011/Sophia.git

# 3. Push your code to GitHub:
git branch -M main
git push -u origin main
```

---

## License

MIT License. Designed and engineered for autonomous personal assistance.
