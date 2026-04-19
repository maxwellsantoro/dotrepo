#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


CONTENT_TYPES = {
    ".js": "application/javascript",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".vsixmanifest": "text/xml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the dotrepo VS Code extension as a VSIX.")
    parser.add_argument(
        "--extension-root",
        default="editors/vscode",
        help="Path to the VS Code extension root (default: editors/vscode)",
    )
    parser.add_argument(
        "--output",
        "--out",
        dest="output",
        required=True,
        help="Output VSIX path",
    )
    return parser.parse_args()


def ensure_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"expected file is missing: {path}")


def load_package(extension_root: Path) -> dict:
    package_path = extension_root / "package.json"
    ensure_file(package_path)
    return json.loads(package_path.read_text(encoding="utf-8"))


def normalize_repository_urls(repository: dict | str | None) -> tuple[str | None, str | None]:
    if isinstance(repository, dict):
        repo_url = repository.get("url")
    elif isinstance(repository, str):
        repo_url = repository
    else:
        repo_url = None
    if not isinstance(repo_url, str) or not repo_url:
        return None, None
    normalized = repo_url.removesuffix("/")
    public = normalized.removesuffix(".git")
    git = normalized if normalized.endswith(".git") else f"{normalized}.git"
    return public, git


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def manifest_tags(package: dict) -> str:
    keywords = package.get("keywords")
    tags: list[str] = []
    if isinstance(keywords, list):
        tags.extend(value for value in keywords if isinstance(value, str))
    contributes = package.get("contributes")
    if isinstance(contributes, dict):
        languages = contributes.get("languages")
        if isinstance(languages, list):
            for language in languages:
                if not isinstance(language, dict):
                    continue
                language_id = language.get("id")
                if not isinstance(language_id, str) or not language_id:
                    continue
                tags.append(language_id)
                squashed = language_id.replace("-", "")
                if squashed != language_id:
                    tags.append(squashed)
    return ",".join(dedupe(tags))


def extension_kind_value(package: dict) -> str:
    extension_kind = package.get("extensionKind")
    if isinstance(extension_kind, list):
        kinds = [value for value in extension_kind if isinstance(value, str) and value]
        if kinds:
            return ",".join(kinds)
    if isinstance(extension_kind, str) and extension_kind:
        return extension_kind
    return "workspace"


def derives_code(package: dict) -> bool:
    return any(
        isinstance(package.get(field), str) and package.get(field)
        for field in ("main", "browser")
    )


def support_url(package: dict, repo_public_url: str | None) -> str | None:
    bugs = package.get("bugs")
    if isinstance(bugs, dict):
        url = bugs.get("url")
        if isinstance(url, str) and url:
            return url
    if repo_public_url:
        return f"{repo_public_url}/issues"
    return None


def learn_url(package: dict, repo_public_url: str | None) -> str | None:
    homepage = package.get("homepage")
    if isinstance(homepage, str) and homepage:
        return homepage
    if repo_public_url:
        return f"{repo_public_url}#readme"
    return None


def details_path(extension_root: Path) -> tuple[Path | None, str | None]:
    readme = extension_root / "README.md"
    if readme.is_file():
        return readme, "extension/readme.md"
    return None, None


def license_path(extension_root: Path) -> tuple[Path | None, str | None]:
    for candidate, archive_name in (
        ("LICENSE", "extension/LICENSE.txt"),
        ("LICENSE.txt", "extension/LICENSE.txt"),
    ):
        path = extension_root / candidate
        if path.is_file():
            return path, archive_name
    return None, None


def archive_entries(extension_root: Path, package: dict) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []

    main = package.get("main")
    if not isinstance(main, str) or not main:
        raise SystemExit("package.json is missing a string main entry")
    main_path = extension_root / main.removeprefix("./")
    ensure_file(main_path)

    package_json = extension_root / "package.json"
    ensure_file(package_json)
    entries.append((package_json, "extension/package.json"))

    readme_file, readme_archive = details_path(extension_root)
    if readme_file and readme_archive:
        entries.append((readme_file, readme_archive))

    license_file, license_archive = license_path(extension_root)
    if license_file and license_archive:
        entries.append((license_file, license_archive))

    contributes = package.get("contributes")
    if isinstance(contributes, dict):
        languages = contributes.get("languages")
        if isinstance(languages, list):
            for language in languages:
                if not isinstance(language, dict):
                    continue
                configuration = language.get("configuration")
                if isinstance(configuration, str) and configuration:
                    config_path = extension_root / configuration.removeprefix("./")
                    ensure_file(config_path)
                    entries.append((config_path, f"extension/{config_path.relative_to(extension_root)}"))

    entries.append((main_path, f"extension/{main_path.relative_to(extension_root)}"))
    ordered = dedupe_entries(entries)
    preferred_order = {
        "extension/package.json": 0,
        "extension/language-configuration.json": 1,
        "extension/readme.md": 2,
        "extension/LICENSE.txt": 3,
    }
    return sorted(ordered, key=lambda item: (preferred_order.get(item[1], 10), item[1]))


