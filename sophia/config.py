"""
Sophia System Configuration
Central settings for Google Cloud, Audio/Voice, UTM Virtualization, Dynamic Island UI, and Filesystem Indexing.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
SOPHIA_HOME = Path(os.environ.get("SOPHIA_HOME", Path.home() / ".sophia"))
SOPHIA_HOME.mkdir(parents=True, exist_ok=True)

CREDENTIALS_DIR = SOPHIA_HOME / "credentials"
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = SOPHIA_HOME / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = SOPHIA_HOME / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SOCKET_PATH = SOPHIA_HOME / "sophia_notch.sock"


class GCPConfig(BaseModel):
    project_id: str = Field(default=os.environ.get("GCP_PROJECT_ID", ""))
    project_number: str = Field(default=os.environ.get("GCP_PROJECT_NUMBER", ""))
    region: str = Field(default="us-central1")
    credentials_path: str = Field(
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", str(CREDENTIALS_DIR / "service_account.json"))
    )
    gemini_model: str = Field(default="gemini-2.5-flash")
    live_model: str = Field(default="gemini-2.0-flash-exp")
    voice_name: str = Field(default="Aoede")  # Charming, natural, confident female tone


class AudioConfig(BaseModel):
    wake_word: str = "sophia"
    sample_rate: int = 16000
    chunk_size: int = 512
    channels: int = 1
    input_device_index: int | None = None
    output_device_index: int | None = None
    vad_threshold: float = 0.5
    wake_word_sensitivity: float = 0.7


class UTMConfig(BaseModel):
    utmctl_path: str = "/Applications/UTM.app/Contents/MacOS/utmctl"
    default_headless: bool = True
    default_linux_vm: str = "Kali"
    default_windows_vm: str = "Windows"
    default_macos_vm: str = "macOS"
    shared_exchange_dir: str = str(SOPHIA_HOME / "vm_exchange")


class UIConfig(BaseModel):
    socket_path: str = str(SOCKET_PATH)
    island_width_collapsed: float = 160.0
    island_height_collapsed: float = 34.0
    island_width_expanded: float = 380.0
    island_height_expanded: float = 120.0
    notch_corner_radius: float = 18.0
    show_waveform: bool = True


class SophiaConfig(BaseModel):
    gcp: GCPConfig = Field(default_factory=GCPConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    utm: UTMConfig = Field(default_factory=UTMConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    base_dir: str = str(BASE_DIR)
    sophia_home: str = str(SOPHIA_HOME)


# Global singleton
config = SophiaConfig()
