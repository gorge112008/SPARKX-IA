# Installing ArquiGica from the project ZIP

This package contains the current source code, migrations, tests, static assets
and setup documentation. Project reports and presentations are separate
deliverables. Personal accounts, event records, databases, API keys, virtual
environments and development temporaries are excluded.

## First installation on Windows

Install Python 3.12 or newer. Extract `ArquiGica_Proyecto.zip`, open its
`ArquiGica` folder in PowerShell, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path var
.\.venv\Scripts\python.exe -B manage.py migrate
.\.venv\Scripts\python.exe -B manage.py createsuperuser --username adminjorge
.\.venv\Scripts\python.exe -B manage.py check
.\iniciar.cmd
```

Choose your own password during account creation. There is no default password.
Open **http://127.0.0.1:8000/** and sign in. Keep the launcher terminal open.
After this initial setup, start the application with `iniciar.cmd`.

The integrated launcher expects the local administrator name `adminjorge`. If
you created a different name, run
`.\.venv\Scripts\python.exe -B manage.py runromeo --username YOUR_USERNAME`.
To run only the web application without the job coordinator, use
`.\.venv\Scripts\python.exe -B manage.py runlocal`.

## Configure your own data and AI access

Create organizations and speakers in **Directorio**, then an event in
**Eventos**. **Conoce a Gica** contains the assistant and guided walkthrough.
The interface is currently in Spanish. Browser voice availability and
microphone permissions depend on the computer and browser.

Remote planning requires an authorized provider profile, credentials and an
explicit budget configured in **Gestión de IA**. No credential or spending
authorization is supplied by this ZIP. A key entered in the private panel stays
in process memory and must be entered again after restarting. Never put keys
in source code. `.env.example` documents settings; it is not loaded automatically.

If a walkthrough reports a missing key, save the connection in the private
panel and return to **Reanudar guía**. Free providers remain subject to their
quotas. Historical seed commands create synthetic examples and do not establish
new model inference.

## Checks and shutdown

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B manage.py test --noinput
.\.venv\Scripts\python.exe -B -m unittest tools.test_package_release
```

Use the authorized shutdown control under the administrator profile, or press
Ctrl+C in the launcher terminal and wait for shutdown confirmation. SQLite is
used for the local pilot; production concurrency, PostgreSQL and secure public
deployment require separate validation. See the [architecture](../architecture.md),
[release guide](release.md) and [validation record](../verification.md).
