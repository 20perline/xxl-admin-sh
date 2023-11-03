import asyncio
import arrow
import inspect
import socket
import typer
from asyncio import create_task, gather
from functools import wraps
from rich import print, print_json
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from typing import Annotated, Dict, Optional, List

from .settings import XxlEnvSettings
from .context import XxlContext
from .utils import highlight
from .client import XxlAdminClient


__all__ = ["app"]


def coroutine_cmd(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if inspect.iscoroutinefunction(f):
            return asyncio.run(f(*args, **kwargs))
        return f(*args, **kwargs)

    return wrapper


app = typer.Typer(
    help="XXL批控制台",
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=True,
    options_metavar="",
    add_completion=False,
    add_help_option=False,
)

config_app = typer.Typer(help="配置管理")
group_app = typer.Typer(help="执行器管理")
job_app = typer.Typer(help="任务管理")


@app.command(name="goto")
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
    print(f"配置文件路径：{cmd_ctx.location}")
    print_json(settings.model_dump_json())


@config_app.command("list-clusters")
def list_clusters(ctx: typer.Context, show_all: Annotated[bool, typer.Option("-a", "--all", help="是否显示所有环境的")] = False):
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
            table.add_column("集群地址", justify="right", style="green")
            for cluster, host in credential.clusters.items():
                table.add_row(cluster, host)
            console = Console()
            console.print(table)


@config_app.command("add-cluster")
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


@config_app.command("remove-cluster")
def remove_cluster(
    ctx: typer.Context,
    cluster: Annotated[str, typer.Argument(help="集群标识")],
):
    """
    移除集群
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    env = settings.default_env
    if cluster in settings.credentials[env].clusters:
        del settings.credentials[env].clusters[cluster]
    print(f"环境{env}移除集群{cluster}成功")


@config_app.command("env-set")
def env_set(
    ctx: typer.Context,
    env: Annotated[str, typer.Argument(help="环境标识, 不传表示当前环境")] = "",
    username: Annotated[str, typer.Option("-u", "--user", help="用户名")] = "",
    password: Annotated[str, typer.Option("-p", "--pass", help="密码")] = "",
):
    """
    新建或更新环境，如果已存在则只更新用户密码（如果有）
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    if len(env) == 0:
        env = settings.default_env
    env = env.lower()
    if env not in settings.env_list:
        settings.credentials[env] = XxlEnvSettings()
    settings.env_list.add(env)
    if len(username) > 0:
        settings.credentials[env].username = username
    if len(password) > 0:
        settings.credentials[env].password = password
    print(f"环境 [green]{env.upper()}[/green] 设置成功")


@group_app.command("list")
@coroutine_cmd
async def list_group(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="执行器名称，支持模糊匹配")] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    查询执行器列表
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    tasks = [create_task(c.list_group(name=name), name=tn) for tn, c in clients.items()]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        table = Table(title=f"{cluster.upper()}执行器列表")
        table.add_column("ID", justify="left", style="cyan")
        table.add_column("AppName", justify="left", style="cyan")
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


