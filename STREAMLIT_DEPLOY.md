# Deploy Proofpoint to Streamlit Community Cloud

The Streamlit entry point is `streamlit_app.py`. It calls the same extraction, evidence rubric, and report generators as the original app directly; it does not need a FastAPI server.

## Deployment settings

1. Sign in to **https://share.streamlit.io/** in your own browser and connect the GitHub account that can access this repository. Never put account passwords, GitHub tokens, or login codes in the repository or chat.
2. Choose **Create app** / deploy an app from GitHub.
3. Select these values:

| Setting | Value |
| --- | --- |
| Repository | `surendra1220/resume-screener-mps` |
| Branch | `main` |
| Main file path | `streamlit_app.py` |
| Python version (advanced settings) | `3.12` |
| Secrets | None required |

4. Choose an available app URL/subdomain and deploy. Make the app public in its sharing/access settings if that is the intended audience.
5. Wait for dependency installation and the healthy app page, then copy the actual `https://….streamlit.app` URL shown by Streamlit. The URL is not confirmed until the hosting platform provisions it.

`requirements.txt` installs the Python dependencies; `packages.txt` installs antiword for legacy `.doc` files. `.streamlit/config.toml` supplies the theme, 10 MB upload limit, XSRF/CORS protection, and disables usage telemetry. No API keys or external AI service are required.

## Verify after deployment

- Select **Try synthetic demo**, review/approve the benchmark, and select **Screen candidate**.
- Download both PDF and HTML reports.
- Open a separate browser/incognito session: it should not contain another session's uploads or report.
- Upload your own candidate resume and optionally a custom JD. Review custom extraction before screening.
- Use **Clear session** to remove the current app state.

The included demo is fictional. The private candidate resume and reference screening from the local workspace are not included or loaded by the Streamlit app.

## Data handling and limits

Uploads are transmitted to and processed on Streamlit's hosting servers. Candidate text, edits, and generated exports are held in the visitor's `st.session_state`; no candidate data is put in a global Streamlit cache, written to Git, or exposed through the FastAPI report cache. Generated reports are discarded on a subsequent app interaction after one hour; input changes invalidate the previous result. Disconnected sessions are configured for 120-second retention, subject to the hosting runtime. Downloaded reports remain on the downloading device. Clear session also resets widgets and app data.

A public URL makes the application accessible to others. Use only documents you are authorized to upload to this hosting provider. This community-hosted surface has session separation, not organization-managed accounts, audit logs, or enterprise retention controls. Set restricted app access when needed through Streamlit's supported access settings.

The engine remains a conservative, inspectable local rules engine. It can miss paraphrases; custom JD drafts and resume evidence require human review. Hosting does not turn self-reported resume evidence into verified experience.

## Local Streamlit run

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open http://localhost:8501. The existing `run.sh` / `run.ps1` scripts continue to launch the original UI on port 8000.
