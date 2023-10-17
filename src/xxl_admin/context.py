from pathlib import Path
from typer import get_app_dir
from typing import List, Dict

from .settings import XxlSettings
from .client import XxlAdminClient


class XxlContext(object):
    SETTINGS_FILENAME = "xxl.json"

    def __init__(self, settings_file: str = None) -> None:
        if not settings_file:
            settings_file = Path(get_app_dir("XXL")).parent / self.SETTINGS_FILENAME
        else:
            settings_file = (
                Path(settings_file) if settings_file.endswith(".json") else Path(settings_file) / self.SETTINGS_FILENAME
            )

        self.client_pool = {}
        self.settings: XxlSettings = None
        self._location: Path = settings_file
        self._settings_file_created = settings_file.exists()
        self._last_updated_at = self._location.stat().st_mtime or 0

    def load(self):
        if self.settings:
            return
        if not self._settings_file_created:
            self.settings = XxlSettings()
        else:
            self.settings = XxlSettings.model_validate_json(self._location.read_text())

    def save(self):
        # been changed since last loaded
        mtime = self._location.stat().st_mtime
        if mtime and mtime > self._last_updated_at:
            return
        self._location.write_text(XxlSettings.model_dump_json(self.settings, exclude_unset=True, indent=4))
        self._settings_file_created = True

    def get_clients(self, all_mode: bool = False, clusters: List[str] = None) -> Dict[str, XxlAdminClient]:
        if not self.settings:
            self.load()
        settings = self.settings
        default_env = settings.default_env
        credential = settings.credentials[default_env]

        if all_mode:
            runtime_clusters = list(credential.clusters.keys())
        elif clusters:
            runtime_clusters = clusters
        else:
            runtime_clusters = [settings.default_cluster]

        clients = {}
        for cluster, _ in credential.clusters.items():
            if cluster in runtime_clusters:
                clients[cluster] = self.get_client_for_cluster(default_env, cluster)
        return clients

    def get_client_for_cluster(self, env: str, cluster: str):
        ck = f"{env}:{cluster}"
        if ck in self.client_pool:
            return self.client_pool[ck]
        else:
            base_url = self.settings.credentials[env].clusters[cluster]
            credential = self.settings.credentials[env]
            client = XxlAdminClient(base_url, username=credential.username, password=credential.password)
            self.client_pool[ck] = client
            return self.client_pool[ck]
