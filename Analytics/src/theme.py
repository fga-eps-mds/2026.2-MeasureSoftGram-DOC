"""Identidade visual do dashboard: a mesma paleta da documentação.

As cores vêm de ``src/css/custom.css`` do site (IDV oficial do MeasureSoftGram):

    primária  #2B4D6F   secundária  #5F7EA3   fundo  #F4F5F6
    erro      #D13310   sucesso     #04724D   aviso  #DF8E16
    tipografia: Roboto (texto) · Quattrocento (marca)

Regras de uso:

* **Cor tem significado.** Verde/amarelo/vermelho só para status (conforme,
  atenção, crítico); cinza para informação neutra. Status sempre acompanha
  rótulo em texto — a cor nunca carrega o significado sozinha.
* **Séries** usam a primária e a secundária da IDV e, como terceira, um cinza.
  A paleta da marca é propositalmente sóbria (pouca saturação), então cada
  gráfico com mais de uma série tem legenda e codificação secundária
  (tracejado, rótulo direto ou tabela). Nunca mais de três séries por gráfico:
  com mais categorias (ex.: repositórios) o gráfico destaca uma e deixa as
  outras em cinza, ou vira tabela.
"""

from __future__ import annotations

IDV = {
    "primaria": "#2B4D6F",
    "primaria_escura": "#24405C",
    "secundaria": "#5F7EA3",
    "fundo": "#F4F5F6",
    "superficie": "#FFFFFF",
    "erro": "#D13310",
    "sucesso": "#04724D",
    "aviso": "#DF8E16",
}

# Tinta (texto, eixos, grade) em cinzas frios, coerentes com a primária.
INK = {
    "primary": "#1F2933",
    "secondary": "#4B5563",
    "muted": "#6B7280",
    "grid": "#E5E7EB",
    "axis": "#C9CED6",
    "surface": "#FFFFFF",
    "border": "#DDE1E6",
}

# Séries — atribuir sempre nesta ordem, nunca ciclar.
SERIES = [IDV["primaria"], IDV["secundaria"], "#9AA5B1"]
NEUTRO = "#9AA5B1"          # contexto (ex.: os outros repositórios)
NEUTRO_CLARO = "#D5DAE0"

# Status — reservados. "neutral" = informativo, sem meta.
STATUS = {
    "good": IDV["sucesso"],
    "warning": IDV["aviso"],
    "critical": IDV["erro"],
    "neutral": "#6B7280",
    "unavailable": "#9AA5B1",
}
ROTULO_STATUS = {
    "good": "Conforme",
    "warning": "Atenção",
    "critical": "Crítico",
    "neutral": "Informativo",
    "unavailable": "Indisponível",
}
ORDEM_STATUS = {"critical": 0, "warning": 1, "good": 2, "neutral": 3, "unavailable": 4}

# Rampa sequencial (magnitude) na matiz da primária, clara -> escura.
SEQUENCIAL = ["#E6ECF2", "#C3D0DE", "#98ADC5", "#6F8CAE", "#4A6D93", "#2B4D6F", "#1B3450"]

# Exposição de risco (P × I): baixo, médio, elevado — tons claros dos status.
RISCO = {"Baixo": "#CFE5DC", "Médio": "#F7E1BD", "Elevado": "#F2C4B8"}

