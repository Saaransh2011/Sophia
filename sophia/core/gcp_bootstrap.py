"""
Sophia GCP Bootstrap
Automates Google Cloud project verification, billing checks, API enablement,
service account creation, and credential setup for Sophia.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from sophia.config import config, CREDENTIALS_DIR, SOPHIA_HOME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SophiaGCPBootstrap")

REQUIRED_APIS = [
    "aiplatform.googleapis.com",
    "generativelanguage.googleapis.com",
    "speech.googleapis.com",
    "texttospeech.googleapis.com",
    "vision.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
]

SERVICE_ACCOUNT_NAME = "sophia-assistant"
SERVICE_ACCOUNT_DISPLAY = "Sophia AI Assistant Service Account"

SERVICE_ACCOUNT_ROLES = [
    "roles/aiplatform.user",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/speech.admin",
]


class GCPBootstrapper:
    def __init__(self, project_id: Optional[str] = None):
        self.gcloud_path = self._find_gcloud()
        self.project_id = project_id or config.gcp.project_id
        self.credentials_file = CREDENTIALS_DIR / "service_account.json"

    def _find_gcloud(self) -> str:
        # Check standard path from environment or common mac locations
        candidate = "/Users/anupam/Downloads/google-cloud-sdk/bin/gcloud"
        if os.path.exists(candidate):
            return candidate
        found = shutil.which("gcloud")
        if found:
            return found
        raise RuntimeError("gcloud CLI not found. Please install Google Cloud SDK or configure PATH.")

    def run_gcloud(self, args: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        cmd = [self.gcloud_path] + args
        logger.debug("Executing: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=capture_output, text=True)
        return result

    def get_current_account(self) -> Optional[str]:
        res = self.run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return None

    def list_projects(self) -> List[Dict[str, str]]:
        res = self.run_gcloud(["projects", "list", "--format=json"])
        if res.returncode == 0 and res.stdout.strip():
            try:
                return json.loads(res.stdout)
            except Exception as e:
                logger.warning("Failed to parse projects json: %s", e)
        return []

    def set_project(self, project_id: str) -> bool:
        logger.info("Setting active GCP project to: %s", project_id)
        res = self.run_gcloud(["config", "set", "project", project_id])
        if res.returncode == 0:
            self.project_id = project_id
            config.gcp.project_id = project_id
            return True
        logger.error("Failed to set project: %s", res.stderr)
        return False

    def verify_billing(self) -> Dict[str, Any]:
        if not self.project_id:
            return {"enabled": False, "error": "No project ID set"}
        res = self.run_gcloud(["beta", "billing", "projects", "describe", self.project_id, "--format=json"])
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                return {"enabled": data.get("billingEnabled", False), "billingAccountName": data.get("billingAccountName")}
            except Exception as e:
                return {"enabled": False, "error": str(e)}
        return {"enabled": False, "error": res.stderr.strip()}

    def enable_apis(self) -> bool:
        if not self.project_id:
            logger.error("No project ID specified for enabling APIs.")
            return False
        logger.info("Enabling required APIs: %s", ", ".join(REQUIRED_APIS))
        cmd = ["services", "enable"] + REQUIRED_APIS + ["--project", self.project_id]
        res = self.run_gcloud(cmd)
        if res.returncode == 0:
            logger.info("Successfully enabled all required GCP APIs.")
            return True
        logger.error("Failed to enable some APIs: %s", res.stderr)
        return False

    def ensure_service_account(self) -> Optional[Path]:
        if not self.project_id:
            return None

        sa_email = f"{SERVICE_ACCOUNT_NAME}@{self.project_id}.iam.gserviceaccount.com"
        logger.info("Ensuring service account exists: %s", sa_email)

        # Check if SA already exists
        res = self.run_gcloud([
            "iam", "service-accounts", "describe", sa_email,
            "--project", self.project_id, "--format=value(email)"
        ])

        if res.returncode != 0:
            logger.info("Creating service account: %s", SERVICE_ACCOUNT_NAME)
            create_res = self.run_gcloud([
                "iam", "service-accounts", "create", SERVICE_ACCOUNT_NAME,
                "--display-name", SERVICE_ACCOUNT_DISPLAY,
                "--project", self.project_id
            ])
            if create_res.returncode != 0:
                logger.error("Failed to create service account: %s", create_res.stderr)
                return None

        # Grant roles
        for role in SERVICE_ACCOUNT_ROLES:
            logger.info("Granting role %s to %s", role, sa_email)
            self.run_gcloud([
                "projects", "add-iam-policy-binding", self.project_id,
                f"--member=serviceAccount:{sa_email}",
                f"--role={role}",
                "--condition=None"
            ])

        # Create key if not already cached
        if not self.credentials_file.exists():
            logger.info("Generating new service account key -> %s", self.credentials_file)
            key_res = self.run_gcloud([
                "iam", "service-accounts", "keys", "create", str(self.credentials_file),
                f"--iam-account={sa_email}",
                "--project", self.project_id
            ])
            if key_res.returncode != 0:
                logger.error("Failed to create service account key: %s", key_res.stderr)
                return None
        else:
            logger.info("Using existing credentials file: %s", self.credentials_file)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.credentials_file)
        config.gcp.credentials_path = str(self.credentials_file)
        return self.credentials_file

    def test_gemini_connection(self) -> bool:
        logger.info("Testing Gemini connection via google-genai SDK...")
        try:
            from google import genai
            client = genai.Client()
            response = client.models.generate_content(
                model=config.gcp.gemini_model,
                contents="You are Sophia, say 'Sophia is online and ready, sir.'"
            )
            logger.info("Gemini Test Response: %s", response.text.strip())
            return True
        except Exception as e:
            logger.error("Gemini connection test failed: %s", e)
            return False


if __name__ == "__main__":
    import sys

    proj = sys.argv[1] if len(sys.argv) > 1 else None
    bootstrapper = GCPBootstrapper(proj)
    account = bootstrapper.get_current_account()
    print(f"Active Account: {account}")

    projects = bootstrapper.list_projects()
    print(f"Available Projects: {[p.get('projectId') for p in projects]}")
