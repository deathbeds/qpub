"""q(uick) p(ubishing) configures python distribution and documentaton tools.

"""
#    ___    ____      _   _    ____
#   / " \ U|  _"\ uU |"|u| |U | __")u
#  | |"| |\| |_) |/ \| |\| | \|  _ \/
# /| |_| |\|  __/    | |_| |  | |_) |
# U \__\_\u|_|      <<\___/   |____/
#    \\//  ||>>_   (__) )(   _|| \\_
#   (_(__)(__)__)      (__) (__) (__)

__version__ = __import__("datetime").date.today().strftime("%Y.%m.%d")
import os
import pathlib
import typing
import re
import dataclasses
import itertools
from . import util
from .exceptions import *
from .util import Path, File, Convention, cached

post_pattern = re.compile("^[0-9]{4}-[0-9]{2}-[0-9]{2}")


class options:
    """options for qpub

    options are passed to doit using environment variables in nox."""

    python: str = os.environ.get("QPUB_PYTHON", "infer")
    conda: bool = os.environ.get("QPUB_CONDA", False)
    generate_types: bool = os.environ.get("QPUB_GENERATE_TYPES", False)
    docs: str = os.environ.get("QPUB_GENERATE_TYPES", "infer")
    pdf: bool = os.environ.get("QPUB_DOCS_PDF", False)
    doit: bool = os.environ.get("QPUB_DOIt", False)
    watch: bool = os.environ.get("QPUB_DOCS_WATCH", False)
    serve: bool = os.environ.get("QPUB_SERVE", False)
    pep517: bool = os.environ.get("QPUB_PEP517", False)

    @classmethod
    def dump(cls):
        return {f"QPUB_{x.upper()}": str(getattr(cls, x)) for x in cls.__annotations__}


# ███████╗██╗██╗     ███████╗     ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗███╗   ██╗████████╗██╗ ██████╗ ███╗   ██╗███████╗
# ██╔════╝██║██║     ██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝████╗  ██║╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝
# █████╗  ██║██║     █████╗      ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██╔██╗ ██║   ██║   ██║██║   ██║██╔██╗ ██║███████╗
# ██╔══╝  ██║██║     ██╔══╝      ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║   ██║   ██║██║   ██║██║╚██╗██║╚════██║
# ██║     ██║███████╗███████╗    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║ ╚████║   ██║   ██║╚██████╔╝██║ ╚████║███████║
# ╚═╝     ╚═╝╚══════╝╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝


DOIT_DB_DAT = Convention(".doit.db.dat")
DOIT_DB_DIR = DOIT_DB_DAT.with_suffix(".dir")
DOIT_DB_BAK = DOIT_DB_DAT.with_suffix(".bak")

PRECOMMITCONFIG_YML = Convention(".pre-commit-config.yaml")
PYPROJECT_TOML = Convention("pyproject.toml")
REQUIREMENTS_TXT = Convention("requirements.txt")
SETUP_CFG = Convention("setup.cfg")
SETUP_PY = Convention("setup.py")
SRC = Convention("src")
GIT = Convention(".git")
GITIGNORE = Convention(".gitignore")
DOCS = Convention("docs")
BUILD = DOCS / "_build"  # abides the sphinx gitignore convention.
TOC = DOCS / "_toc.yml"
CONFIG = DOCS / "_config.yml"
CONF = Convention("conf.py")
CONFTEST = Convention("conftest.py")
NOXFILE = Convention("noxfile.py")
DODO = Convention("dodo.py")
POETRY_LOCK = Convention("poetry.lock")
MKDOCS = Convention("mkdocs.yml")  # https://www.mkdocs.org/

MANIFEST = Convention("MANIFEST.in")
ENVIRONMENT_YML = Convention("environment.yml")
ENVIRONMENT_YAML = Convention("environment.yaml")
GITHUB = Convention(".github")
WORKFLOWS = GITHUB / "workflows"
CONVENTIONS = [x for x in locals().values() if isinstance(x, Convention)]

BUILDSYSTEM = "build-system"


