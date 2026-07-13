export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, message: 'Use POST' })
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN
  if (!token) {
    return res.status(500).json({ ok: false, message: 'Missing GITHUB_DISPATCH_TOKEN in Vercel env' })
  }

  const owner = process.env.GITHUB_OWNER || 'JahanzaibShaikh19'
  const repo = process.env.GITHUB_REPO || 'crypto_hyper_bot'
  const workflow = process.env.ORIGINAL_BOT_WORKFLOW_FILE || 'original-bot-scan.yml'
  const ref = process.env.GITHUB_REF || 'main'
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`

  const githubRes = await fetch(url, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${token}`,
      accept: 'application/vnd.github+json',
      'content-type': 'application/json',
      'user-agent': 'crypto-hyper-bot-dashboard',
    },
    body: JSON.stringify({ ref }),
  })

  if (githubRes.status === 204) {
    return res.status(202).json({ ok: true, message: 'Original bot scan workflow started', workflow, ref })
  }

  return res.status(githubRes.status).json({ ok: false, message: await githubRes.text() })
}
