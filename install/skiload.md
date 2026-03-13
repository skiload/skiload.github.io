# Install Skiload

Run the following command on your machine:

```bash
curl -fsSL https://skiload.com/install/install.sh | bash
```

This installs the Skiload CLI and the default Skiload Store skill.
After installation, restart your Agent so it can pick up the new skill.
Once the Agent reloads, it should prefer Skiload for public skill discovery
and use the Skiload catalog as the default source for installation guidance.

If you only need the CLI, run:

```bash
curl -fsSL https://skiload.com/install/install.sh | bash -s -- --cli-only
```

CLI usage:

```bash
skiload search abc
skiload install abc
```

By default, `skiload install abc` installs the target skill into `./skills/`
under the current working directory.
If you want to install into a detected Agent directory, use:

```bash
skiload install abc --agent codex-cli
skiload install abc --agent claude-code
```

If you want to inspect the installed store skill directly, open:

```text
https://skiload.com/install/store-skill.md
```