@job_app.command("list")
@coroutine_cmd
async def list_job(
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
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    g_prefix = "_group"
    group_tasks = [create_task(c.list_group(name=""), name=f"{g_prefix}{tn}") for tn, c in clients.items()]
    job_tasks = [create_task(c.list_job(executor=name, job_group=group), name=tn) for tn, c in clients.items()]
    tasks = group_tasks + job_tasks
    await gather(*tasks)
    group_names = {}
    for gt in group_tasks:
        for g in gt.result():
            group_names[g["id"]] = g["appname"]
    for t in job_tasks:
        cluster = t.get_name()
        table = Table(title=f"{cluster.upper()}任务列表")
        table.add_column("ID", justify="left", style="cyan")
        table.add_column("执行器", justify="left", style="cyan")
        table.add_column("描述", justify="left", style="cyan")
        table.add_column("运行模式", justify="center", style="green", no_wrap=True)
        table.add_column("调度类型", style="magenta")
        table.add_column("负责人", justify="right", style="green")
        table.add_column("状态", justify="right", style="green")
        for job in t.result():
            group = group_names.get(job["jobGroup"], "")
            group = f'{group}({job["jobGroup"]})'
            table.add_row(
                str(job["id"]),
                group,
                job["jobDesc"],
                highlight(f'{job["glueType"]}: {job["executorHandler"]}', name, "red"),
                job["scheduleConf"] if "scheduleConf" in job else job["jobCron"],
                job["author"],
                "关闭" if job["triggerStatus"] == 0 else "启动",
            )
        console = Console()
        console.print(table)


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
                print(f"{i}: {j['jobDesc']}(执行器ID[{j['jobGroup']}]) 当前状态：{status}")
            choice_idx = Prompt.ask("[bold gold1]!!!存在相似名称任务，请确认你想要执行的任务序号[/bold gold1]")
            print("\n")
            if choice_idx.isnumeric():
                idx = int(choice_idx)
            else:
                idx = -1
            if idx >= 0 and idx < len(jobs):
                res_map[cluster] = jobs[idx]
            else:
                res_map[cluster] = {"id": -1, "executorHandler": f"{executor}??"}

    return res_map


@job_app.command("run")
@coroutine_cmd
async def run_job(
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
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    cluster_job_map = await search_and_match_job(clients, executor)
    tasks = [
        create_task(c.trigger_job(job_id=cluster_job_map[tn]["id"], param=param, address_list=address), name=tn)
        for tn, c in clients.items()
    ]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        match_id = cluster_job_map[cluster]["id"]
        handler = cluster_job_map[cluster]["executorHandler"]
        if t.result():
            res = "[green]OK[/green]"
        else:
            res = "[red]FAILED[/red]" if match_id > 0 else "[red]SKIPPED[/red]"
        print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 触发结果: {res}")


@job_app.command("debug")
@coroutine_cmd
async def debug_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")],
    param: Annotated[str, typer.Option("-p", "--param", help="任务参数")] = "",
):
    """
    本地触发指定任务
    """
    cmd_ctx: XxlContext = ctx.obj
    default_cluster = cmd_ctx.settings.default_cluster
    clients = cmd_ctx.get_clients(all_mode=False, clusters=None)
    address = cmd_ctx.local_registry
    if address is None:
        groups = await clients[default_cluster].list_group()
        ip = socket.gethostbyname(socket.gethostname())
        registry_list = set(
            r for group in groups if group["registryList"] is not None for r in group["registryList"]
        )
        address = next((x for x in registry_list if ip in x), None)
        # 缓存起来
        cmd_ctx.local_registry = address
    if not address:
        print("本地执行器未找到，请确认是否注册成功")
        return
    cluster_job_map = await search_and_match_job(clients, executor)
    if default_cluster not in cluster_job_map:
        print(f"本地任务不存在 [red]{executor}[/red]")
        return
    job_id = cluster_job_map[default_cluster]["id"]

    trigger_ok = await clients[default_cluster].trigger_job(job_id=job_id, param=param, address_list=address)
    if trigger_ok:
        res = "[green]OK[/green]"
    else:
        res = "[red]FAILED[/red]"
    print(f"本地触发 [magenta]{executor}[/magenta] 结果: {res}")


@job_app.command("add")
@coroutine_cmd
async def add_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Option("--exec", help="JobHandler")],
    group: Annotated[int, typer.Option("--group", help="执行器ID")],
    cron: Annotated[str, typer.Option("--cron", help="Cron")],
    title: Annotated[str, typer.Option("--title", help="任务标题")],
    author: Annotated[str, typer.Option("--author", help="责任人")] = "",
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    创建新任务
    """
    cmd_ctx: XxlContext = ctx.obj
    settings = cmd_ctx.settings
    if len(author) == 0:
        author = settings.get_default_user()

    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)
    tasks = [
        create_task(c.add_job(job_group=group, executor=executor, job_desc=title, cron=cron, author=author), name=tn)
        for tn, c in clients.items()
    ]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        if t.result():
            res = "[green]OK[/green]"
        else:
            res = "[red]FAILED[/red]"
        print(f"{cluster.upper()}集群 创建任务 [magenta]{executor}[/magenta] 结果: {res}")


@job_app.command("update")
@coroutine_cmd
async def update_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="JobHandler")],
    cron: Annotated[str, typer.Option("--cron", help="Cron")] = None,
    title: Annotated[str, typer.Option("--title", help="任务标题")] = None,
    title_prefix: Annotated[str, typer.Option("--prefix", help="任务标题前缀")] = None,
    author: Annotated[str, typer.Option("--author", help="责任人")] = None,
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    更新任务
    """
    cmd_ctx: XxlContext = ctx.obj

    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)
    cluster_job_map = await search_and_match_job(clients, executor)

    tasks = []
    for cluster, client in clients.items():
        cur_job = cluster_job_map[cluster]
        if cur_job["id"] <= 0:
            continue
        job_id = cur_job["id"]
        job_group = cur_job["jobGroup"]
        executor = cur_job["executorHandler"]
        cron = cron or cur_job.get("jobCron", None) or cur_job.get("scheduleConf", None)
        title = title or cur_job["jobDesc"]
        title = f"{title_prefix}{title}" if title_prefix else title
        author = author or cur_job["author"]

        task = create_task(client.update_job(job_id, job_group, executor, title, cron, author), name=cluster)
        tasks.append(task)

    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        if t.result():
            res = "[green]OK[/green]"
        else:
            res = "[red]FAILED[/red]"
        print(f"{cluster.upper()}集群 更新任务 [magenta]{executor}[/magenta] 结果: {res}")


