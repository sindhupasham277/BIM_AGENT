# Security

## Reporting a vulnerability

Please report security problems privately through GitHub's **Report a vulnerability** button (Security tab), not in a public issue. Include the steps to reproduce and the version or commit.

## What counts

- A way to change, delete or export model data without an Apply confirmation.
- A way for generated or model-embedded text to escape the sandbox (imports, private members, file or network access).
- A preview that does not match what Apply actually does.
- Exposure of API keys or local files.

## Handling secrets

- The OpenAI key is read from the `BTP_API` environment variable and is never stored in the repository.
- `.env`, Revit models (`*.rvt`, `*.rfa`) and memory databases are ignored by Git.
