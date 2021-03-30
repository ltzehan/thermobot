## thermobot

Rewrite of the original [temperature-ops-bot](https://github.com/markus-lendermann/temperature-ops-bot) that was deployed on GCP.

### Setup

Requires the following to be installed:

- [GCP Datastore Emulator](https://cloud.google.com/datastore/docs/tools/datastore-emulator)
- ngrok

Tokens are expected to be available in the `secrets.json` file as:

```json
{
    "telegram-bot": "BOT TOKEN FROM TELEGRAM API",
    "project-url": "GCP PROJECT URL / LOCAL DEV SERVER URL"
}
```

### Local development

```bash
gcloud config set project <PROJECT_NAME>

# Start the datastore emulator server
gcloud beta emulators datastore start

# Export emulation configuration
gcloud beta emulators datastore env-init > set_vars.cmd && set_vars.cmd && del set_vars.cmd

set FLASK_ENV=development
python -m src.wsgi

# Expose server to internet-facing URL
ngrok http 5000 -region ap
# Configure bot webhook
python webhookHelper.py
```

### Running tests

```bash
pytest -q n auto --tb=no
```