# the cli program stops here. there rest work for the tasks
# in the sections below we define tasks to configure distribution


@dataclasses.dataclass(order=True)
class Chapter:
    dir: pathlib.Path = ""
    index: None = None
    repo: object = None
    parent: object = None
    docs: object = None
    posts: list = dataclasses.field(default_factory=list)
    pages: list = dataclasses.field(default_factory=list)
    modules: list = dataclasses.field(default_factory=list)
    tests: list = dataclasses.field(default_factory=list)
    src: object = None
    chapters: list = dataclasses.field(default_factory=list)
    _chapters: list = dataclasses.field(default_factory=list)
    conventions: list = dataclasses.field(default_factory=list, repr=False)
    hidden: list = dataclasses.field(default_factory=list, repr=False)
    exclude: object = None

    def __post_init__(self):
        if not isinstance(self.dir, pathlib.Path):
            self.dir = pathlib.Path(self.dir)
        self.repo = (
            (self.dir / GIT).exists() and __import__("git").Repo(self.dir / GIT) or None
        )
        pathspec = __import__("pathspec")
        self.exclude = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern,
            self.get_exclude_patterns() + [".git"],
        )
        contents = (
            self.repo
            and list(map(File, __import__("git").Git(self.dir).ls_files().splitlines()))
            or None
        )

        for parent in contents or []:
            if parent.parent not in contents:
                contents += [parent.parent]

        for file in self.dir.iterdir():
            local = file.relative_to(self.dir)
            if contents is not None:
                if local not in contents:
                    continue

            if local in {DOCS}:
                self.docs = Project(dir=file, parent=self)
            elif local in {SRC}:
                self.src = SRC
                self.chapters += [x for x in file.iterdir() if x.is_dir()]
            elif local in CONVENTIONS:
                self.conventions += [file]
            elif local.stem.startswith((".",)):
                self.hidden += [file]
            elif file.is_dir():
                if self.exclude.match_file(local / ".tmp"):
                    ...
                else:
                    self.chapters += [file]
                continue
            elif local.stem.startswith(("_",)):
                if local.stem.endswith("_"):
                    self.modules += [file]
                else:
                    self.hidden += [file]
            elif self.exclude.match_file(local):
                continue
            elif file.suffix not in {".ipynb", ".md", ".rst", ".py"}:
                continue
            elif file.stem.lower() in {"readme", "index"}:
                self.index = file
            elif post_pattern.match(file.stem):
                self.posts += [file]
            elif util.is_pythonic(file.stem):
                if file.stem.startswith("test_"):
                    self.tests += [file]
                else:
                    self.modules += [file]
            else:
                self.pages += [file]

        for k in "chapters posts tests modules pages conventions".split():
            setattr(self, k, sorted(getattr(self, k), reverse=k in {"posts"}))

        self._chapters = list(Project(dir=x, parent=self) for x in self.chapters)

    def root(self):
        return self.parent.root() if self.parent else self

    def files(
        self, content=False, posts=False, docs=False, tests=False, conventions=False
    ):
        if self.index:
            yield self.index
        if posts:
            yield from self.posts
        if docs:
            yield from self.pages
            if self.docs:
                yield from self.docs.files(
                    content=content,
                    posts=posts,
                    docs=docs,
                    tests=tests,
                    conventions=conventions,
                )
        if content:
            yield from self.modules
        if tests:
            yield from self.tests
        for chapter in self._chapters:
            yield from chapter.files(
                content=content,
                posts=posts,
                docs=docs,
                tests=tests,
                conventions=conventions,
            )
        if conventions:
            yield from self.conventions

    @property
    def path(self):
        return File(self.dir)

    def __truediv__(self, object):
        return self.path / object


