import logging
import inspect
from httpx import AsyncClient
from pathlib import Path
from http.cookiejar import LWPCookieJar

from .utils import md5, generate_default_value

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
        self.cookie_path = Path(self.cookie_dir) / f"{str(md5(self.base_url))}.cookies"

        self.is_logged_in = False
        self._client = AsyncClient(base_url=self.base_url)
        self._client.cookies.jar = LWPCookieJar(filename=self.cookie_path)

    def _required_login(func):
        async def wrapper(self: "XxlAdminClient", *args, **kwargs):
            login_ok = True
            if not self.is_logged_in:
                login_ok = await self.login()
            if not login_ok:
                func_sig = inspect.signature(func)
                return_type = func_sig.return_annotation
                return generate_default_value(return_type)
            return await func(self, *args, **kwargs)

        return wrapper

    async def login(self) -> bool:
        if self.is_logged_in:
            return True
        if self.cookie_path.exists():
            self._client.cookies.jar.load(ignore_discard=True, ignore_expires=True)
        self._client.cookies.jar.clear_expired_cookies()
        if len(self._client.cookies) > 0:
            logger.info("从本地Cookies加载会话成功")
            self.is_logged_in = True
            return True
        username = self.username
        password = self.password
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
        self.is_logged_in = True
        return True

    @_required_login
    async def list_group(self, name: str = "", title: str = "", start: int = 0, length: int = 30) -> list:
        payload = {"start": start, "length": length}
        if len(name) > 0:
            payload["appname"] = name
        if len(title) > 0:
            payload["title"] = title
        response = await self._client.post("/xxl-job-admin/jobgroup/pageList", data=payload)
        logger.info(f"list group request: {response.request.url} {payload}")
        logger.info(f"list group response: {response.text}")
        if response.status_code == 200:
            return response.json()["data"]
        return []

    @_required_login
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
        logger.info(f"list job request: {response.request.url} {payload}")
        logger.info(f"list job response: {response.text}")
        if response.status_code == 200:
            return response.json()["data"]
        return []

    @_required_login
    async def job_logs(
        self,
        job_id: int,
        job_group: int = -1,
        log_status: int = -1,
        filter_time: str = "",
        start: int = 0,
        length: int = 30,
    ) -> list:
        payload = {
            "jobId": job_id,
            "jobGroup": job_group,
            "logStatus": log_status,
            "filterTime": filter_time,
            "start": start,
            "length": length,
        }
        response = await self._client.post("/xxl-job-admin/joblog/pageList", data=payload)
        logger.info(f"job logs request: {response.request.url} {payload}")
        logger.info(f"job logs response: {response.text}")
        if response.status_code == 200:
            return response.json()["data"]
        return []

    @_required_login
    async def search_job(self, executor: str) -> list:
        data = await self.list_job(executor=executor)
        return data

    @_required_login
    async def trigger_job(self, job_id: int, param: str = None, address_list: str = None) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id, "executorParam": param, "addressList": address_list}
        response = await self._client.post("/xxl-job-admin/jobinfo/trigger", data=payload)
        logger.info(f"trigger job request: {response.request.url} {payload}")
        logger.info(f"trigger job response: {response.text}")
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    @_required_login
    async def start_job(self, job_id: int) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id}
        response = await self._client.post("/xxl-job-admin/jobinfo/start", data=payload)
        logger.info(f"start job request: {response.request.url} {payload}")
        logger.info(f"start job response: {response.text}")
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    @_required_login
    async def stop_job(self, job_id: int) -> bool:
        if job_id <= 0:
            return False
        payload = {"id": job_id}
        response = await self._client.post("/xxl-job-admin/jobinfo/stop", data=payload)
        logger.info(f"stop job request: {response.request.url} {payload}")
        logger.info(f"stop job response: {response.text}")
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    @_required_login
    async def add_job(self, job_group: int, job_desc: str, executor: str, cron: str, author: str) -> bool:
        if job_group <= 0:
            return False
        payload = {
            "jobGroup": job_group,
            "jobDesc": job_desc,
            "cronGen_display": cron,
            "jobCron": cron,
            "scheduleType": "CRON",  # 2.4.*
            "scheduleConf": cron,  # 2.4.*
            "glueType": "BEAN",
            "executorHandler": executor,
            "executorRouteStrategy": "FIRST",
            "executorBlockStrategy": "SERIAL_EXECUTION",
            "misfireStrategy": "DO_NOTHING",
            "author": author,
            "executorTimout": 0,
            "executorFailRetryCount": 0,
        }
        response = await self._client.post("/xxl-job-admin/jobinfo/add", data=payload)
        logger.info(f"add new job request: {response.request.url} {payload}")
        logger.info(f"add new job response: {response.text}")
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    @_required_login
    async def update_job(
        self, job_id: int, job_group: int, job_desc: str, executor: str, cron: str, author: str
    ) -> bool:
        if job_id <= 0 or job_group <= 0:
            return False
        payload = {
            "id": job_id,
            "jobGroup": job_group,
            "jobDesc": job_desc,
            "cronGen_display": cron,
            "jobCron": cron,  # 2.2.*
            "scheduleType": "CRON",  # 2.4.*
            "scheduleConf": cron,  # 2.4.*
            "glueType": "BEAN",
            "executorHandler": executor,
            "executorRouteStrategy": "FIRST",
            "executorBlockStrategy": "SERIAL_EXECUTION",
            "author": author,
            "misfireStrategy": "DO_NOTHING",
            "executorTimout": 0,
            "executorFailRetryCount": 0,
        }
        response = await self._client.post("/xxl-job-admin/jobinfo/update", data=payload)
        logger.info(f"update job request: {response.request.url} {payload}")
        logger.info(f"update job response: {response.text}")
        if response.status_code != 200:
            return False
        return response.json()["code"] == 200

    async def close(self):
        await self._client.aclose()
