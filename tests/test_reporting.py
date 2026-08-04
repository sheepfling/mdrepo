"""Diagnostic rendering safety coverage."""

from io import StringIO
from pathlib import Path

from mdrepo.models import Diagnostic, OutputFormat, Severity
from mdrepo.reporting import write_diagnostics


def test_text_output_escapes_control_characters() -> None:
    stream = StringIO()
    write_diagnostics(
        diagnostics=(
            Diagnostic(
                rule_id="MDR001",
                message="bad\nmessage",
                severity=Severity.ERROR,
                path=Path("docs/line\nbreak.md"),
                line=1,
                column=1,
                hint="use\tportable paths",
            ),
        ),
        output_format=OutputFormat.TEXT,
        stream=stream,
    )

    assert stream.getvalue() == (
        r"docs/line\nbreak.md:1:1: error MDR001 bad\nmessage" + "\n"
        r"  hint: use\tportable paths" + "\n"
    )