class Distribution(Chapter):
    @cached
    def get_name(self):
        """get the project name"""

        # get the name of subdirectories if there are any.
        if self.chapters:
            if SRC in self.chapters:
                self.src = Project(self.dir / SRC, parent=self)
                return self.src.get_name()
            if len(self.chapters) == 1:
                return self.chapters[0].stem

        # get the name of modules if there are any.
        if self.modules:
            if len(self.modules) == 1:
                return self.modules[0].stem
            else:
                raise BaseException

        # look for dated posted
        if self.posts:
            if len(self.posts) == 1:
                return self.posts[0].stem.split("-", 3)[-1].replace(*"-_")

        # look for pages.
        if self.pages:
            if len(self.pages) == 1:
                return self.pages[0].stem
        raise BaseException

    @cached
    def get_description(self):
        """get from the docstring of the project. raise an error if it doesn't exist."""

        # look in modules/chapters to see if we can flit this project.
        if self.is_flit():
            flit = __import__("flit")
            return flit.common.get_info_from_module(self._flit_module).pop("summary")

        if self.src:
            return self.src.get_description()

        return ""

    @cached
    def get_version(self):
        """determine a version for the project, if there is no version defer to calver.

        it would be good to support semver, calver, and agever (for blogs).
        """
        # use the flit convention to get the version.
        # there are a bunch of version convention we can look for bumpversion, semver, rever
        # if the name is a post name then infer the version from there
        if self.is_flit():
            flit = __import__("flit")
            return flit.common.get_info_from_module(self._flit_module).pop("version")

        if self.src:
            return self.src.get_version()

        return __import__("datetime").date.today().strftime("%Y.%m.%d")

    @cached
    def get_exclude_patterns(self):
        """get the excluded patterns for the current layout"""
        return list(sorted(set(dict(self._iter_exclude()).values())))

    @cached
    def get_exclude_paths(self):
        """get the excluded path by the canonical python.gitignore file."""
        return list(sorted(dict(self._iter_exclude())))

    def _iter_exclude(self, files=None):
        for x in files or itertools.chain(
            self.dir.iterdir(),
            (self.docs.files(True, True, True, True, True) if self.docs else tuple()),
        ):
            if x.is_dir():
                x /= "tmp"

            exclude = self.get_exclude_by(x.relative_to(self.root().dir))
            if exclude:
                yield x, exclude

    def get_exclude_by(self, object):
        """return the path that ignores an object.

        exclusion is based off the canonical python.gitignore specification."""
        if not hasattr(self, "gitignore_patterns"):
            self._init_exclude()

        for k, v in self.gitignore_patterns.items():
            if any(v.match((str(object),))):
                return k
        else:
            return None

    def _init_exclude(self):
        """initialize the path specifications to decide what to omit."""

        self.gitignore_patterns = {}
        for file in (
            Path(__file__).parent / "templates" / "Python.gitignore",
            Path(__file__).parent / "templates" / "Nikola.gitignore",
            Path(__file__).parent / "templates" / "JupyterNotebooks.gitignore",
        ):
            for pattern in (
                file.read_text().splitlines()
                + ".local .vscode _build .gitignore".split()
            ):
                if bool(pattern):
                    match = __import__("pathspec").patterns.GitWildMatchPattern(pattern)
                    if match.include:
                        self.gitignore_patterns[pattern] = match

    @cached
    def get_author(self):
        if self.repo:
            return self.repo.commit().author.name
        return "dgaf"

    @cached
    def get_email(self):
        if self.repo:
            return self.repo.commit().author.email
        return ""

    @cached
    def get_url(self):
        if self.repo:
            if hasattr(self.repo.remotes, "origin"):
                return self.repo.remotes.origin.url
        return ""

    get_exclude = get_exclude_patterns

    @cached
    def get_classifiers(self):
        """some classifiers can probably be inferred."""
        return []

    @cached
    def get_license(self):
        """should be a trove classifier"""
        # import trove_classifiers

        # infer the trove framework
        # make a gui for adding the right classifiers.
        "I dont know what the right thing is to say here."
        return ""

    @cached
    def get_keywords(self):
        return []

    def get_python_version(self):
        import sys

        return f"{sys.version_info.major}.{sys.version_info.minor}"

    @cached
    def get_test_files(self, default=True):
        """list the test like files. we'll access their dependencies separately ."""
        if default:
            return list(self.files(tests=True))
        items = util.collect_test_files(self.path)
        return items

    @cached
    def get_docs_files(self, default=True):
        """list the test like files. we'll access their dependencies separately ."""
        if default:
            return list(self.files(docs=True))
        items = util.collect_test_files(self.path)
        return items

    def get_untracked_files(self):
        if self.repo:
            self.repo.untracked_files
        return []

    @cached
    def get_description_file(self):
        """get the description file for a project. it looks like readme or index something."""
        if self.index and self.index.stem.lower() in {"readme", "index"}:
            return self.index

    @cached
    def get_description_content_type():
        """get the description file for a project. it looks like readme or index something."""
        file = self.get_description_file()
        return {".md": "text/markdown", ".rst": "text/x-rst"}.get(
            file and file.suffix.lower() or None, "text/plain"
        )

    @cached
    def get_long_description(self, expand=False):
        file = self.get_description_file()
        if expand:
            return file.read_text()
        return f"file: {file}" if file else ""

    def get_requires_from_files(self, files):
        """list imports discovered from the files."""
        return list(set(util.import_to_pip(util.merged_imports(files))))

    def get_requires_from_requirements_txt(self):
        """get any hardcoded dependencies in requirements.txt."""
        if (self / REQUIREMENTS_TXT).exists():
            known = [
                x
                for x in REQUIREMENTS_TXT.read_text().splitlines()
                if not x.lstrip().startswith("#") and x.strip()
            ]
            return list(
                __import__("packaging.requirements")
                .requirements.Requirement.parseString(x)
                .name
                for x in known
            )

        return []

    @cached
    def get_requires(self):
        """get the requirements for the project.

        use heuristics that investigate a few places where requirements may be specified.

        the expectation is that pip requirements might be pinned in a requirements file
        or anaconda environment file.
        """
        known = self.get_requires_from_requirements_txt()

        known.append(self.get_name())
        return sorted(
            [
                package
                for package in self.get_requires_from_files(self.files(content=True))
                if package.lower() not in known and package[0].isalpha()
            ]
        )

    @cached
    def get_test_requires(self):
        """test requires live in test and docs folders."""

        requires = ["pytest", "pytest-sugar"]
        if ".ipynb" in self.suffixes:
            requires += ["nbval", "importnb"]
        requires += self.get_requires_from_files(
            self / x for x in self.get_test_files()
        )
        return [x for x in requires if x not in [self.get_name()]]

    @cached
    def get_doc_requires(self):
        """test requires live in test and docs folders."""

        # infer the sphinx extensions needed because we miss this often.
        if CONF in self.conventions:
            "infer the dependencies from conf.py."
        requires = []
        if options.docs == "jb":
            requires += ["jupyter-book"]
        if self.docs:
            requires += self.get_requires_from_files(self.docs.files)
        return requires

    def is_flit(self):
        """does the module abide flit conventions:

        1. is the python script or folder with a name
        2. can the description and version be inferred

        """

        flit = __import__("flit")

        try:
            setattr(
                self,
                "_flit_module",
                getattr(
                    self,
                    "_flit_module",
                    flit.common.Module(self.get_name(), self.root().dir),
                ),
            )

            return True
        except ValueError:
            return False

    def is_poetry(self):
        """is the project otherwise a poetry project"""

        return bool(not self.is_flit()) and bool(self.chapters)

    def is_setuptools(self):
        """is the project otherwise a poetry project"""

        return True

    def python_backend(self):
        return (
            "flit" if self.is_flit() else "poetry" if self.is_poetry() else "setuptools"
        )

    def docs_backend(self):
        return "jb"

    def __call__(self):
        ...


