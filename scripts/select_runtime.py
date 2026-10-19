"""Select a successful, current-main CI artifact for the privileged CD workflow."""
import json
import os
from pathlib import Path
import re
import urllib.request


def validate_run(run, repository, workflow_id):
    if (run.get("workflow_id") != workflow_id or run.get("status") != "completed"
            or run.get("conclusion") != "success" or run.get("head_branch") != "main"
            or run.get("event") not in {"push", "workflow_dispatch"}
            or run.get("repository", {}).get("full_name") != repository
            or (run.get("head_repository") or {}).get("full_name") != repository
            or not re.fullmatch(r"[0-9a-f]{40}", run.get("head_sha", ""))):
        raise ValueError("CD requires a successful CI run from this repository's main branch")
    return run["head_sha"]


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"],
               "Accept": "application/vnd.github+json", "User-Agent": "Nen-CD"}

    def get(path):
        request = urllib.request.Request("https://api.github.com/repos/" + repository + "/" + path, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    run_id = str(event.get("workflow_run", {}).get("id") or os.environ.get("NEN_CI_RUN_ID", ""))
    if not run_id.isdigit():
        raise ValueError("Enter the numeric ID of the successful CI run")
    workflow_id = get("actions/workflows/ci.yml")["id"]
    run = get("actions/runs/" + run_id)
    commit = validate_run(run, repository, workflow_id)
    current = get("git/ref/heads/main")["object"]["sha"]
    outputs = {"skip": "true"}
    if commit != current:
        print("A newer main commit exists; this older deployment is skipped.")
    else:
        name = "nen-runtime-" + commit
        artifacts = get("actions/runs/" + run_id + "/artifacts?per_page=100")["artifacts"]
        matches = [artifact for artifact in artifacts if artifact["name"] == name and not artifact["expired"]]
        if len(matches) != 1:
            raise ValueError("Expected exactly one unexpired verified runtime artifact")
        outputs = {"skip": "false", "commit": commit, "run_id": run_id, "artifact": name}
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for key, value in outputs.items():
            output.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
