# Production Dashboard Setup

The frontend is now Vercel-serverless friendly and functional.

## Architecture

```txt
GitHub Actions hourly job
  -> runs scripts/generate_dashboard_data.py
  -> updates frontend/public/data/dashboard.json
  -> Vercel serves React dashboard

Dashboard Run Scan button
  -> calls /api/run-scan on Vercel
  -> dispatches GitHub Actions workflow manually
```

## Vercel Settings

Use root deployment because `vercel.json` routes the build to the frontend.

```txt
Root Directory: ./
Install Command: npm --prefix frontend install
Build Command: npm --prefix frontend run build
Output Directory: frontend/dist
```

## Required Vercel Environment Variable

Create a fine-grained GitHub token with permission to run Actions for this repo, then add it in Vercel:

```txt
GITHUB_DISPATCH_TOKEN=your_github_token
```

Optional values:

```txt
GITHUB_OWNER=JahanzaibShaikh19
GITHUB_REPO=crypto_hyper_bot
GITHUB_WORKFLOW_FILE=signal-snapshot.yml
GITHUB_REF=main
```

## GitHub Repo Settings

For the hourly job to commit refreshed dashboard data:

```txt
Settings -> Actions -> General -> Workflow permissions -> Read and write permissions
```

## Local Frontend Run

```bash
cd frontend
npm install
npm run dev
```

## Local Data Refresh

```bash
python scripts/generate_dashboard_data.py
```

## Notes

- The long-running Python bot should still run on a VPS/Render/Railway if you want continuous Telegram delivery.
- Vercel is used for the dashboard and manual workflow trigger only.
- The hourly snapshot script uses public market APIs and no heavy Python dependencies, so it avoids Vercel/Python build failures.
