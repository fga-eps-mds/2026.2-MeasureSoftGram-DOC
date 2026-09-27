// Coleta as sprints do Zenhub e grava data/zenhub/zenhub-sprints-AAAA-MM-DD.json.
// Versão em Node do coleta_zenhub.py, para máquinas em que o Python não
// consegue abrir a conexão TLS com api.zenhub.com (antivírus/proxy).
//
// Uso (Node 18+):  node scripts/coleta_zenhub.mjs
// Lê ZENHUB_TOKEN e ZENHUB_WORKSPACE de Analytics/.env ou do ambiente.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");
const envPath = join(RAIZ, ".env");
if (existsSync(envPath)) {
  for (const linha of readFileSync(envPath, "utf-8").split(/\r?\n/)) {
    const l = linha.trim();
    if (!l || l.startsWith("#") || !l.includes("=")) continue;
    const i = l.indexOf("=");
    const k = l.slice(0, i).trim();
    const v = l.slice(i + 1).trim().replace(/^["']|["']$/g, "");
    if (!(k in process.env)) process.env[k] = v;
  }
}

const TOKEN = process.env.ZENHUB_TOKEN;
const WS = process.env.ZENHUB_WORKSPACE || "6a8326e265e211000ef9379a";
if (!TOKEN ) {
  console.error("Defina ZENHUB_TOKEN no Analytics/.env");
  process.exitCode = 1;
  throw new Error("sem token");
}

const consulta = (fragTipo) => `
query($ws: ID!) {
  workspace(id: $ws) {
    sprints(first: 50) {
      nodes {
        id name startAt endAt
        issues(first: 100) {
          pageInfo { hasNextPage }
          nodes {
            number title state htmlUrl
            repository { name }
            issueType { __typename ${fragTipo} }
            estimate { value }
            parentIssue { number repository { name } }
            pipelineIssue(workspaceId: $ws) { pipeline { name } }
          }
        }
      }
    }
  }
}`;

try {
async function gql(query, variables = {}) {
  const resp = await fetch("https://api.zenhub.com/public/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` },
    body: JSON.stringify({ query, variables }),
  });
  if (resp.status === 401) throw new Error("Token recusado (401). Gere outro em Zenhub > Settings > API.");
  const corpo = await resp.json();
  if (!resp.ok || corpo.errors) throw new Error("Erro do Zenhub: " + JSON.stringify(corpo.errors || corpo, null, 1));
  return corpo.data;
}


const intro = await gql(`{ __type(name: "IssueIssueType") { possibleTypes { name } } }`);
const membros = intro.__type?.possibleTypes?.map((t) => t.name) ?? [];
const fragTipo = membros.map((m) => `... on ${m} { name }`).join(" ");

const corpo = { data: await gql(consulta(fragTipo), { ws: WS }) };

const sprints = corpo.data.workspace.sprints.nodes.map((s) => {
  const completo = !s.issues.pageInfo.hasNextPage;
  if (!completo) console.warn(`Aviso: ${s.name} tem mais de 100 issues; coleta parcial.`);
  const issues = s.issues.nodes.map((i) => ({
    numero: i.number,
    repositorio: i.repository.name,
    titulo: i.title,
    tipo: i.issueType?.name ?? null,
    estimativa: i.estimate?.value ?? null,
    estado: i.state,
    pipeline: i.pipelineIssue?.pipeline?.name ?? null,
    pai: i.parentIssue?.number ?? null,
    pai_repositorio: i.parentIssue?.repository?.name ?? null,
    url: i.htmlUrl,
  }));
  return { id: s.id, nome: s.name, inicio: s.startAt, fim: s.endAt, completo,
           total_issues: issues.length, issues };
}).sort((a, b) => a.inicio.localeCompare(b.inicio));

const agora = new Date(Date.now() - 3 * 3600 * 1000); // horário de Brasília
const dia = agora.toISOString().slice(0, 10);
const saida = join(RAIZ, "data", "zenhub");
mkdirSync(saida, { recursive: true });
const destino = join(saida, `zenhub-sprints-${dia}.json`);
writeFileSync(destino, JSON.stringify({
  fonte: `Zenhub GraphQL, workspace ${WS}`,
  coletado_em: agora.toISOString().replace("Z", "-03:00"),
  sprints,
}, null, 1), "utf-8");
console.log(`Gravado ${destino} (${sprints.length} sprints)`);
} catch (erro) {
  console.error(erro.message);
  process.exitCode = 1;
}
