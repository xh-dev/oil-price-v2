from pathlib import Path
import re

from packaging.requirements import InvalidRequirement, Requirement
import tomlkit


def sync_requirements():
    project_dir = Path(__file__).resolve().parent.parent
    requirements_file = project_dir / "requirements.txt"
    dependencies = []
    for number, line in enumerate(requirements_file.read_text(encoding="utf-8").splitlines(), 1):
        requirement = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if not requirement or requirement.startswith("#"):
            continue
        try:
            Requirement(requirement)
        except InvalidRequirement as error:
            raise ValueError(
                f"requirements.txt:{number}: Expected a PEP 508 dependency; "
                "pip options, includes, and editable installs are not supported."
            ) from error
        dependencies.append(requirement)

    pyproject_file = project_dir / "pyproject.toml"
    document = tomlkit.parse(pyproject_file.read_text(encoding="utf-8"))
    project = document["project"]
    if "dependencies" in project.get("dynamic", []):
        raise ValueError("Cannot sync dependencies declared dynamic in pyproject.toml.")
    project["dependencies"] = dependencies
    pyproject_file.write_text(tomlkit.dumps(document), encoding="utf-8")
    print(f"Synced {len(dependencies)} runtime dependencies to pyproject.toml.")


if __name__ == "__main__":
    sync_requirements()