# Rótulo curto de cada fonte (aparece como etiqueta em cada bloco).
FONTES = {
    "SONAR": ("SonarCloud", "#2B4D6F"),
    "ZENHUB": ("Zenhub", "#5F7EA3"),
    "PLANILHA": ("Planilha", "#4B5563"),
    "GITHUB": ("GitHub", "#6B7280"),
    "CALCULADO": ("Calculado", "#6B7280"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Quattrocento:wght@700&display=swap');

html, body, .stApp, .stMarkdown, p, li, label, input, textarea, h1, h2, h3, h4, td, th {
  font-family: 'Roboto', system-ui, -apple-system, 'Segoe UI', Arial, sans-serif;
}
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }
h1, h2, h3, h4 { color: #1F2933; letter-spacing: -0.005em; }
h2 { font-size: 1.35rem !important; font-weight: 700 !important; }
h3 { font-size: 1.1rem !important; font-weight: 600 !important; }
h4 { font-size: 1rem !important; font-weight: 600 !important; }

/* Cabeçalho */
.msg-topo { border-bottom: 1px solid #DDE1E6; padding-bottom: .75rem; margin-bottom: 1rem; }
.msg-marca { font-family: 'Quattrocento', Georgia, serif; font-weight: 700; color: #2B4D6F;
             font-size: 1.05rem; letter-spacing: .01em; }
.msg-titulo { font-size: 1.55rem; font-weight: 700; color: #1F2933; margin: .1rem 0 .35rem; line-height: 1.2; }
.msg-meta { color: #4B5563; font-size: .85rem; display: flex; flex-wrap: wrap; gap: .35rem 1.1rem; }
.msg-meta b { color: #1F2933; font-weight: 500; }

/* Etiqueta de fonte */
.msg-fonte { display: inline-block; font-size: .68rem; font-weight: 700; letter-spacing: .06em;
             text-transform: uppercase; color: #FFFFFF; border-radius: 3px; padding: .08rem .4rem;
             vertical-align: middle; }
.msg-fonte-contorno { background: transparent !important; border: 1px solid currentColor; }

/* Pergunta gerencial acima de cada bloco */
.msg-secao { margin: 1.6rem 0 .5rem; }
.msg-secao h3 { margin: 0 !important; padding: 0 !important; }
.msg-pergunta { color: #4B5563; font-size: .9rem; margin-top: .15rem; }

/* KPI */
.msg-kpi { background: #FFFFFF; border: 1px solid #DDE1E6; border-left: 4px solid var(--kpi-cor, #9AA5B1);
           border-radius: 6px; padding: .7rem .85rem .65rem; height: 100%; min-height: 118px; }
.msg-kpi-topo { display: flex; justify-content: space-between; align-items: center; gap: .4rem; }
.msg-kpi-rotulo { color: #4B5563; font-size: .8rem; font-weight: 500; }
.msg-kpi-valor { color: #1F2933; font-size: 1.55rem; font-weight: 700; line-height: 1.25; margin-top: .2rem;
                 font-variant-numeric: tabular-nums; }
.msg-kpi-valor.indisponivel { color: #9AA5B1; font-size: 1.15rem; font-weight: 500; }
.msg-kpi-delta { font-size: .8rem; color: #4B5563; margin-top: .1rem; font-variant-numeric: tabular-nums; }
.msg-kpi-status { font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
.msg-kpi-nota { font-size: .75rem; color: #6B7280; margin-top: .25rem; line-height: 1.3; }

/* Situação geral */
.msg-status-geral { background: #FFFFFF; border: 1px solid #DDE1E6; border-radius: 6px; padding: .9rem 1rem;
                    border-top: 4px solid var(--kpi-cor, #9AA5B1); }
.msg-status-geral .rotulo { font-size: .8rem; color: #4B5563; font-weight: 500; }
.msg-status-geral .valor { font-size: 1.3rem; font-weight: 700; margin: .15rem 0; }

/* Dado indisponível */
.msg-tabela { overflow: auto; border: 1px solid #E1E5EA; border-radius: 8px; margin: .3rem 0 .8rem; }
.msg-tabela table { border-collapse: collapse; width: 100%; font-size: .85rem; }
.msg-tabela th { position: sticky; top: 0; background: #F4F5F6; color: #52606D; font-weight: 500; text-align: left;
  padding: .45rem .6rem; border-bottom: 1px solid #E1E5EA; }
.msg-tabela td { padding: .4rem .6rem; border-bottom: 1px solid #EEF0F2; vertical-align: top; }
.msg-tabela .num { text-align: right; white-space: nowrap; }
.msg-tabela a { color: #2B4D6F; text-decoration: underline; }
.msg-ausente { background: #F9FAFB; border: 1px dashed #C9CED6; border-radius: 6px; padding: .7rem .9rem;
               color: #4B5563; font-size: .88rem; margin: .4rem 0 .8rem; }
.msg-ausente b { color: #1F2933; }

/* Lista de pontos de atenção */
.msg-alerta { border-left: 3px solid var(--kpi-cor, #9AA5B1); background: #FFFFFF; padding: .45rem .75rem;
              margin-bottom: .4rem; border-radius: 0 4px 4px 0; font-size: .9rem; color: #1F2933; }
.msg-alerta .st { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
                  margin-right: .45rem; }
.msg-alerta .onde { color: #6B7280; font-size: .8rem; }

/* Sidebar */
section[data-testid="stSidebar"] { border-right: 1px solid #DDE1E6; }
section[data-testid="stSidebar"] h2 { font-size: .8rem !important; text-transform: uppercase; letter-spacing: .06em;
                                     color: #4B5563; }
div[data-testid="stExpander"] details { border-color: #DDE1E6; background: #FFFFFF; }
</style>
"""


def cor_status(status: str) -> str:
    return STATUS.get(status, STATUS["neutral"])


def pior(status: list[str]) -> str:
    """Status mais grave entre os que têm meta (ignora neutro e indisponível)."""
    validos = [s for s in status if s in ("good", "warning", "critical")]
    return min(validos, key=ORDEM_STATUS.get) if validos else "neutral"
