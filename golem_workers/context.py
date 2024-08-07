from copy import deepcopy

from itertools import chain

import collections.abc
import json
import shlex
from typing import Mapping, Optional, Union, MutableMapping, Sequence
from ya_activity import ExeScriptRequest

from golem.node import GolemNode
from golem.resources import Activity, PoolingBatch


class WorkContextCommand:
    def __init__(self, context: "WorkContext", script: Sequence[Mapping]) -> None:
        self._context = context
        self._script = script

        self._batch: Optional[PoolingBatch] = None

    @property
    def script(self) -> Sequence[Mapping]:
        return self._script

    def __await__(self):
        if self._batch:
            raise RuntimeError("Action was already awaited!")

        async def inner():
            self._batch = await self._context.activity.execute(
                ExeScriptRequest(json.dumps(self._script))
            )
            results = await self._batch.wait()

            return results

        return inner().__await__()


class WorkContext:
    def __init__(
        self,
        activity: Activity,
        extra: Optional[MutableMapping] = None,
        default_deploy_args: Optional[Mapping] = None,
    ) -> None:
        self._activity = activity

        self.extra = extra or {}
        self.default_deploy_args: MutableMapping = default_deploy_args or {}

    @property
    def golem_node(self) -> GolemNode:
        return self._activity.node

    @property
    def activity(self):
        return self._activity

    def _make_command(self, script: Union[Mapping, Sequence[Mapping]]) -> WorkContextCommand:
        if not isinstance(script, collections.abc.Sequence):
            script = [script]

        return WorkContextCommand(self, script)

    def deploy(self, args: Optional[Mapping] = None) -> WorkContextCommand:
        deploy_args = deepcopy(self.default_deploy_args)

        if args:
            deploy_args.update(args)

        return self._make_command({"deploy": deploy_args})

    def start(self) -> WorkContextCommand:
        return self._make_command({"start": {}})

    def run(
        self,
        command: Union[str, Sequence[str]],
        *,
        shell: Optional[bool] = None,
        shell_cmd: str = "/bin/sh",
    ) -> WorkContextCommand:
        """Run.

        :param command: Either a list `[entry_point, *args]` or a string.
        :param shell: If True, command will be passed as a string to "/bin/sh -c".
            Default value is True if `command` is a string and False if it is a list.
        :param shell_cmd: Shell command, matters only in `shell` is True.

        Examples::

            ctx.run(["/bin/echo", "foo"])                       # /bin/echo "foo"
            ctx.run("echo foo")                                 # /bin/sh -c "echo foo"
            ctx.run(["echo", "foo"], shell=True)                # /bin/sh -c "echo foo"
            ctx.run(["/bin/echo", "foo", ">", "/my_volume/x"])  # /bin/echo "foo" ">" "/my_volume/x"
                                                            # (NOTE: this is usually **not** the
                                                            # intended effect)
            ctx.run("echo foo > /my_volume/x")              # /bin/sh -c "echo foo > /my_volume/x"
                                                            # (This is better)
        """

        if shell is None:
            shell = isinstance(command, str)

        if shell:
            command_str = command if isinstance(command, str) else shlex.join(command)
            entry_point = shell_cmd
            args = ["-c", command_str]
        else:
            command_list = command if isinstance(command, list) else shlex.split(command)
            entry_point, *args = command_list

        if 1 < len(entry_point.split()):
            raise ValueError(f"Whitespaces in entry point '{entry_point}' are forbidden")

        return self._make_command(
            {
                "run": {
                    "entry_point": entry_point,
                    "args": args,
                    "capture": {
                        "stdout": {
                            "stream": {},
                        },
                        "stderr": {
                            "stream": {},
                        },
                    },
                }
            }
        )

    async def destroy(self) -> None:
        await self._activity.destroy()

    def gather(self, *commands: WorkContextCommand) -> WorkContextCommand:
        return self._make_command(list(chain.from_iterable(action.script for action in commands)))
