# from typing import Optional
import typer
from asyncio import create_task, gather, run as aiorun
from rich import print, print_json
from rich.table import Table
from rich.console import Console
from typing import Annotated, Dict, Optional, List
from .core import XxlContext, XxlCmd, highlight
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


def get_xxl_clients(
    cmd_ctx: XxlContext, all_mode: bool = False, clusters: List[str] = None
):
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
        cluster: XxlAdminClient(
            base_url, username=credentials.username, password=credentials.password
        )
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
    if env_or_cluster in settings.env_list():
        settings.default_env = env_or_cluster
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
    显示当前配置
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    print_json(settings.model_dump_json())


@group_app.command("list")
def list_group(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster")] = None,
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
        tasks = [
            create_task(c.list_group(name=name), name=tn) for tn, c in clients.items()
        ]
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
    name: Annotated[str, typer.Argument()] = "",
    group: Annotated[int, typer.Option("-g", "--group")] = -1,
    all_mode: Annotated[bool, typer.Option("-a", "--all")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster")] = None,
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
        tasks = [
            create_task(c.list_job(executor=name, job_group=job), name=tn)
            for tn, c in clients.items()
        ]
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
                    highlight(
                        f'{job["glueType"]} {job["executorHandler"]}', name, "red"
                    ),
                    job["scheduleConf"] if "scheduleConf" in job else job["jobCron"],
                    job["author"],
                    "关闭" if job["triggerStatus"] == 0 else "启动",
                )
            console = Console()
            console.print(table)

    aiorun(_list_job(clients, name, group))


@job_app.command("run")
def run_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument()],
    all_mode: Annotated[bool, typer.Option("-a", "--all")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster")] = None,
):
    """
    执行指定任务
    """
    pass


@job_app.command("add")
def add_job(
    ctx: typer.Context
):
    """
    创建新任务
    """
    pass


@job_app.command("disable")
def disable_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster")] = None,
):
    """
    创建新任务
    """
    pass


@job_app.command("enable")
def enable_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster")] = None,
):
    """
    创建新任务
    """
    pass


cmd = XxlCmd(typer=app, ctx=XxlContext(name=app_name))
