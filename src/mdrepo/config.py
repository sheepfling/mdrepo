"""Typed configuration loading for the focused repository policy tool."""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from mdrepo.models import OutputFormat, Severity

_CONFIG_FILENAMES = ("pyproject.toml", "mdrepo.toml", ".mdrepo.toml")
_EXCEPTION_HEALTH_RULES = {"MDR201", "MDR202"}


class ConfigurationError(RuntimeError):
    """Raised when configuration cannot be discovered, decoded, or validated."""
####




def _to_kebab(value: str) -> str:
    return value.replace("_", "-")
####




class ConfigModel(BaseModel):
    """Strict base model with human-friendly kebab-case TOML aliases."""

    model_config = ConfigDict(
        alias_generator=_to_kebab,
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )
####




class RepositoryProvider(str):
    """String constants accepted for repository web URL parsing."""

    AUTO = "auto"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
####




class RuleSelectionConfig(ConfigModel):
    """Rule selection and severity overrides."""

    select: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)
    severity: dict[str, Severity] = Field(default_factory=dict)

    @field_validator("select", "ignore")
    @classmethod
    def _normalize_rule_lists(cls, values: list[str]) -> list[str]:
        return _normalize_rule_ids(values)
    ####


    @field_validator("severity")
    @classmethod
    def _normalize_severity_keys(cls, values: dict[str, Severity]) -> dict[str, Severity]:
        return {key.strip().upper(): value for key, value in values.items()}
    ####
####





class LinkConfig(ConfigModel):
    """Portable local-link behavior not owned by a formatter."""

    require_posix: bool = True
    allow_root_relative: bool = False
    allow_outside_root: bool = False
    check_missing_targets: bool = False
    check_case: bool = True
####




