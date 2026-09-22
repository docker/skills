#!/usr/bin/env python3
"""Discover and validate hygiene rules for checked-in Compose YAML assets."""

import re
from collections.abc import Mapping
from pathlib import Path

import yaml

DATASTORE_PORTS = {5432, 3306, 6379, 27017, 11211, 5672, 9200}
SENSITIVE_SUFFIXES = ("PASSWORD", "PASSWD", "SECRET", "TOKEN", "API_KEY")
PASSWORD_FLAG_KEYS = {
    "MYSQL_ALLOW_EMPTY_PASSWORD",
    "MYSQL_RANDOM_ROOT_PASSWORD",
    "MARIADB_ALLOW_EMPTY_PASSWORD",
    "MARIADB_ALLOW_EMPTY_ROOT_PASSWORD",
    "MARIADB_RANDOM_ROOT_PASSWORD",
}
INTERPOLATION_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^}]+\})")
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://([^/\s@]+)@")


def _display_path(path, root):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def discover_compose_assets(root):
    """Return parsed Compose assets and parse errors under skills/*/assets/."""
    root = Path(root).resolve()
    assets = []
    errors = []
    patterns = ("skills/*/assets/*.yaml", "skills/*/assets/*.yml")
    paths = sorted({path for pattern in patterns for path in root.glob(pattern)})

    for path in paths:
        display = _display_path(path, root)
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{display}: cannot parse YAML: {exc}; fix or remove the invalid asset")
            continue
        if isinstance(document, Mapping) and isinstance(document.get("services"), Mapping):
            assets.append((path, document))

    return assets, errors


def _has_interpolation(value):
    return bool(INTERPOLATION_RE.search(str(value)))


def _is_sensitive_key(key):
    normalized = key.upper()
    return (
        normalized.endswith(SENSITIVE_SUFFIXES)
        and not normalized.endswith("_FILE")
        and normalized not in PASSWORD_FLAG_KEYS
    )


def _environment_items(environment):
    if isinstance(environment, Mapping):
        yield from environment.items()
    elif isinstance(environment, list):
        for item in environment:
            if not isinstance(item, str):
                continue
            key, separator, value = item.partition("=")
            yield key, value if separator else None


def _literal_url_password(value):
    if value is None:
        return False
    for match in URL_RE.finditer(str(value)):
        userinfo = match.group(1)
        if ":" not in userinfo:
            continue
        password = userinfo.split(":", 1)[1]
        if password and not _has_interpolation(password):
            return True
    return False


def _environment_errors(path, service_name, environment):
    errors = []
    for key, value in _environment_items(environment):
        if not isinstance(key, str):
            continue
        value_text = "" if value is None else str(value)
        if _is_sensitive_key(key) and value_text and not _has_interpolation(value_text):
            errors.append(
                f"{path}: service '{service_name}' environment key '{key}' has a nonempty literal credential; "
                "use Compose interpolation, an empty value, or a *_FILE variable"
            )
        if _literal_url_password(value):
            errors.append(
                f"{path}: service '{service_name}' environment key '{key}' contains a literal password in URL userinfo; "
                "interpolate the password"
            )
    return errors


def _target_has_datastore_port(target):
    if isinstance(target, bool) or target is None:
        return False
    text = str(target).split("/", 1)[0]
    try:
        if "-" in text:
            start, end = (int(part) for part in text.split("-", 1))
            return any(start <= port <= end for port in DATASTORE_PORTS)
        return int(text) in DATASTORE_PORTS
    except ValueError:
        return False


def _short_port_parts(port):
    text = str(port).split("/", 1)[0]
    if text.startswith("["):
        match = re.fullmatch(r"\[([^]]+)]:(?:[^:]+):([^:]+)", text)
        return (match.group(1), match.group(2)) if match else None
    parts = text.rsplit(":", 2)
    if len(parts) == 1:
        return None, parts[0]
    if len(parts) == 2:
        return None, parts[1]
    if len(parts) == 3:
        return parts[0], parts[2]
    return None


def _port_errors(path, service_name, ports):
    if not isinstance(ports, list):
        return []
    errors = []
    for port in ports:
        if _has_interpolation(port):
            continue
        host_ip = None
        target = None
        published = None
        description = str(port)
        if isinstance(port, Mapping):
            if any(_has_interpolation(value) for value in port.values()):
                continue
            target = port.get("target")
            published = port.get("published")
            host_ip = port.get("host_ip")
        elif isinstance(port, (str, int)) and not isinstance(port, bool):
            parts = _short_port_parts(port)
            if parts is not None:
                host_ip, target = parts
                published = True
        if published is None or not _target_has_datastore_port(target):
            continue
        if host_ip in (None, "", "0.0.0.0", "::"):
            errors.append(
                f"{path}: service '{service_name}' publishes datastore port '{description}' on all interfaces; "
                "bind it to 127.0.0.1 (or another explicit host IP)"
            )
    return errors


def _image_error(path, service_name, image):
    if not isinstance(image, str) or not image.strip():
        return (
            f"{path}: service '{service_name}' image has no explicit non-latest tag or digest; "
            "set a version tag or digest"
        )
    reference = image.strip()
    if "@" in reference:
        name, digest = reference.rsplit("@", 1)
        if name and ":" in digest and digest.split(":", 1)[1]:
            return None
    final_component = reference.rsplit("/", 1)[-1]
    if ":" not in final_component:
        return (
            f"{path}: service '{service_name}' image '{reference}' has no explicit tag; "
            "set a non-latest version tag or digest"
        )
    tag = final_component.rsplit(":", 1)[1]
    if not tag or tag.lower() == "latest":
        return (
            f"{path}: service '{service_name}' image '{reference}' does not use an explicit non-latest tag; "
            "set a version tag or digest"
        )
    return None


def _socket_source(source):
    return source in {"/var/run/docker.sock", "/run/docker.sock"}


def _socket_volume(volume):
    if isinstance(volume, str):
        source = volume.removeprefix("type=bind,").split(",", 1)[0]
        source = source.removeprefix("source=").removeprefix("src=")
        return _socket_source(source.split(":", 1)[0])
    if isinstance(volume, Mapping):
        return _socket_source(volume.get("source", volume.get("src")))
    return False


def _volume_errors(path, service_name, volumes):
    if not isinstance(volumes, list):
        return []
    return [
        f"{path}: service '{service_name}' mounts /var/run/docker.sock; remove the Docker socket mount"
        for volume in volumes
        if _socket_volume(volume)
    ]


def validate_compose_asset(path, document, root=None):
    """Return hygiene errors for a parsed Compose document."""
    path = Path(path).resolve()
    root = Path(root).resolve() if root is not None else path.parent
    display = _display_path(path, root)
    errors = []
    services = document.get("services", {})

    for service_name in sorted(services, key=str):
        service = services[service_name]
        if not isinstance(service, Mapping):
            continue
        errors.extend(_environment_errors(display, service_name, service.get("environment")))
        errors.extend(_port_errors(display, service_name, service.get("ports")))
        if "image" in service:
            image_error = _image_error(display, service_name, service.get("image"))
            if image_error:
                errors.append(image_error)
        errors.extend(_volume_errors(display, service_name, service.get("volumes")))
    return errors


def validate_compose_assets(root):
    """Discover all Compose YAML assets and return parse and hygiene errors."""
    assets, errors = discover_compose_assets(root)
    for path, document in assets:
        errors.extend(validate_compose_asset(path, document, root))
    return errors
