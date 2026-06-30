"""
Interactive Projection Wizard — guides the user through runtime field selection.

After the canonical candidate is built, the wizard:
  Step 1  — Displays all available canonical fields with numbered menu.
  Step 2  — Prompts for field selection (numbers or names).
  Step 3  — Optionally renames any selected field.
  Step 4  — Prompts for missing value policy.
  Step 5  — Displays a projection summary.
  Step 6  — Asks for confirmation (Y/N).
  Step 7  — Constructs and returns a ProjectionRequest.
"""

from typing import Dict, List, Optional, Tuple

import typer

from src.models.projection_request import ProjectionRequest
from src.projection.projection_service import FIELD_DISPLAY_NAMES, _TOP_LEVEL_FIELDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Ordered field list for the wizard menu.
_WIZARD_FIELDS: List[str] = list(_TOP_LEVEL_FIELDS)


def _header(text: str) -> None:
    """Print a bold section header."""
    typer.echo("\n" + "─" * 60)
    typer.echo(f"  {text}")
    typer.echo("─" * 60)


def _print_field_menu() -> None:
    """Display the numbered field selection menu."""
    _header("Available Canonical Fields")
    for i, field in enumerate(_WIZARD_FIELDS, start=1):
        label = FIELD_DISPLAY_NAMES.get(field, field)
        typer.echo(f"  {i:>2}. {label}  ({field})")


def _parse_field_selection(raw: str) -> List[str]:
    """
    Parse the user's field selection input.

    Accepts comma-separated numbers, field names, or a mix.
    Returns the list of selected canonical field paths.
    """
    selected: List[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(_WIZARD_FIELDS):
                field = _WIZARD_FIELDS[idx]
                if field not in selected:
                    selected.append(field)
            else:
                typer.echo(f"  [!] Invalid number: {token} — skipped.")
        elif token in _WIZARD_FIELDS:
            if token not in selected:
                selected.append(token)
        else:
            # Check if it matches a display name.
            matched = next(
                (f for f, label in FIELD_DISPLAY_NAMES.items()
                 if label.lower() == token.lower()),
                None,
            )
            if matched and matched not in selected:
                selected.append(matched)
            else:
                typer.echo(f"  [!] Unknown field: '{token}' — skipped.")
    return selected


def _prompt_renames(selected_fields: List[str]) -> Dict[str, str]:
    """
    Interactively collect field rename mappings.

    Returns a dict mapping canonical field name → desired output name.
    """
    rename: Dict[str, str] = {}
    while True:
        typer.echo("\n  Select a field to rename (number or name), or press Enter to skip:")
        for i, field in enumerate(selected_fields, start=1):
            label = FIELD_DISPLAY_NAMES.get(field, field)
            typer.echo(f"    {i}. {label}  ({field})")

        choice = typer.prompt("  Field", default="").strip()
        if not choice:
            break

        # Resolve choice to a field name.
        target: Optional[str] = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(selected_fields):
                target = selected_fields[idx]
        elif choice in selected_fields:
            target = choice
        else:
            typer.echo(f"  [!] '{choice}' not found.")
            continue

        new_name = typer.prompt(f"  New output name for '{target}'").strip()
        if new_name:
            rename[target] = new_name
            typer.echo(f"  ✓ '{target}' will be output as '{new_name}'")

        again = typer.prompt("  Rename another field? (y/N)", default="n")
        if again.lower() != "y":
            break

    return rename


def _print_summary(
    selected: List[str],
    rename: Dict[str, str],
    policy: str,
) -> None:
    """Display the projection configuration summary."""
    _header("Projection Summary")
    typer.echo("\n  Included Fields:")
    for field in selected:
        label = FIELD_DISPLAY_NAMES.get(field, field)
        typer.echo(f"    ✓ {label}")

    if rename:
        typer.echo("\n  Renames:")
        for src, dst in rename.items():
            typer.echo(f"    {src}  →  {dst}")

    typer.echo(f"\n  Missing Value Policy:  {policy.upper()}")


def run_wizard() -> ProjectionRequest:
    """
    Run the full interactive projection wizard.

    Returns:
        A ``ProjectionRequest`` built from the user's choices.
    """
    logger.info("ProjectionWizard: starting interactive wizard.")

    # ---- Step 1 & 2: Field selection ----
    _print_field_menu()
    typer.echo(
        "\n  Select fields to include (comma-separated numbers or names)."
        "\n  Press Enter with no input to include ALL fields.\n"
    )
    raw_selection = typer.prompt("  Your selection", default="").strip()

    if not raw_selection:
        selected: List[str] = list(_WIZARD_FIELDS)
        typer.echo("  → Including all fields.")
    else:
        selected = _parse_field_selection(raw_selection)
        if not selected:
            typer.echo("  [!] No valid fields selected — defaulting to all fields.")
            selected = list(_WIZARD_FIELDS)

    typer.echo(
        "\n  Selected: " + ", ".join(FIELD_DISPLAY_NAMES.get(f, f) for f in selected)
    )

    # ---- Step 3: Rename ----
    rename_choice = typer.prompt(
        "\n  Would you like to rename any fields?\n  1 Yes  2 No",
        default="2",
    ).strip()
    rename: Dict[str, str] = {}
    if rename_choice == "1":
        rename = _prompt_renames(selected)

    # ---- Step 4: Missing value policy ----
    _header("Missing Value Policy")
    typer.echo(
        "  Choose how to handle fields that are requested but absent on the candidate:\n"
        "  1  Omit   — field is silently excluded from output\n"
        "  2  Null   — field is included with a null value\n"
        "  3  Error  — raise an error and halt"
    )
    policy_map = {"1": "omit", "2": "null", "3": "error"}
    policy_raw = typer.prompt("  Policy (1/2/3)", default="1").strip()
    policy = policy_map.get(policy_raw, "omit")

    # ---- Step 5: Summary ----
    _print_summary(selected, rename, policy)

    # ---- Step 6: Confirm ----
    typer.echo("")
    confirm = typer.prompt("  Proceed with this projection? (Y/n)", default="Y").strip()
    if confirm.lower() not in ("y", "yes", ""):
        typer.echo("  Wizard cancelled — using default (all fields, omit policy).")
        logger.info("ProjectionWizard: cancelled by user.")
        return ProjectionRequest()

    # ---- Step 7: Build ProjectionRequest ----
    request = ProjectionRequest(
        include=selected,
        rename=rename,
        missing_policy=policy,  # type: ignore[arg-type]
    )
    logger.info(
        "ProjectionWizard: built request — %d fields, %d renames, policy=%s",
        len(selected),
        len(rename),
        policy,
    )
    return request
