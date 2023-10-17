from typing import Dict, Set
from pydantic import BaseModel


class XxlEnvSettings(BaseModel):
    username: str = "admin"
    password: str = ""
    clusters: Dict[str, str] = {"cn": "http://localhost:8080"}


class XxlSettings(BaseModel):
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