class Build(Distribution):
    @classmethod
    def create_doit_tasks(cls):
        self = cls()
        if self.is_flit():
            return dict(actions=[f"flit build"])
        if self.is_poetry():
            return dict(actions=[f"poetry build"])
        if self.is_setuptools():
            return dict(actions=[f"python setup.py sdist bdist_wheel"])
        raise BaseException


class Install(Distribution):
    def tasks(self):
        return dict(name="pip-install", actions=[f"pip install ."])


class Project(Distribution):
    """the Project class provides a consistent interface for inferring project features from
    the content of directories and git repositories.

    """

    @property
    def suffixes(self):
        return sorted(set(x.suffix for x in self.files(True, True, True, True, True)))

    def as_toc(self, recurse=False):
        index = self.index
        if index is None:
            for object in (self.pages, self.posts, self.tests, self.modules):
                if object:
                    index = object[0]
                    break
        if not index:
            raise NoIndex()
        data = dict(file=str(index.with_suffix("")), sections=[])
        for x in itertools.chain(
            self.pages,
            (self.docs,) if self.docs else (),
            self.posts,
            self.tests,
            self.modules,
            self.chapters,
        ):
            if x == index:
                continue
            if self.docs and (x == self.docs):
                try:
                    data["sections"].append(self.docs.as_toc(recurse))
                except NoIndex:
                    ...
            elif x in self.chapters:
                try:
                    data["sections"].append(
                        self._chapters[self.chapters.index(x)].as_toc(recurse)
                    )
                except NoIndex:
                    ...
            else:
                data["sections"].append(dict(file=str(x.with_suffix(""))))

        return data

    def to_pre_commit(self):
        """from the suffixes in the content, fill out the precommit based on our opinions."""
        precommit = self / PRECOMMITCONFIG_YML
        data = precommit.load() or {}
        if "    @cachedrepos" not in data:
            data["repos"] = []

        for suffix in [None] + self.suffixes:
            if suffix in util.LINT_DEFAULTS:
                for kind in util.LINT_DEFAULTS[suffix]:
                    for repo in data["repos"]:
                        if repo["repo"] == kind["repo"]:
                            repo["rev"] = repo.get("rev", None) or kind.get("rev", None)

                            ids = set(x["id"] for x in kind["hooks"])
                            repo["hooks"] = repo["hooks"] + [
                                x for x in kind["hooks"] if x["id"] not in ids
                            ]
                            break
                    else:
                        data["repos"] += [dict(kind)]

        precommit.dump(data)

    def serialize(self, infer=False):
        url = self.get_url()
        if url.endswith(".git"):
            url = url[:-4]
        exclude = map(str, self.get_exclude())
        exclude = [x[:-1] if x.endswith("/") else x for x in exclude]

        data = dict(
            name=self.get_name(),
            version=self.get_version(),
            url=url,
            author=self.get_author(),
            email=self.get_email(),
            classifiers=self.get_classifiers(),
            license=self.get_license(),
            description=self.get_description(),
            long_description=str(self.get_description_file()),
            keywords=self.get_keywords(),
            platforms=[],
            python_version=self.get_python_version(),
            exclude=exclude,
        )

        if infer:
            data.update(
                requires=self.get_requires(),
                test_requires=self.get_test_requires(),
                docs_requires=self.get_doc_requires(),
            )

        return data

    def as_flit(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "flit.json").read_text()
            ),
            self.serialize(True),
        )

    def to_flit(self):
        data = self.as_flit()
        data = util.merge(
            self.as_pytest(),
            {BUILDSYSTEM: data.pop(BUILDSYSTEM)},
            (self / PYPROJECT_TOML).load(),
            data,
        )
        (self / PYPROJECT_TOML).write(data)
        name = data["tool"]["flit"]["metadata"]["module"]
        version = self.get_version()
        adds = [self / PYPROJECT_TOML]
        # the case where isnt any python source.
        if not ((self / name).exists() or (self / name).with_suffix(".py").exists()):
            (self / name).with_suffix(".py").write_text(
                f"""
"{name}"
__version__ = "{version}"
with __import__("importnb").Notebook():
    from {name} import *\n"""
            )

    def to_toc_yml(self):
        """

        book > part > chapter > section

        there are two conventions for jupyter book:
        1. using sections
        2. using files

        """
        (self / TOC).write(self.as_toc(True))

    def as_config(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "_config.json").read_text()
            ),
            self.serialize(),
        )

    def to_config_yml(self):
        """configure the book project once and never again.

        https://jupyterbook.org/customize/config.html

        """
        (self / CONFIG).write(self.as_config())

    def to_setup_py(self):
        (self / SETUP_PY).write_text("""__import__("setuptools").setup()""")

    def as_setuptools(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "setuptools.json").read_text()
            ),
            self.serialize(True),
        )

    def to_setuptools(self):
        data = self.as_setuptools()
        data = util.merge((self / SETUP_CFG).load(), data)
        (self / SETUP_CFG).write(data)

    def as_poetry(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "poetry.json").read_text()
            ),
            self.serialize(),
        )

    def as_pytest(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "pytest.json").read_text()
            ),
            self.serialize(),
        )

    def to_poetry(self):
        """configuration for poetry

        https://python-poetry.org/docs/pyproject/"""

        data = self.as_poetry()
        data = util.merge(
            self.as_pytest(),
            {BUILDSYSTEM: data.pop(BUILDSYSTEM)},
            (self / PYPROJECT_TOML).load(),
            data,
        )
        (self / PYPROJECT_TOML).write(data)

    def to_pytest_config(self):
        return dict(
            addopts="-s",
            norecursedirs=" ".join(map(str, self.get_exclude())),
            minversion="6.2",
        )

    def to_gitignore(self):
        (self / GITIGNORE).write_text("\n".join(map(str, self.get_exclude())))

    def to_manifest(self):
        (self / MANIFEST).write_text(
            " ".join(
                map(str, ["include"] + list(self.files(True, True, True, True, True)))
            )
        )

    def to_github_action(self):
        """create a github actions to publish dgaf actionss"""

    def to_readthedocs(self):
        """configure a read the docs deployment with dgaf."""

    def to_requirements(self):
        """write a requirements file."""
        (self / REQUIREMENTS_TXT).update

    def to_conda_environment(self):
        """export a conda environment file."""

    def to_doit(self):
        """make a dodo.py file"""

    def to_nox(self):
        """make a noxfile.py file"""

    def to_readthedocs(self):
        """https://docs.readthedocs.io/en/stable/config-file/v2.html"""

    def to_whl(self):
        return "dgaf-2020.12.29-py3-none-any.whl"

    def to_sdist(self):
        return "qpub-2020.12.01.tar.gz"

    def as_pyproject(self):
        if self.is_flit():
            return self.as_flit()
        if self.is_poetry():
            return self.as_poetry()
        return self.as_setuptools()

    def as_docs(self):
        if self.is_flit():
            return self.as_flit()
        if self.is_poetry():
            return self.as_poetry()
        return self.as_setuptools()


