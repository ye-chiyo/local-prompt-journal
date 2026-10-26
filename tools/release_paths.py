"""Validate artifact locations before release verification writes anything."""
from pathlib import Path


def external_output(output, repo):
    destination = Path(output).resolve()
    selected_repo = Path(repo).resolve()
    tool_repo = Path(__file__).resolve().parent.parent
    if any(destination.is_relative_to(root) for root in (selected_repo, tool_repo)):
        raise ValueError('Output directory must be outside both the selected repository and the tool source repository.')
    return destination
