import re
from typer import Typer, get_app_dir
from typing import Dict, Set
from pathlib import Path
from pydantic import BaseModel
from typer_cmd.shell import TyperCmd, CmdContext


def highlight(str1, substr1, color):
    if not substr1 or len(substr1) == 0:
        return str1
    p = re.compile(re.escape(substr1), re.IGNORECASE)
    for m in p.findall(str1):
        str1 = p.sub(f"[{color}]{m}[/{color}]", str1)
    return str1


class XxlEnvSettings(BaseModel):
    username: str = "admin"
    password: str = ""
    clusters: Dict[str, str] = {"cn": "http://localhost:8080"}


class XxlSettings(BaseModel):
    name: str = "xxl"
    env_list: Set[str] = {"test"}
    default_env: str = "test"
    default_cluster: str = "cn"
    credentials: Dict[str, XxlEnvSettings] = {"cn": XxlEnvSettings()}

    def cluster_list(self) -> Set[str]:
        clusters = set()
        for env in self.credentials.values():
            for cl in env.clusters.keys():
                clusters.add(cl)
        return clusters


class XxlContext(CmdContext):
    SETTINGS_FILENAME = "settings.json"

    def __init__(self, name: str = "xxl", settings_file: str = None) -> None:
        if not settings_file:
            settings_file = Path(get_app_dir(name)) / self.SETTINGS_FILENAME
        else:
            settings_file = (
                Path(settings_file)
                if settings_file.endswith(".json")
                else Path(settings_file) / self.SETTINGS_FILENAME
            )

        self._location: Path = settings_file
        self._last_updated_at = self._location.stat().st_mtime or 0
        self.settings: XxlSettings = None

    def load(self):
        # do nothing when file not exists
        if not self._location.exists():
            return
        self.settings = XxlSettings.model_validate_json(self._location.read_text())

    def save(self):
        # been changed since last loaded
        mtime = self._location.stat().st_mtime
        if mtime and mtime > self._last_updated_at:
            return
        self._location.write_text(
            XxlSettings.model_dump_json(self.settings, exclude_unset=True, indent=4)
        )


class XxlCmd(TyperCmd):
    def __init__(self, typer: Typer, ctx: XxlContext = None, **kwargs):
        super().__init__(typer=typer, **kwargs)
        self.ctx: XxlContext = ctx

    def get_prompt(self) -> str | None:
        if not self.ctx:
            return super().get_prompt()
        else:
            settings = self.ctx.settings
            return f"(XXL[{settings.default_env}|{settings.default_cluster}]) "