# ███████╗██╗███╗   ██╗
# ██╔════╝██║████╗  ██║
# █████╗  ██║██╔██╗ ██║
# ██╔══╝  ██║██║╚██╗██║
# ██║     ██║██║ ╚████║
# ╚═╝     ╚═╝╚═╝  ╚═══╝


class Flit(Project):
    """flit projects are discovered when a python script
    or directory exists with docstring and version."""

    def develop(self):
        return dict()

    def configure(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "flit.json").read_text()
            ),
            self.serialize(True),
        )


class Poetry(Project):
    def develop(self):
        ...

    def configure(self):
        return __import__("jsone").render(
            __import__("json").loads(
                (Path(__file__).parent / "templates" / "poetry.json").read_text()
            ),
            self.serialize(True),
        )

    def update(self):
        ...


class Setuptools(Project):
    def develop(self):
        ...

    def configure(self):
        ...


class JupyterBook(Project):
    def configure(self):
        ...

    def html(self):
        ...

    def pdf(self):
        ...


class Sphinx(Project):
    def configure(self):
        ...

    def html(self):
        ...

    def pdf(self):
        ...


class Mkdocs(Project):
    def configure(self):
        ...


class Nikola(Project):
    def configure(self):
        ...


class Pytest(Project):
    def configure(self):
        ...


class Github(Project):
    ...
