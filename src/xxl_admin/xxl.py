# from typing import Optional
import typer
from asyncio import create_task, gather, run as aiorun
from rich import print, print_json
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from typing import Annotated, Dict, Optional, List
from .core import XxlContext, XxlCmd, XxlEnvSettings, highlight
from .client import XxlAdminClient


app_name = "xxl"
app = typer.Typer(
    name=app_name,
    help="XXL批控制台",
    context_settings={"help_option_names": ["-h", "--help"]},
)


config_app = typer.Typer(help="配置管理")
app.add_typer(config_app, name="config")

group_app = typer.Typer(help="执行器管理")
app.add_typer(group_app, name="group")

job_app = typer.Typer(help="任务管理")
app.add_typer(job_app, name="job")


def get_xxl_clients(cmd_ctx: XxlContext, all_mode: bool = False, clusters: List[str] = None):
    settings = cmd_ctx.settings
    default_env = settings.default_env
    credentials = settings.credentials[default_env]

    if all_mode:
        runtime_clusters = list(credentials.clusters.keys())
    elif clusters:
        runtime_clusters = clusters
    else:
        runtime_clusters = [settings.default_cluster]

    return {
        cluster: XxlAdminClient(base_url, username=credentials.username, password=credentials.password)
        for cluster, base_url in credentials.clusters.items()
        if cluster in runtime_clusters
    }


@app.command()
def goto(
    ctx: typer.Context,
    env_or_cluster: Annotated[str, typer.Argument(help="环境或集群（当作集群时不能指定第二个参数）")],
    cluster: Annotated[str, typer.Argument(help="集群")] = "",
):
    """
    切换环境或集群
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    if env_or_cluster in settings.env_list:
        settings.default_env = env_or_cluster
        if len(cluster) == 0:
            return
    elif env_or_cluster in settings.cluster_list():
        settings.default_cluster = env_or_cluster
        return

    if cluster in settings.cluster_list():
        settings.default_cluster = cluster
    else:
        print(f"环境或集群不存在: [red]{env_or_cluster}[/red]")
        return


@config_app.command("show")
def show_config(ctx: typer.Context):
    """
    显示当前完整配置
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    print_json(settings.model_dump_json())


@config_app.command("clusters")
def show_clusters(ctx: typer.Context, show_all: Annotated[bool, typer.Option("-a", "--all", help="是否显示所有环境的")] = False):
    """
    集群列表
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    env = settings.default_env
    if show_all:
        env = None
    for _env, credential in settings.credentials.items():
        if not env or _env == env:
            table = Table(title=f"{_env.upper()}集群列表")
            table.add_column("集群ID", justify="left", style="cyan")
            table.add_column("集群地址", justify="right", style="green", no_wrap=True)
            for cluster, host in credential.clusters.items():
                table.add_row(cluster, host)
            console = Console()
            console.print(table)


@config_app.command("add")
def add_cluster(
    ctx: typer.Context,
    cluster: Annotated[str, typer.Argument(help="集群标识")],
    host: Annotated[str, typer.Argument(help="集群地址")],
):
    """
    新增集群
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    env = settings.default_env
    settings.credentials[env].clusters[cluster] = host
    print(f"环境{env}新增/修改集群{cluster}成功")