class RepositoryConfig(ConfigModel):
    """Same-repository web-link detection."""

    enabled: bool = True
    url: str | None = None
    discover_from_git: bool = True
    remote: str = "origin"
    provider: str = RepositoryProvider.AUTO
    relative_refs: list[str] = Field(default_factory=lambda: ["main", "master"])
    include_current_branch: bool = True
    require_existing_target: bool = True

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {
            RepositoryProvider.AUTO,
            RepositoryProvider.GITHUB,
            RepositoryProvider.GITLAB,
            RepositoryProvider.BITBUCKET,
        }
        if normalized not in allowed:
            raise ValueError(f"provider must be one of {sorted(allowed)}")
        ####
        return normalized
    ####


    @field_validator("relative_refs")
    @classmethod
    def _normalize_refs(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip().strip("/")
            if item and item not in normalized:
                normalized.append(item)
            ####
        ####
        return normalized
    ####
####





class OrphanConfig(ConfigModel):
    """Rooted documentation-graph behavior."""

    enabled: bool = False
    roots: list[str] = Field(default_factory=lambda: ["README.md", "docs/index.md"])
    markdown_extensions: list[str] = Field(default_factory=lambda: [".md", ".markdown"])
    extensionless_links: bool = True
    directory_indexes: list[str] = Field(default_factory=lambda: ["README.md", "index.md"])

    @field_validator("markdown_extensions")
    @classmethod
    def _normalize_extensions(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip().lower()
            if not item:
                continue
            ####
            if not item.startswith("."):
                item = f".{item}"
            ####
            if item not in normalized:
                normalized.append(item)
            ####
        ####
        if not normalized:
            raise ValueError("at least one Markdown extension is required")
        ####
        return normalized
    ####
####





class ExceptionPolicyConfig(ConfigModel):
    """Health reporting for structured exceptions."""

    report_expired: bool = True
    report_unused: bool = True
    expired_severity: Severity = Severity.WARNING
    unused_severity: Severity = Severity.WARNING
####




class ExceptionConfig(ConfigModel):
    """One documented, narrow policy exception."""

    id: str = Field(min_length=1)
    rule: str = Field(pattern=r"^MDR\d{3}$")
    path: str = "**"
    target: str | None = None
    reason: str = Field(min_length=8)
    expires: date | None = None

    @field_validator("id", "path", "reason")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        ####
        return normalized
    ####


    @field_validator("rule")
    @classmethod
    def _normalize_rule(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized in _EXCEPTION_HEALTH_RULES:
            raise ValueError("exception-health diagnostics cannot themselves be excepted")
        ####
        return normalized
    ####


    @field_validator("target")
    @classmethod
    def _strip_optional_target(cls, value: str | None) -> str | None:
        if value is None:
            return None
        ####
        normalized = value.strip()
        return normalized or None
    ####
####





class ApplicationConfig(ConfigModel):
    """Complete configuration for one repository run."""

    include: list[str] = Field(default_factory=lambda: ["*.md", "**/*.md"])
    exclude: list[str] = Field(
        default_factory=lambda: [
            ".git/**",
            ".venv/**",
            "build/**",
            "dist/**",
            "site/**",
        ]
    )
    encoding: str = "utf-8"
    output: OutputFormat = OutputFormat.TEXT
    fail_on: Severity = Severity.ERROR
    rules: RuleSelectionConfig = Field(default_factory=RuleSelectionConfig)
    links: LinkConfig = Field(default_factory=LinkConfig)
    repository: RepositoryConfig = Field(default_factory=RepositoryConfig)
    orphans: OrphanConfig = Field(default_factory=OrphanConfig)
    exception_policy: ExceptionPolicyConfig = Field(default_factory=ExceptionPolicyConfig)
    exceptions: list[ExceptionConfig] = Field(default_factory=lambda: list[ExceptionConfig]())

    @model_validator(mode="after")
    def _validate_exception_ids(self) -> ApplicationConfig:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for exception in self.exceptions:
            if exception.id in seen:
                duplicates.add(exception.id)
            ####
            seen.add(exception.id)
        ####
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise ValueError(f"exception IDs must be unique; duplicates: {joined}")
        ####
        return self
    ####
####





@dataclass(frozen=True, slots=True)
class LoadedConfig:
    """Validated configuration plus discovery provenance."""

    root: Path
    model: ApplicationConfig
    raw: dict[str, Any]
    sources: tuple[Path, ...]
####




def load_configuration(
    *,
    cwd: Path,
    root_override: Path | None,
    config_paths: list[Path],
    overrides: list[str],
) -> LoadedConfig:
    """Discover, merge, override, and validate repository configuration."""

    explicit_paths = tuple(path.expanduser().resolve() for path in config_paths)
    root = _resolve_root(
        cwd=cwd.resolve(),
        root_override=root_override,
        explicit_paths=explicit_paths,
    )
    discovered_paths = _config_paths_at_root(root)

    ordered_paths: list[Path] = []
    for path in (*discovered_paths, *explicit_paths):
        if path not in ordered_paths:
            ordered_paths.append(path)
        ####
    ####

    merged: dict[str, Any] = {}
    loaded_sources: list[Path] = []
    for path in ordered_paths:
        if not path.exists():
            raise ConfigurationError(f"configuration file does not exist: {path}")
        ####
        section = _read_config_section(path)
        if section is None:
            continue
        ####
        merged = deep_merge(merged, section)
        loaded_sources.append(path)
    ####

    for expression in overrides:
        key, value = parse_override(expression)
        set_dotted_value(merged, key, value)
    ####

    try:
        model = ApplicationConfig.model_validate(merged)
    except ValidationError as error:
        raise ConfigurationError(f"invalid mdrepo configuration:\n{error}") from error
    ####
    _validate_known_rule_ids(model)

    return LoadedConfig(
        root=root,
        model=model,
        raw=copy.deepcopy(merged),
        sources=tuple(loaded_sources),
    )
####




def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge tables; lists and scalar values replace earlier values."""

    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(
                cast(dict[str, Any], current),
                cast(dict[str, Any], value),
            )
        else:
            merged[key] = copy.deepcopy(value)
        ####
    ####
    return merged
####




def parse_override(expression: str) -> tuple[str, Any]:
    """Parse ``dotted.key=TOML_VALUE`` with a string fallback."""

    key, separator, raw_value = expression.partition("=")
    if not separator or not key.strip():
        raise ConfigurationError(
            f"configuration override must have the form KEY=VALUE: {expression!r}"
        )
    ####

    normalized_key = key.strip()
    normalized_value = raw_value.strip()
    if not normalized_value:
        return normalized_key, ""
    ####

    try:
        value = tomllib.loads(f"value = {normalized_value}\n")["value"]
    except tomllib.TOMLDecodeError:
        value = normalized_value
    ####
    return normalized_key, value
####




def set_dotted_value(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a nested mapping value, creating intermediate tables as needed."""

    parts = [part.strip().replace("_", "-") for part in dotted_key.split(".")]
    if any(not part for part in parts):
        raise ConfigurationError(f"invalid dotted configuration key: {dotted_key!r}")
    ####

    current = target
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ConfigurationError(
                f"cannot set {dotted_key!r}: {part!r} is not a configuration table"
            )
        ####
        current = cast(dict[str, Any], child)
    ####
    current[parts[-1]] = value
####




def _validate_known_rule_ids(config: ApplicationConfig) -> None:
    from mdrepo.rules import RULES_BY_ID

    known = set(RULES_BY_ID)
    configured = {
        *config.rules.select,
        *config.rules.ignore,
        *config.rules.severity,
        *(exception.rule for exception in config.exceptions),
    }
    unknown = sorted(configured - known)
    if unknown:
        raise ConfigurationError(f"unknown mdrepo rule ID(s): {', '.join(unknown)}")
    ####
####




def _normalize_rule_ids(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        for item in value.split(","):
            rule_id = item.strip().upper()
            if rule_id and rule_id not in normalized:
                normalized.append(rule_id)
            ####
        ####
    ####
    return normalized
####




def _resolve_root(
    *,
    cwd: Path,
    root_override: Path | None,
    explicit_paths: tuple[Path, ...],
) -> Path:
    if root_override is not None:
        root = root_override.expanduser().resolve()
        if not root.is_dir():
            raise ConfigurationError(f"project root is not a directory: {root}")
        ####
        return root
    ####

    if explicit_paths:
        return explicit_paths[0].parent
    ####

    discovered = _discover_root(cwd)
    return discovered or cwd
####




def _discover_root(start: Path) -> Path | None:
    git_fallback: Path | None = None
    for directory in (start, *start.parents):
        if git_fallback is None and (directory / ".git").exists():
            git_fallback = directory
        ####

        if (directory / "mdrepo.toml").is_file() or (directory / ".mdrepo.toml").is_file():
            return directory
        ####

        pyproject = directory / "pyproject.toml"
        if pyproject.is_file() and _pyproject_has_section(pyproject):
            return directory
        ####
    ####
    return git_fallback
####




def _config_paths_at_root(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for filename in _CONFIG_FILENAMES:
        path = root / filename
        if not path.is_file():
            continue
        ####
        if filename == "pyproject.toml" and not _pyproject_has_section(path):
            continue
        ####
        paths.append(path)
    ####
    return tuple(paths)
####




def _pyproject_has_section(path: Path) -> bool:
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return False
    ####
    tool = parsed.get("tool")
    return isinstance(tool, dict) and isinstance(cast(dict[str, Any], tool).get("mdrepo"), dict)
####




def _read_config_section(path: Path) -> dict[str, Any] | None:
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationError(f"unable to read configuration {path}: {error}") from error
    except UnicodeError as error:
        raise ConfigurationError(f"configuration is not UTF-8 text: {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"invalid TOML in {path}: {error}") from error
    ####

    tool = parsed.get("tool")
    if isinstance(tool, dict) and "mdrepo" in tool:
        section = cast(dict[str, Any], tool)["mdrepo"]
        if not isinstance(section, dict):
            raise ConfigurationError(f"[tool.mdrepo] must be a table in {path}")
        ####
        return copy.deepcopy(cast(dict[str, Any], section))
    ####

    if "mdrepo" in parsed:
        section = parsed["mdrepo"]
        if not isinstance(section, dict):
            raise ConfigurationError(f"[mdrepo] must be a table in {path}")
        ####
        return copy.deepcopy(cast(dict[str, Any], section))
    ####

    if path.name == "pyproject.toml":
        return None
    ####
    return copy.deepcopy(parsed)
####


