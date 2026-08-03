"""Local Git metadata and same-repository web URL interpretation."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

from mdrepo.config import ConfigurationError, RepositoryConfig, RepositoryProvider

_SCP_REMOTE: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)$"
)
_LINE_FRAGMENT: Final[re.Pattern[str]] = re.compile(r"^L\d+(?:-L?\d+)?$", re.IGNORECASE)

@dataclass(frozen=True, slots=True)
class RepositoryIdentity:
    """Normalized web identity for the checked Git repository."""

    web_url: str
    provider: str
    host: str
    base_path: str
    refs: tuple[str, ...]
    source: str
    port: int | None = None

@dataclass(frozen=True, slots=True)
class RemoteRepositoryTarget:
    """A web URL that maps to a file in the current repository."""

    repository_path: PurePosixPath
    ref: str
    query: str
    fragment: str
    line_fragment: bool

def discover_repository_identity(
        *,
        root: Path,
        config: RepositoryConfig,
) -> RepositoryIdentity | None:
    """Build repository identity from explicit config or local Git metadata."""

    if not config.enabled:
        return None

    source = "configuration"
    raw_url = config.url
    if raw_url is None and config.discover_from_git:
        raw_url = _git_output(root, "config", "--get", f"remote.{config.remote}.url")
        source = f"git remote {config.remote}"
    if raw_url is None:
        return None

    web_url = normalize_repository_url(raw_url)
    if web_url is None:
        return None
    parsed = urlsplit(web_url)
    provider = _resolve_provider(config.provider, parsed.hostname or "")
    if provider is None:
        return None

    refs = list(config.relative_refs)
    if config.include_current_branch and config.discover_from_git:
        current_branch = _git_output(root, "branch", "--show-current")
        if current_branch:
            refs.append(current_branch)
        remote_head = _git_output(
            root,
            "symbolic-ref",
            "--quiet",
            "--short",
            f"refs/remotes/{config.remote}/HEAD",
        )
        prefix = f"{config.remote}/"
        if remote_head and remote_head.startswith(prefix):
            refs.append(remote_head.removeprefix(prefix))

    normalized_refs = tuple(
        sorted(
            {ref.strip().strip("/") for ref in refs if ref.strip().strip("/")},
            key=lambda ref: (-len(ref), ref),
        )
    )
    return RepositoryIdentity(
        web_url=web_url,
        provider=provider,
        host=(parsed.hostname or "").lower(),
        base_path=parsed.path.rstrip("/"),
        refs=normalized_refs,
        source=source,
        port=_effective_web_port(parsed),
    )

def normalize_repository_url(raw_url: str) -> str | None:
    """Normalize common HTTPS, SSH, and SCP-like Git remotes to an HTTPS web URL."""

    normalized = raw_url.strip()
    if not normalized:
        return None

    scp_match = _SCP_REMOTE.fullmatch(normalized)
    if scp_match is not None and "://" not in normalized:
        host = scp_match.group("host")
        path = scp_match.group("path")
        normalized = f"https://{host}/{path}"

    try:
        parsed = urlsplit(normalized)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https", "ssh", "git"}:
        return None
    hostname = parsed.hostname
    if not hostname:
        return None

    try:
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError(f"invalid repository URL {raw_url!r}: {error}") from error
    netloc = hostname.lower()
    if port is not None and not (
            (parsed.scheme.lower() == "http" and port == 80)
            or (parsed.scheme.lower() in {"https", "ssh", "git"} and port in {22, 443})
    ):
        netloc = f"{netloc}:{port}"

    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path or path == "/":
        return None
    return urlunsplit(("https", netloc, path, "", ""))

def parse_same_repository_url(
        *,
        target: str,
        identity: RepositoryIdentity,
) -> RemoteRepositoryTarget | None:
    """Map a supported provider file URL back to a repository-relative path."""

    try:
        parsed = urlsplit(target)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    try:
        target_port = _effective_web_port(parsed)
    except ValueError:
        return None

    if identity.provider == RepositoryProvider.GITHUB:
        raw_target = _parse_github_raw(
            parsed=parsed,
            identity=identity,
            target_port=target_port,
        )
        if raw_target is not None:
            return raw_target

    if (parsed.hostname or "").lower() != identity.host or target_port != identity.port:
        return None
    decoded_path = unquote(parsed.path)
    route = _provider_route(identity.provider)
    if route is None:
        return None
    prefix = f"{identity.base_path}{route}"
    if not decoded_path.startswith(prefix):
        return None
    remainder = decoded_path[len(prefix):].lstrip("/")
    matched = _match_ref_and_path(remainder=remainder, refs=identity.refs)
    if matched is None:
        return None
    ref, repository_path = matched
    return RemoteRepositoryTarget(
        repository_path=repository_path,
        ref=ref,
        query=parsed.query,
        fragment=parsed.fragment,
        line_fragment=bool(_LINE_FRAGMENT.fullmatch(parsed.fragment)),
    )

def _parse_github_raw(
        *,
        parsed: SplitResult,
        identity: RepositoryIdentity,
        target_port: int | None,
) -> RemoteRepositoryTarget | None:
    if (
            identity.host != "github.com"
            or (parsed.hostname or "").lower() != "raw.githubusercontent.com"
            or target_port != identity.port
    ):
        return None

    base_parts = tuple(part for part in identity.base_path.split("/") if part)
    decoded_parts = tuple(part for part in unquote(parsed.path).split("/") if part)
    if len(base_parts) != 2 or decoded_parts[:2] != base_parts:
        return None
    remainder = "/".join(decoded_parts[2:])
    matched = _match_ref_and_path(remainder=remainder, refs=identity.refs)
    if matched is None:
        return None
    ref, repository_path = matched
    return RemoteRepositoryTarget(
        repository_path=repository_path,
        ref=ref,
        query=parsed.query,
        fragment=parsed.fragment,
        line_fragment=bool(_LINE_FRAGMENT.fullmatch(parsed.fragment)),
    )

def _provider_route(provider: str) -> str | None:
    if provider == RepositoryProvider.GITHUB:
        return "/blob/"
    if provider == RepositoryProvider.GITLAB:
        return "/-/blob/"
    if provider == RepositoryProvider.BITBUCKET:
        return "/src/"
    return None

def _effective_web_port(parsed: SplitResult) -> int | None:
    """Return a URL port while treating standard HTTP(S) ports as implicit."""

    port = parsed.port
    if port in {80, 443}:
        return None
    return port

def _match_ref_and_path(
        *,
        remainder: str,
        refs: tuple[str, ...],
) -> tuple[str, PurePosixPath] | None:
    for ref in refs:
        prefix = f"{ref}/"
        if not remainder.startswith(prefix):
            continue
        raw_path = remainder.removeprefix(prefix)
        path = PurePosixPath(raw_path)
        if not raw_path or path.is_absolute() or ".." in path.parts:
            return None
        return ref, path
    return None

def _resolve_provider(configured: str, hostname: str) -> str | None:
    if configured != RepositoryProvider.AUTO:
        return configured

    normalized = hostname.lower()
    if "github" in normalized:
        return RepositoryProvider.GITHUB
    if "gitlab" in normalized:
        return RepositoryProvider.GITLAB
    if "bitbucket" in normalized:
        return RepositoryProvider.BITBUCKET
    return None

def _git_output(root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None