@config_app.command("env")
def configure_env(
    ctx: typer.Context,
    env: Annotated[str, typer.Argument(help="环境标识（小写）")],
    username: Annotated[str, typer.Argument(help="用户名")] = "",
    password: Annotated[str, typer.Argument(help="密码")] = "",
):
    """
    新建或更新环境，如果已存在则只更新用户密码（如果有）
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    if env.lower() != env:
        print("环境标识只支持小写")
        return
    if env not in settings.env_list:
        settings.credentials[env] = XxlEnvSettings()
    settings.env_list.add(env)
    settings.credentials[env].username = username
    settings.credentials[env].password = password
    print(f"环境{env.upper()}设置成功")


@group_app.command("list")
def list_group(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="执行器名称，支持模糊匹配")] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    查询执行器列表
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = get_xxl_clients(cmd_ctx=cmd_ctx, all_mode=all_mode, clusters=clusters)

    async def _list_group(clients: Dict[str, XxlAdminClient], name: str):
        tasks = [c.login() for c in clients.values()]
        login_ok = any(await gather(*tasks))
        if not login_ok:
            return
        tasks = [create_task(c.list_group(name=name), name=tn) for tn, c in clients.items()]
        await gather(*tasks)
        for t in tasks:
            cluster = t.get_name()
            table = Table(title=f"{cluster.upper()}执行器列表")
            table.add_column("ID", justify="left", style="cyan")
            table.add_column("AppName", justify="left", style="cyan", no_wrap=True)
            table.add_column("名称", style="magenta")
            table.add_column("注册方式", justify="right", style="green")
            table.add_column("机器地址", justify="right", style="green")
            for group in t.result():
                table.add_row(
                    str(group["id"]),
                    highlight(group["appname"], name, "red"),
                    group["title"],
                    "自动" if group["addressType"] == 0 else "手动",
                    group["addressList"],
                )
            console = Console()
            console.print(table)

    aiorun(_list_group(clients, name))


@job_app.command("list")
def list_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")] = "",
    group: Annotated[int, typer.Option("-g", "--group", help="执行器ID")] = -1,
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    查询任务列表
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = get_xxl_clients(cmd_ctx=cmd_ctx, all_mode=all_mode, clusters=clusters)

    async def _list_job(clients: Dict[str, XxlAdminClient], name: str, job: int):
        tasks = [c.login() for c in clients.values()]
        login_ok = any(await gather(*tasks))
        if not login_ok:
            return
        tasks = [create_task(c.list_job(executor=name, job_group=job), name=tn) for tn, c in clients.items()]
        await gather(*tasks)
        for t in tasks:
            cluster = t.get_name()
            table = Table(title=f"{cluster.upper()}任务列表")
            table.add_column("ID", justify="left", style="cyan")
            table.add_column("执行器ID", justify="left", style="cyan")
            table.add_column("描述", justify="left", style="cyan", no_wrap=True)
            table.add_column("运行模式", justify="center", style="green")
            table.add_column("调度类型", style="magenta")
            table.add_column("负责人", justify="right", style="green")
            table.add_column("状态", justify="right", style="green")
            for job in t.result():
                table.add_row(
                    str(job["id"]),
                    str(job["jobGroup"]),
                    job["jobDesc"],
                    highlight(f'{job["glueType"]}: {job["executorHandler"]}', name, "red"),
                    job["scheduleConf"] if "scheduleConf" in job else job["jobCron"],
                    job["author"],
                    "关闭" if job["triggerStatus"] == 0 else "启动",
                )
            console = Console()
            console.print(table)

    aiorun(_list_job(clients, name, group))


async def search_and_match_job(clients: Dict[str, XxlAdminClient], executor: str) -> Dict[str, Dict]:
    """
    按名称匹配任务
    """
    tasks = [create_task(c.search_job(executor=executor), name=tn) for tn, c in clients.items()]
    await gather(*tasks)
    search_res_map = {}
    res_map = {}
    for t in tasks:
        cluster = t.get_name()
        search_res_map[cluster] = t.result()

    for cluster, jobs in search_res_map.items():
        if len(jobs) == 1:
            res_map[cluster] = jobs[0]
        elif len(jobs) == 0:
            res_map[cluster] = {"id": -1, "executorHandler": f"{executor}??"}
        else:
            for i, j in enumerate(jobs):
                status = "关闭" if j["triggerStatus"] == 0 else "启动"
                print(f"{i}: {j['jobDesc']}(执行器ID[{j['jobGroup']}]) {status}")
            choice_idx = Prompt.ask(":warning:存在相似名称任务，请确认你想要执行的任务序号")
            if choice_idx.isnumeric():
                idx = int(choice_idx)
            else:
                print(f":warning:集群{cluster}未能为[magenta]{executor}[/magenta]指定任务ID，将被跳过")
                idx = -1
            if idx >= 0 and idx < len(jobs):
                res_map[cluster] = jobs[idx]
            else:
                res_map[cluster] = {"id": -1, "executorHandler": f"{executor}??"}

    return res_map


@job_app.command("run")
def run_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")],
    param: Annotated[str, typer.Option("-p", "--param", help="任务参数")] = "",
    address: Annotated[str, typer.Option("-t", "--target", help="机器地址")] = None,
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    执行指定任务
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = get_xxl_clients(cmd_ctx=cmd_ctx, all_mode=all_mode, clusters=clusters)

    async def _run_job(clients: Dict[str, XxlAdminClient], executor: str, param: str = "", address: str = None):
        cluster_job_map = await search_and_match_job(clients, executor)
        tasks = [
            create_task(
                c.trigger_job(job_id=cluster_job_map[tn]["id"], param=param, address_list=address),
                name=tn,
            )
            for tn, c in clients.items()
        ]
        await gather(*tasks)
        for t in tasks:
            cluster = t.get_name()
            handler = cluster_job_map[cluster]["executorHandler"]
            if t.result():
                res = "[green]OK[/green]"
            else:
                res = "[red]FAILED[/red]"
            print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 触发结果: {res}")

    aiorun(_run_job(clients, executor, param, address))


@job_app.command("add")
def add_job(ctx: typer.Context):
    """
    创建新任务
    """
    pass


@job_app.command("disable")
def disable_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")],
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    停止任务
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = get_xxl_clients(cmd_ctx=cmd_ctx, all_mode=all_mode, clusters=clusters)

    async def _disable_job(clients: Dict[str, XxlAdminClient], executor: str):
        cluster_job_map = await search_and_match_job(clients, executor)
        tasks = [
            create_task(
                c.stop_job(job_id=cluster_job_map[tn]["id"]),
                name=tn,
            )
            for tn, c in clients.items()
        ]
        await gather(*tasks)
        for t in tasks:
            cluster = t.get_name()
            handler = cluster_job_map[cluster]["executorHandler"]
            if t.result():
                res = "[green]OK[/green]"
            else:
                res = "[red]FAILED[/red]"
            print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 执行结果: {res}")

    aiorun(_disable_job(clients, executor))


@job_app.command("enable")
def enable_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument()],
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    启动任务
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = get_xxl_clients(cmd_ctx=cmd_ctx, all_mode=all_mode, clusters=clusters)

    async def _enable_job(clients: Dict[str, XxlAdminClient], executor: str):
        cluster_job_map = await search_and_match_job(clients, executor)
        tasks = [
            create_task(
                c.start_job(job_id=cluster_job_map[tn]["id"]),
                name=tn,
            )
            for tn, c in clients.items()
        ]
        await gather(*tasks)
        for t in tasks:
            cluster = t.get_name()
            handler = cluster_job_map[cluster]["executorHandler"]
            if t.result():
                res = "[green]OK[/green]"
            else:
                res = "[red]FAILED[/red]"
            print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 执行结果: {res}")

    aiorun(_enable_job(clients, executor))


cmd = XxlCmd(typer=app, ctx=XxlContext(name=app_name))
