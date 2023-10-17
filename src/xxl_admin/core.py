import shlex
from typer import Typer
from typer.main import get_group
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
from .utils import get_typer_commands


class XxlShell(object):
    NAME = "XXL-Admin-SH"

    def __init__(self, typer: Typer):
        self.typer = typer
        self.ctx = XxlContext()

        cmd_map = get_typer_commands(get_group(self.typer))
        self.completer = NestedCompleter.from_nested_dict(cmd_map)

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
        self.intro()

        while True:
            try:
                prompt, style = self.get_prompt_style()
                command = session.prompt(
                    prompt,
                    style=style,
                    key_bindings=key_bindings,
                    enable_suspend=False,
                )
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            command = command.strip()
            if not command:
                continue
            if command == "exit" or command == "quit":
                break
            if command == "help":
                self.typer(prog_name="", standalone_mode=False)
                continue
            args = shlex.split(command)
            extra = {"obj": self.ctx}
            self.typer(args=args, prog_name="", standalone_mode=False, **extra)

        # save context after loop exit
        self.ctx.save()
