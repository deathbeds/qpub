import dgaf
import pathlib
import functools
Path = type(pathlib.Path())

compat = {"yml": "yaml", "cfg": "ini"}


def squash_depfinder(object):
    import depfinder
    if isinstance(object, tuple):
        object = object[-1]
    if isinstance(object, depfinder.main.ImportFinder):
        object = object.describe()
    return set(object.get('required', set())).union(
        object.get('questionable', set()))
    return object


class File(Path):
    def __bool__(self):
        return self.is_file()

    def imports(self):
        import depfinder
        if self.suffix == '.py':
            deps = depfinder.parse_file(self)
        elif self.suffix == '.ipynb':
            deps = depfinder.notebook_path_to_dependencies(self)
        else:
            deps = {}
        return squash_depfinder(deps)

    def load(self):
        if self.suffix == '.env' or self.stem == '.env':
            import os
            import dotenv
            dotenv.load_dotenv(dotenv_path=self)
            return dict(os.environ)
        try:
            suffix = self.suffix.lstrip('.')
            suffix = compat.get(suffix, suffix)

            return __import__("anyconfig").load(self, suffix)
        except FileNotFoundError:
            return {}

    def dump(self, *object):
        object = functools.reduce(merge, object)
        suffix = self.suffix.lstrip('.')
        suffix = compat.get(suffix, suffix)

        return __import__("anyconfig").dump(object, self, suffix)

    def commit(self, msg, ammend=False):
        return


class Dir(Path):
    def __bool__(self):
        return self.is_dir()


class Module(str):
    def __bool__(self):
        try:
            return False
        except:
            return False


def merge(a, b):
    """merge dictionaries.  """
    a, b = a or {}, b or {}
    for k in set(a).union(b):
        kind = type(a[k] if k in a else b[k])
        if k not in a:
            a[k] = kind()
        if issubclass(kind, dict):
            a[k] = merge(a[k], b.get(k, kind()))
        elif issubclass(kind, set):
            a[k] = a[k].union(b.get(k, kind()))
        elif issubclass(kind, (tuple, list)):
            # assume unique lists
            a[k] += [x for x in b.get(k, kind()) if x not in a[k]]
        else:
            a[k] = a[k] or b.get(k, kind())
    return a


def make_conda_pip_envs():
    import json
    import doit
    file = dgaf.File("environment.yml") or dgaf.File("environment.yaml")
    file or make_prior_env()
    reqs = dgaf.File("requirements.txt")
    reqs.touch()
    env = file.load()
    if not env.get("dependencies", []):
        return
    cmd = doit.tools.CmdAction(
        " ".join(["conda install --dry-run --json"]+[
            x for x in env.get("dependencies", []) if isinstance(x, str)]))
    cmd.execute()
    result = json.loads(cmd.out)
    if "success" in result:
        ...
    if "error" in result:
        if result.get("packages"):
            reqs = dgaf.File("requirements.txt")
            reqs.write_text("\n".join(set(filter(str.strip, reqs.read_text().splitlines())).union(
                result['packages'])))

            env["dependencies"] = [
                x for x in env["dependencies"] if x not in result["packages"]
            ]
            for dep in env["dependencies"]:
                if isinstance(dep, dict) and "pip" in dep:
                    pip = dep
            else:
                pip = dict(pip=[])
                env["dependencies"].append(pip)
            pip["pip"] = list(set(pip["pip"]).union(result["packages"]))

            if "pip" not in env["dependencies"]:
                env["dependencies"] += ["pip"]

            env["dependencies"] = list(set(x for x in env["dependencies"]
                                           if isinstance(x, str))) + [pip]

            file.dump(env)


def make_prior_env():
    """create and write conda environment file."""
    dependencies = depfinder()
    channels = ['conda-forge']
    file = dgaf.File("environment.yml") or dgaf.File("environment.yaml")

    if any(x in dependencies for x in ("panel", "holoviews", "hvplot")):
        channels = ['pyviz'] + channels

    file.dump(
        dgaf.merge(file.load(), dict(name="notebook", channels=channels,
                                     dependencies=list(dependencies)))
    )


def make_pyproject():
    import git
    author = git.Repo().commit().author

    metadata = dgaf.dodo.PYPROJECT.get(
        "tool", {}).get("flit", {}).get("metadata", {})
    metadata["module"] = metadata.get("module", "") or "readme"
    metadata["author"] = metadata.get("author", "") or author.name
    metadata["author-email"] = metadata.get("author", "") or author.email
    metadata["homepage"] = "http://"
    # add requirements
    dgaf.File("pyproject.toml").dump(dgaf.dodo.PYPROJECT)


def depfinder() -> set:
    """Find the dependencies for all of the content."""
    import depfinder
    object = {}
    deps = set()
    for file in dgaf.File().iterdir():
        deps = deps.union(file.imports())
    deps.discard('dgaf')
    return deps


def typer_to_doit(app):
    app.registered_commands()
    for command in commands:
        returns = command.callback.__annotations__.get("return", [])

        # the return annotation only gets complication if it is a tuple.
        if isinstance(returns, tuple):
            # def f()-> (..., "foo.txt")
            # def g()-> ("foo.txt", ["bar.txt"])
            # def h()-> (["foo.txt", g], [])
            file_deps, targets = returns
        else:
            file_deps, targets = [], returns
        if not isinstance(file_deps, list):
            file_deps = [file_deps]

        if not isinstance(targets, list):
            targets = [targets]

        file_deps == [...] and file_deps.pop()
        targets == [...] and targets.pop()

        task_deps = []
        # split callable tasks from file dependencies
        for file_dep in file_deps:
            if callable(file_dep):
                task_deps += [file_dep.__name__]

        # do something about globs
        ...

        # pop tasks from the file deps
        if task_deps:
            for task_dep in task_deps:
                try:
                    file_deps.pop(file_deps.index(task_dep))
                except ValueError:
                    ...

        # decorate the function according to the doit specification
        command.callback.create_doit_tasks = lambda: dict(
            actions=[command.callback],
            file_deps=file_deps,
            task_deps=task_deps,
            targets=targets
        )
