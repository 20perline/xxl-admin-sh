import logging
from pathlib import Path
from typer import get_app_dir
from typing import List, Dict
from rich.prompt import Prompt

from .settings import XxlSettings
from .client import XxlAdminClient

logger = logging.getLogger(__name__)


class XxlContext(object):
    SETTINGS_FILENAME = "xxl.json"
    LOG_FILENAME = "xxl.log"

    def __init__(self, settings_file: str = None) -> None:
        if not settings_file:
            settings_file = Path(get_app_dir("XXL")).parent / self.SETTINGS_FILENAME
        else:
            settings_file = (
                Path(settings_file) if settings_file.endswith(".json") else Path(settings_file) / self.SETTINGS_FILENAME
            )

        self.local_registry = None
        self.settings: XxlSettings = None
        self.location: Path = settings_file
        self._settings_file_created = settings_file.exists()
        self._last_updated_at = self.location.stat().st_mtime if self._settings_file_created else 0
        self.setup_log()

    def setup_log(self):
        log_file = self.location.parent / self.LOG_FILENAME
        logging.basicConfig(
            filename=log_file,
            filemode="a",
            format="%(asctime)s %(levelname)-8s %(name)-15s %(message)s",
            level="DEBUG",
        )

    def load(self):
        if self.settings:
            return
        if not self._settings_file_created:
            logger.debug("settings file not found, using default settings")
            self.settings = XxlSettings()
        else:
            logger.debug(f"loading settings from file: {self.location}")
            self.settings = XxlSettings.model_validate_json(self.location.read_text())

    def save(self):
        # been changed since last loaded
        mtime = self.location.stat().st_mtime if self._settings_file_created else 0
        if mtime and mtime > self._last_updated_at:
            logger.debug("settings had been modified from local file. current settings won't be saved.")
            return
        self.location.write_text(self.settings.model_dump_json(exclude_none=True, indent=4))
        self._settings_file_created = True
        logger.debug("settings saved to local file.")

    def get_clients(self, all_mode: bool = False, clusters: List[str] = None) -> Dict[str, XxlAdminClient]:
        if not self.settings:
            self.load()
        settings = self.settings
        default_env = settings.default_env
        credential = settings.credentials[default_env]

        if all_mode:
            runtime_clusters = list(credential.clusters.keys())
        elif clusters:
            runtime_clusters = set(clusters)
        else:
            runtime_clusters = [settings.default_cluster]

        if len(credential.username) == 0:
            credential.username = Prompt.ask('用户名')
        if len(credential.password) == 0:
            credential.password = Prompt.ask('密码', password=True)
        return {
            cluster: XxlAdminClient(base_url, username=credential.username, password=credential.password)
            for cluster, base_url in credential.clusters.items()
            if cluster in runtime_clusters
        }
