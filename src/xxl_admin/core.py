import shlex
import logging
from typer import Typer
from typing import Tuple, List
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from . import __version__
from .key_bindings import kb as key_bindings
from .context import XxlContext

logger = logging.getLogger(__name__)


class XxlShell(object):
    NAME = "XXL-Admin-SH"

    def __init__(self, typer: Typer):
        self.typer = typer
        self.ctx = XxlContext()

        cmd_map = self._recur_get_commands(self.typer)
        cmd_map["exit"] = cmd_map["quit"] = cmd_map["help"] = None
        self.completer = NestedCompleter.from_nested_dict(cmd_map)
        self.intro()

    def _recur_get_commands(self, typer: Typer):
        cmd_map = {}
        for cmd_info in typer.registered_commands:
            cmd_map[cmd_info.name] = None
        for group in typer.registered_groups:
            cmd_map[group.name] = self._recur_get_commands(group.typer_instance)
        return cmd_map

    def get_prompt_style(self) -> Tuple[List[Tuple], Style]:
        style = Style.from_dict(
            {
                # empty string means user input
                # "": "#ff0066",
                "username": "#91bb75",
                "at": "#a96abe",
                "env": "#e5c07b",
                "pound": "#56b6c2"
            }
        )

        settings = self.ctx.settings
        username = settings.credentials[settings.default_env].username
        message = [
            ("class:username", username),
            ("class:at", "@"),
            ("class:env", f"{settings.default_env}:{settings.default_cluster}"),
            ("class:pound", " XXL# "),
        ]
        return message, style

    def intro(self):
        xxl_sh_version = f"{self.NAME} {__version__}"
        home = "Home: https://github.com/20perline/xxl-admin-sh"
        issues = "Issues: https://github.com/20perline/xxl-admin-sh/issues"
        print("\n".join([xxl_sh_version, home, issues]), "\n")

    def start(self):

        self.ctx.load()

        session = PromptSession(
            history=FileHistory(Path().home() / ".xxl.history"),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.completer,
            complete_while_typing=True,
            enable_open_in_editor=False,
        )

        while True:
            logger.info("REPL waiting for command...")
            try:
                prompt, style = self.get_prompt_style()
                command = session.prompt(
                    prompt,
                    style=style,
                    key_bindings=key_bindings,
                    enable_suspend=False,
                )
            except KeyboardInterrupt:
                logger.warning("KeyboardInterrupt!")
                continue
            except EOFError:
                break
            command = command.strip()
            logger.info(f"[Command] {command}")
            if not command:
                continue
            if command == "exit" or command == "quit":
                break
            if command == "help":
                self.typer(prog_name="", standalone_mode=False)
                continue
            args = shlex.split(command)
            extra = {"obj": self.ctx}
            try:
                self.typer(args=args, prog_name="", standalone_mode=False, **extra)
            except Exception as e:
                logger.exception(e)
                print(f"异常：{e}")

        # save context after loop exit
        self.ctx.save()
