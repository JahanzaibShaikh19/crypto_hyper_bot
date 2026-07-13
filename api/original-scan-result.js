export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ ok: false, message: 'Use GET' })
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN
  const owner = process.env.GITHUB_OWNER || 'JahanzaibShaikh19'
  const repo = process.env.GITHUB_REPO || 'crypto_hyper_bot'
  const ref = process.env.GITHUB_REF || 'main'
  const path = 'frontend/public/data/original-bot-scan.json'

  if (!token) {
    return res.status(503).json({ ok: false, message: 'Missing GITHUB_DISPATCH_TOKEN in Vercel env' })
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}?ref=${encodeURIComponent(ref)}`

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
  const decoded = Buffer.from(payload.content || '', payload.encoding || 'base64').toString('utf8')
  res.setHeader('Cache-Control', 'no-store, max-age=0')
  return res.status(200).json(JSON.parse(decoded))
}
