export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ ok: false, message: 'Use GET' })
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN
  if (!token) {
    return res.status(200).json({ ok: false, status: 'unavailable', message: 'Missing GITHUB_DISPATCH_TOKEN' })
  }

  const owner = process.env.GITHUB_OWNER || 'JahanzaibShaikh19'
  const repo = process.env.GITHUB_REPO || 'crypto_hyper_bot'
  const workflow = process.env.ORIGINAL_BOT_WORKFLOW_FILE || 'original-bot-scan.yml'
  const after = req.query?.after ? Date.parse(String(req.query.after)) : 0
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/runs?per_page=5&branch=main`

  const githubRes = await fetch(url, {
    headers: {
      authorization: `Bearer ${token}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'crypto-hyper-bot-dashboard',
    },
  })

  if (!githubRes.ok) {
    return res.status(githubRes.status).json({ ok: false, message: await githubRes.text() })
  }

  const payload = await githubRes.json()
  const runs = payload.workflow_runs || []
  const run = after ? runs.find((item) => Date.parse(item.created_at) >= after - 3000) : runs[0]
  if (!run) {
    return res.status(200).json({ ok: true, status: 'queued', message: 'Waiting for new original bot scan run to appear' })
  }

  return res.status(200).json({
    ok: true,
    id: run.id,
    status: run.status,
    conclusion: run.conclusion,
    htmlUrl: run.html_url,
    createdAt: run.created_at,
    updatedAt: run.updated_at,
    message: run.conclusion ? `Original bot scan ${run.conclusion}` : `Original bot scan ${run.status}`,
  })
}