@job_app.command("off")
@coroutine_cmd
async def disable_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")],
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    停止任务
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    cluster_job_map = await search_and_match_job(clients, executor)
    tasks = [create_task(c.stop_job(job_id=cluster_job_map[tn]["id"]), name=tn) for tn, c in clients.items()]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        match_id = cluster_job_map[cluster]["id"]
        handler = cluster_job_map[cluster]["executorHandler"]
        if t.result():
            res = "[green]OK[/green]"
        else:
            res = "[red]FAILED[/red]" if match_id > 0 else "[red]SKIPPED[/red]"
        print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 执行结果: {res}")


@job_app.command("on")
@coroutine_cmd
async def enable_job(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument()],
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    启动任务
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    cluster_job_map = await search_and_match_job(clients, executor)
    tasks = [create_task(c.start_job(job_id=cluster_job_map[tn]["id"]), name=tn) for tn, c in clients.items()]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        match_id = cluster_job_map[cluster]["id"]
        handler = cluster_job_map[cluster]["executorHandler"]
        if t.result():
            res = "[green]OK[/green]"
        else:
            res = "[red]FAILED[/red]" if match_id > 0 else "[red]SKIPPED[/red]"
        print(f"{cluster.upper()}集群 [magenta]{handler}[/magenta] 执行结果: {res}")


@job_app.command("log")
@coroutine_cmd
async def show_job_log(
    ctx: typer.Context,
    executor: Annotated[str, typer.Argument(help="任务名称，支持模糊匹配")],
    time_range: Annotated[str, typer.Argument(help="调度时间范围，如2 days ago等描述性语言，默认近1天")] = "1 days ago",
    all_mode: Annotated[bool, typer.Option("-a", "--all", help="是否在所有集群执行")] = False,
    clusters: Annotated[Optional[List[str]], typer.Option("-c", "--cluster", help="仅在特定集群上执行（支持多个）")] = None,
):
    """
    查询任务日志
    """
    cmd_ctx: XxlContext = ctx.obj
    clients = cmd_ctx.get_clients(all_mode=all_mode, clusters=clusters)

    arw = arrow.utcnow().to("local")
    start_time = arw.dehumanize(time_range)
    arw_str = arw.format("YYYY-MM-DD HH:mm:ss")
    start_time_str = start_time.format("YYYY-MM-DD HH:mm:ss")

    cluster_job_map = await search_and_match_job(clients, executor)
    tasks = [
        create_task(c.job_logs(job_id=cluster_job_map[tn]["id"], filter_time=f"{start_time_str} - {arw_str}"), name=tn)
        for tn, c in clients.items()
    ]
    await gather(*tasks)
    for t in tasks:
        cluster = t.get_name()
        handler = cluster_job_map[cluster]["executorHandler"]
        table = Table(title=f"{cluster.upper()} - {handler}调度日志")
        table.add_column("ID", justify="left", style="cyan")
        table.add_column("调度时间", justify="left", style="cyan")
        table.add_column("调度结果", justify="left", style="cyan")
        table.add_column("执行时间", justify="center", style="green", no_wrap=True)
        table.add_column("执行参数", style="magenta")
        table.add_column("执行结果", style="magenta")
        for job in t.result():
            table.add_row(
                str(job["jobId"]),
                job["triggerTime"],
                "成功" if job["triggerCode"] == 200 else "失败",
                job["handleTime"],
                job["executorParam"],
                "成功" if job["handleCode"] == 200 else "失败",
            )
        console = Console()
        console.print(table)


app.add_typer(config_app, name="config")
app.add_typer(group_app, name="group")
app.add_typer(job_app, name="job")
