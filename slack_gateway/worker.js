/**
 * Slack Gateway - Cloudflare Worker
 * ===================================
 * Slack App からのメンションイベントを受け取り、
 * GitHub Actions の repository_dispatch をトリガーする。
 *
 * 環境変数（Cloudflare Dashboard で設定）:
 *   SLACK_BOT_TOKEN       : xoxb-... （Slack Bot Token）
 *   SLACK_SIGNING_SECRET  : Slack App の Signing Secret
 *   GITHUB_TOKEN          : GitHub Personal Access Token（repo権限）
 *   GITHUB_REPO           : "Yuki-F-0911/x-bookmark"
 *
 * デプロイ:
 *   npm install -g wrangler
 *   wrangler deploy
 */

const GITHUB_API = "https://api.github.com";

export default {
  async fetch(request, env) {
    // Slack URL Verification チャレンジ
    if (request.method === "POST") {
      const body = await request.text();
      const payload = JSON.parse(body);

      // URL verification（Slack App設定時の初回リクエスト）
      if (payload.type === "url_verification") {
        return new Response(JSON.stringify({ challenge: payload.challenge }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // Slack署名検証
      const isValid = await verifySlackSignature(request, body, env.SLACK_SIGNING_SECRET);
      if (!isValid) {
        return new Response("Unauthorized", { status: 401 });
      }

      // app_mention イベントを処理
      if (payload.event && payload.event.type === "app_mention") {
        const event = payload.event;
        // Botへのメンション部分を除去して質問文を取得
        const question = event.text.replace(/<@[A-Z0-9]+>/g, "").trim();
        const channel  = event.channel;
        const thread_ts = event.thread_ts || event.ts;

        // 空の質問はスキップ
        if (!question) {
          return new Response("OK", { status: 200 });
        }

        // GitHub Actions をトリガー（非同期）
        await triggerGitHubActions(env, {
          question,
          channel,
          thread_ts,
        });

        // Slackには即座に200を返す（3秒以内のルール）
        return new Response("OK", { status: 200 });
      }

      return new Response("OK", { status: 200 });
    }

    return new Response("X Bookmark Digest Slack Gateway", { status: 200 });
  },
};

/**
 * Slack署名を検証する
 */
async function verifySlackSignature(request, body, signingSecret) {
  const timestamp = request.headers.get("X-Slack-Request-Timestamp");
  const slackSignature = request.headers.get("X-Slack-Signature");

  if (!timestamp || !slackSignature) return false;

  // リプレイ攻撃防止（5分以内のリクエストのみ受け付け）
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - parseInt(timestamp)) > 300) return false;

  const sigBase = `v0:${timestamp}:${body}`;
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(sigBase));
  const hexSignature = "v0=" + Array.from(new Uint8Array(signature))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");

  return hexSignature === slackSignature;
}

/**
 * GitHub Actions repository_dispatch をトリガーする
 */
async function triggerGitHubActions(env, payload) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_REPO}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github.v3+json",
      "Content-Type": "application/json",
      "User-Agent": "XBookmarkDigest-SlackBot/1.0",
    },
    body: JSON.stringify({
      event_type: "slack-mention",
      client_payload: payload,
    }),
  });

  if (!response.ok) {
    console.error(`GitHub API エラー: ${response.status} ${await response.text()}`);
  } else {
    console.log(`GitHub Actions トリガー成功: question="${payload.question}"`);
  }
}
