"""Read declared dependencies without evaluating build files or resolving packages."""

import json
import tomllib
import xml.etree.ElementTree as ET

from banger.discovery import discover_files

UNSUPPORTED = {
    "Gemfile",
    "Rakefile",
    "setup.py",
    "setup.cfg",
    "CMakeLists.txt",
    "build.gradle",
    "build.gradle.kts",
    "conanfile.py",
    "conanfile.txt",
}


def sections_for(path, content):
    name = path.name
    if name == "package.json":
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return {
            key: value
            for key, value in data.items()
            if key
            in {
                "dependencies",
                "devDependencies",
                "optionalDependencies",
                "peerDependencies",
                "bundledDependencies",
                "bundleDependencies",
                "overrides",
                "resolutions",
            }
        }
    if name in {"pyproject.toml", "Cargo.toml"}:
        data = tomllib.loads(content)
        sections = {}

        def visit(node, prefix=""):
            for key, value in node.items():
                location = prefix + key
                if (
                    key
                    in {
                        "dependencies",
                        "optional-dependencies",
                        "dependency-groups",
                        "dev-dependencies",
                        "build-dependencies",
                        "dynamic",
                    }
                    or location == "build-system.requires"
                ):
                    sections[location] = value
                elif isinstance(value, dict):
                    visit(value, location + ".")

        visit(data)
        return sections
    if name.startswith("requirements") and path.suffix == ".txt":
        return {
            "requirements": [
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        }
    if name == "go.mod":
        required, block = [], False
        for line in content.splitlines():
            value = line.strip()
            if not value or value.startswith("//"):
                continue
            if block:
                if value.split("//", 1)[0].strip() == ")":
                    block = False
                else:
                    required.append(value)
            elif value.startswith(("require ", "require\t")):
                value = value[len("require") :].strip()
                if value.split("//", 1)[0].strip() == "(":
                    block = True
                else:
                    required.append(value)
        if block:
            raise ValueError("Unclosed require block")
        return {"require": required}
    root = ET.fromstring(content)
    sections = {}

    def local(node):
        return node.tag.rsplit("}", 1)[-1]

    def visit_xml(node, ancestors=()):
        tag = local(node)
        if tag in {"dependency", "PackageReference", "PackageVersion"}:
            item = dict(node.attrib)
            item.update(
                {
                    local(c): c.text or "" if not len(c) else ET.tostring(c, encoding="unicode")
                    for c in node
                }
            )
            conditions = [dict(parent.attrib) for parent in ancestors if parent.attrib]
            if conditions:
                item["ancestor_attributes"] = conditions
            key = ".".join(local(p) for p in ancestors[1:]) if tag == "dependency" else tag
            sections.setdefault(key, []).append(item)
        else:
            for child in node:
                visit_xml(child, (*ancestors, node))

    visit_xml(root)
    return sections


def list_dependencies(root):
    result = {
        "basis": "declared; not installed or resolved",
        "manifests": [],
        "unresolved": [],
        "truncated": False,
        "limitations": "No package manager or build code is run. Includes, conditions, workspace inheritance, property expansion, overrides and transitive/lockfile resolution are not evaluated.",
    }
    budget = 4 * 1024 * 1024
    count = 0
    for path in discover_files(root):
        supported = (
            path.name
            in {
                "package.json",
                "pyproject.toml",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
                "Directory.Packages.props",
            }
            or path.suffix in {".csproj", ".fsproj", ".vbproj"}
            or path.name.startswith("requirements")
            and path.suffix == ".txt"
        )
        unsupported = path.name in UNSUPPORTED or path.suffix == ".gemspec"
        if not supported and not unsupported:
            continue
        if count >= 100 or budget <= 0:
            result["truncated"] = True
            break
        count += 1
        relative = path.relative_to(root).as_posix()
        if unsupported:
            result["unresolved"].append(
                {
                    "path": relative,
                    "reason": "Unsupported or executable manifest; inspect source without evaluation",
                }
            )
            continue
        try:
            with path.open("rb") as source:
                data = source.read(min(1024 * 1024 + 1, budget + 1))
            budget -= len(data)
            if len(data) > 1024 * 1024 or budget < 0:
                raise ValueError("Manifest or query byte limit")
            sections = sections_for(path, data.decode("utf-8-sig"))
            json.dumps(sections)
            result["manifests"].append({"path": relative, "sections": sections})
        except (ValueError, TypeError, OSError, ET.ParseError) as exc:
            result["unresolved"].append({"path": relative, "reason": str(exc)[:500]})
    return result
