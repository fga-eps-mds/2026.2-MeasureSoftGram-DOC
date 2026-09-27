// Transporte HTTP em Node para o cliente Python do Zenhub (src/zenhub/client.py).
//
// Existe porque em algumas máquinas Windows o TLS do Python (OpenSSL) é cortado
// no meio por antivírus/firewall (SSLEOFError), enquanto o Node conecta normal.
// O Python chama este script uma vez por requisição:
//   stdin : {"url": "...", "body": {...}, "timeoutMs": 60000}
//   env   : ZENHUB_AUTH="Bearer <chave>"   (por variável de ambiente, nunca por argumento)
//   stdout: {"status": 200, "headers": {...}, "body": "<texto>"}  ou  {"erro": "..."}
// Requer Node 18+ (fetch nativo). Não imprime a chave.

const entrada = await new Promise((ok) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => (s += c));
  process.stdin.on("end", () => ok(s));
});

try {
  const { url, body, timeoutMs } = JSON.parse(entrada);
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: process.env.ZENHUB_AUTH || "" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs || 60000),
  });
  const headers = {};
  resp.headers.forEach((v, k) => (headers[k.toLowerCase()] = v));
  process.stdout.write(JSON.stringify({ status: resp.status, headers, body: await resp.text() }));
} catch (e) {
  const tipo = e?.name === "TimeoutError" || e?.name === "AbortError" ? "timeout" : "rede";
  const causa = e?.cause?.code || e?.cause?.message || "";
  process.stdout.write(JSON.stringify({ erro: `${tipo}: ${e?.message || e} ${causa}`.trim() }));
}