def dedupe_entries(entries: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    seen: set[str] = set()
    deduped: list[tuple[Path, str]] = []
    for source, archive_name in entries:
        if archive_name in seen:
            continue
        seen.add(archive_name)
        deduped.append((source, archive_name.replace("\\", "/")))
    return deduped


def content_types_xml(archive_names: list[str]) -> str:
    extensions = sorted(
        {
            Path(name).suffix
            for name in archive_names
            if Path(name).suffix in CONTENT_TYPES
        }
        | {".vsixmanifest"}
    )
    defaults = "".join(
        f'<Default Extension="{escape(extension)}" ContentType="{escape(CONTENT_TYPES[extension])}"/>'
        for extension in extensions
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f"{defaults}"
        "</Types>\n"
    )


def rewrite_readme_links(readme: str, *, readme_path: Path, repo_root: Path, repo_public_url: str | None) -> str:
    if not repo_public_url:
        return readme

    def replace(match: re.Match[str]) -> str:
        prefix, target, suffix = match.groups()
        parsed = urlparse(target)
        if parsed.scheme or target.startswith(("#", "mailto:", "data:")):
            return match.group(0)
        resolved = (readme_path.parent / parsed.path).resolve()
        try:
            relative = resolved.relative_to(repo_root)
        except ValueError:
            return match.group(0)
        rebuilt = f"{repo_public_url}/blob/HEAD/{relative.as_posix()}"
        if parsed.fragment:
            rebuilt = f"{rebuilt}#{parsed.fragment}"
        return f"{prefix}{rebuilt}{suffix}"

    return re.sub(r"(!?\[[^\]]*\]\()([^)]+)(\))", replace, readme)


def manifest_xml(
    package: dict,
    *,
    repo_public_url: str | None,
    repo_git_url: str | None,
    has_readme: bool,
    has_license: bool,
) -> str:
    name = expect_string(package, "name")
    display_name = expect_string(package, "displayName")
    version = expect_string(package, "version")
    publisher = expect_string(package, "publisher")
    description = expect_string(package, "description")
    engine = expect_string(package.get("engines", {}), "vscode")
    categories = package.get("categories")
    categories_value = ",".join(value for value in categories if isinstance(value, str)) if isinstance(categories, list) else ""
    tags_value = manifest_tags(package)
    extension_kind = extension_kind_value(package)
    support = support_url(package, repo_public_url)
    learn = learn_url(package, repo_public_url)

    properties: list[str] = [
        f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.Engine" Value="{escape(engine)}" />',
        '\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />',
        '\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />',
        f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="{escape(extension_kind)}" />',
        '\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />',
        '\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.EnabledApiProposals" Value="" />',
    ]
    if derives_code(package):
        properties.append('\t\t\t\t<Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true" />')
    if repo_git_url:
        properties.extend(
            [
                f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Links.Source" Value="{escape(repo_git_url)}" />',
                f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Links.Getstarted" Value="{escape(repo_git_url)}" />',
                f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Links.GitHub" Value="{escape(repo_git_url)}" />',
            ]
        )
    if support:
        properties.append(
            f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Links.Support" Value="{escape(support)}" />'
        )
    if learn:
        properties.append(
            f'\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Links.Learn" Value="{escape(learn)}" />'
        )
    properties.extend(
        [
            '\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown" Value="true" />',
            '\t\t\t\t<Property Id="Microsoft.VisualStudio.Services.Content.Pricing" Value="Free" />',
        ]
    )

    assets = [
        '\t\t\t<Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />'
    ]
    if has_readme:
        assets.append(
            '\t\t\t<Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/readme.md" Addressable="true" />'
        )
    if has_license:
        assets.append(
            '\t\t\t<Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE.txt" Addressable="true" />'
        )

    license_xml = '\n\t\t\t<License>extension/LICENSE.txt</License>' if has_license else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '\t<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" '
        'xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">\n'
        '\t\t<Metadata>\n'
        f'\t\t\t<Identity Language="en-US" Id="{escape(name)}" Version="{escape(version)}" Publisher="{escape(publisher)}" />\n'
        f'\t\t\t<DisplayName>{escape(display_name)}</DisplayName>\n'
        f'\t\t\t<Description xml:space="preserve">{escape(description)}</Description>\n'
        f'\t\t\t<Tags>{escape(tags_value)}</Tags>\n'
        f'\t\t\t<Categories>{escape(categories_value)}</Categories>\n'
        '\t\t\t<GalleryFlags>Public</GalleryFlags>\n'
        '\t\t\t<Properties>\n'
        f'{"\n".join(properties)}\n'
        '\t\t\t</Properties>'
        f'{license_xml}\n'
        '\t\t</Metadata>\n'
        '\t\t<Installation>\n'
        '\t\t\t<InstallationTarget Id="Microsoft.VisualStudio.Code"/>\n'
        '\t\t</Installation>\n'
        '\t\t<Dependencies/>\n'
        '\t\t<Assets>\n'
        f'{"\n".join(assets)}\n'
        '\t\t</Assets>\n'
        '\t</PackageManifest>\n'
    )


def expect_string(container: dict, key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"package.json is missing a string {key} value")
    return value


def write_vsix(extension_root: Path, output_path: Path) -> None:
    package = load_package(extension_root)
    entries = archive_entries(extension_root, package)
    repo_root = extension_root.parents[1]
    repo_public_url, repo_git_url = normalize_repository_urls(package.get("repository"))
    has_readme = any(archive_name == "extension/readme.md" for _, archive_name in entries)
    has_license = any(archive_name == "extension/LICENSE.txt" for _, archive_name in entries)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    archive_names = [archive_name for _, archive_name in entries]
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("extension.vsixmanifest", manifest_xml(
            package,
            repo_public_url=repo_public_url,
            repo_git_url=repo_git_url,
            has_readme=has_readme,
            has_license=has_license,
        ))
        archive.writestr("[Content_Types].xml", content_types_xml(archive_names))
        for source, archive_name in entries:
            if archive_name == "extension/readme.md":
                rewritten = rewrite_readme_links(
                    source.read_text(encoding="utf-8"),
                    readme_path=source,
                    repo_root=repo_root,
                    repo_public_url=repo_public_url,
                )
                archive.writestr(archive_name, rewritten)
            else:
                archive.write(source, archive_name)


def main() -> int:
    args = parse_args()
    extension_root = Path(args.extension_root).resolve()
    output_path = Path(args.output).resolve()
    write_vsix(extension_root, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
