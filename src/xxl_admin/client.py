from httpx import AsyncClient
from pathlib import Path
from http.cookiejar import LWPCookieJar
from getpass import getpass
import logging

logger = logging.getLogger(__name__)


class XxlAdminClient(object):
    def __init__(self, base_url, username: str = "", password: str = "", cookie_dir: str = None) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password
        if cookie_dir and len(cookie_dir) > 0:
            self.cookie_dir = cookie_dir
        else:
            self.cookie_dir = Path().home()
        self.cookie_path = Path(self.cookie_dir) / f"{str(hash(self.base_url))}.cookies"

        self._client = AsyncClient(base_url=self.base_url)
        self._client.cookies.jar = LWPCookieJar(filename=self.cookie_path)

    async def login(self) -> bool:
        if self.cookie_path.exists():
            self._client.cookies.jar.load(ignore_discard=True, ignore_expires=True)
        self._client.cookies.jar.clear_expired_cookies()
        if len(self._client.cookies) > 0:
            logger.info("从本地Cookies加载会话成功")
            return True
        username = self.username or input("用户名：")
        password = self.password or getpass("密码：")
        if len(username) == 0 or len(password) == 0:
            logger.error("用户名密码不能为空")
            return False
        payload = {"userName": username, "password": password}
        response = await self._client.post("/xxl-job-admin/login", data=payload)
        if response.status_code != 200:
            logger.error("登录失败：用户名或密码不正确")
            return False
        logger.info("用户%s登录成功", username)
        self._client.cookies.jar.save(ignore_discard=True, ignore_expires=False)
        return True

    async def list_group(self, name: str = "", title: str = "", start: int = 0, length: int = 30) -> list:
        payload = {"start": start, "length": length}
        if len(name) > 0:
            payload["appname"] = name
        if len(title) > 0:
            payload["title"] = title
        response = await self._client.post("/xxl-job-admin/jobgroup/pageList", data=payload)
        if response.status_code == 200:
            return response.json()["data"]
        return []

    async def list_job(
        self,
        executor: str = "",
        job_desc: str = "",
        job_group: int = -1,
        status: int = -1,
        author: str = "",
        start: int = 0,
        length: int = 30,
    ) -> list:
        payload = {
            "executorHandler": executor,
            "jobDesc": job_desc,
            "jobGroup": job_group,
            "triggerStatus": status,
            "author": author,
            "start": start,
            "length": length,
        }
        response = await self._client.post("/xxl-job-admin/jobinfo/pageList", data=payload)
        if response.status_code == 200:
            return response.json()["data"]
        return []

    async def search_job(self, executor: str) -> list:
        login_ok = await self.login()
        if not login_ok:
            return
        data = await self.list_job(executor=executor)
        return data

    async def trigger_job(self, job_id: int, param: str = None, address_list: str = None) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id, "executorParam": param, "addressList": address_list}
        response = await self._client.post("/xxl-job-admin/jobinfo/trigger", data=payload)
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    async def start_job(self, job_id: int) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id}
        response = await self._client.post("/xxl-job-admin/jobinfo/start", data=payload)
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    async def stop_job(self, job_id: int) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id}
        response = await self._client.post("/xxl-job-admin/jobinfo/stop", data=payload)
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    async def close(self):
        await self._client.aclose()
