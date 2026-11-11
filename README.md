# Brand Research MCP

A small remote MCP server for public Meta Ad Library research. It uses the official MCP Python SDK and Playwright to read the rendered public page. It does **not** log in, use private endpoints, defeat CAPTCHAs, or bypass rate limits.

## Tools

- `search_meta_ads_library(brand_name, country="IN")`
- `research_multiple_brands(brand_names, country="IN")` — maximum five per call, sequential with a delay
- `build_meta_ads_library_url(brand_name, country="IN", active_status="active")`

The output is raw visible page text and public Ad Library links, not a guaranteed structured ad dataset. Confirm advertiser identity and ad details on Meta's page.

## Local run

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Set `MCP_API_TOKEN` in your shell, then:

```bash
python server.py
```

The MCP endpoint is `http://localhost:8000/mcp`. Requests must include:

```http
Authorization: Bearer YOUR_MCP_API_TOKEN
```

## Free cloud deployment (best-effort)

1. Push this folder to a GitHub repository.
2. Create a Render account and choose **New > Blueprint**.
3. Connect the repository containing `render.yaml`.
4. Deploy the `brand-research-mcp` service.
5. In Render's Environment settings, confirm `MCP_API_TOKEN` exists. Copy it securely.
6. Your MCP endpoint will be `https://YOUR-SERVICE.onrender.com/mcp`.
7. Configure that URL and bearer token in an MCP client that supports remote Streamable HTTP servers.

### Free-tier caveats

- Render free services can spin down when idle and may take time to wake.
- Free compute is limited; Chromium may be slow or exceed available memory.
- Free instances have ephemeral filesystems. This MVP intentionally does not promise durable research history.
- Free hosting is not unlimited or guaranteed 24/7.
- Meta can change its page, rate-limit requests, or show login/CAPTCHA challenges. Stop when access is restricted; do not attempt to bypass them.

## Security

- Keep `MCP_API_TOKEN` private. Do not paste it into public GitHub files.
- Rotate the token if exposed.
- Use only the public Ad Library. No account login or credentials are required.
- Restrict the service further before sharing it with other people.

## Next milestones

1. Validate the rendered page extraction on a few known advertisers.
2. Add robust parsing for advertiser, ad ID, start date, platforms, creative, CTA and destination only where visibly present.
3. Add a persistent database only after choosing a hosting tier with durable storage.
4. Add request quotas and per-user authentication before public use.
