"""Qualidade (Q-Rapids) — os quatro indicadores estratégicos do plano de qualidade, do dado bruto ao indicador.

Segue ``docs/planejamento/selecaometricas.mdx`` (quais métricas entram) e ``docs/planejamento/metas.mdx``
(fórmula, metas da R3, piso e portões). O cálculo está em ``src/metrics/qrapids.py``; esta página só mostra:

1. **Indicadores estratégicos** — Product Quality, Blocking, Process Performance e Product Readiness em
   R1, R2 e hoje, com meta da R3, piso (valor da R2), situação e portões;
2. **Fatores e métricas** — a conta de cada fator e cada métrica com fórmula, dado bruto e fonte;
3. **Evolução dos indicadores** — R1 → R2 → hoje contra a meta, e a série de M9 por sprint;
4. **Portões e catálogo** — as condições obrigatórias e as 44 métricas do Q-Rapids com a decisão do plano.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src import theme
from src.components import charts, filters, layout, rastreio
from src.components.kpi import kpi
from src.metrics import qrapids

ESCOPO = {
    "release": None,
    "periodo": None,
    "repos": "repositórios avaliados (métricas do Sonar, CI e issues)",
    "branch": "coletas do pipeline desta branch",
}
PLANO = config.QRAPIDS["plano"]
LIM = config.QRAPIDS["limiares"]
JANELAS = ("R1", "R2", "Atual")
STATUS_KPI = {"🟢 Atingido": "good", "🟡 Em evolução": "warning", "🔴 Abaixo do piso": "critical"}
CORES = [theme.SEQUENCIAL[6], theme.IDV["secundaria"], theme.NEUTRO, theme.SEQUENCIAL[3]]


def _n(v, casas=2) -> str:
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{casas}f}".replace(".", ",")


def _menus():
    layout.menus([
        ("Indicador estratégico", "Product Quality, Blocking, Process Performance ou Product Readiness",
         "soma dos fatores avaliados com peso 1/n; fator sem dado sai do denominador (nunca vale zero)",
         [("metas.mdx", "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/metas/")]),
        ("Fator", "agrupa métricas de um mesmo assunto (ex.: Code Quality = M1 e M2)",
         "média simples das métricas incluídas, todas em 0–1 (1 = melhor)", []),
        ("Métrica incluída", "uma das 10 métricas que entram na agregação (M1, M2, M3, M5, M6, M7, M8, M9, M10, DT)",
         "dado bruto → limiar ou função de utilidade → valor de 0 a 1",
         [("selecaometricas.mdx",
           "https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/planejamento/selecaometricas/")]),
        ("Métrica monitorada", "aparece no painel e pode gerar alerta, mas não tem peso em nenhum fator",
         "valor calculado, fora de qualquer média", []),
        ("Meta da R3", "meta de 30/11 definida na métrica; a do fator é a média das metas das métricas e a do "
         "indicador é a fórmula aplicada às metas dos fatores, truncada em 2 casas", "ver metas.mdx", []),
        ("Piso", "valor do indicador na R2: abaixo dele o indicador regrediu", "🔴 abaixo do piso · 🟡 entre o piso "
         "e a meta · 🟢 na meta ou acima, com todos os portões passando", []),
        ("Portão", "condição obrigatória fora da média (M8 em minutos, metas globais da disciplina)",
         "o indicador só conta como atingido se a meta e todos os seus portões passarem", []),
        ("Atual", "do dia seguinte à entrega da R2 até hoje; no Sonar, a última coleta até lá",
         "M9 usa a última sprint concluída; DT usa a release em andamento (parcial)", []),
    ], [
        *[(f"Meta · {qrapids.METRICAS[k][0]} {qrapids.METRICAS[k][1]}", f"≥ {_n(v)}", "config.py · QRAPIDS['plano']",
           rastreio.codigo()) for k, v in PLANO["metas"].items()],
        ("Portão M8", f"mediana ≤ {PLANO['portao_ci_mediana_min']:g} min", "config.py · QRAPIDS['plano']", rastreio.codigo()),
        ("Meta de cobertura global (R3)", f"≥ {config.METAS['coverage']['R3']:g}%", "config.py · METAS", rastreio.codigo()),
        ("Meta de duplicação global (R3)", f"≤ {config.METAS['duplicated_lines_density']['R3']:g}%",
         "config.py · METAS", rastreio.codigo()),
        *[(f"Limiar · {k}", str(v), "config.py · QRAPIDS['limiares']", rastreio.codigo()) for k, v in LIM.items()],
    ], fontes=["SONAR", "GITHUB", "ZENHUB", "CALCULADO"])


# ───────────────────────── indicadores estratégicos ─────────────────────────

def _indicadores(av: dict):
    ind = av["indicadores"]
    layout.secao("Indicadores estratégicos", "Onde está cada indicador em relação ao piso (R2) e à meta da R3?",
                 ["SONAR", "GITHUB", "ZENHUB", "CALCULADO"])
    cols = st.columns(len(ind))
    for col, r in zip(cols, ind.itertuples()):
        with col:
            ok = {True: "portões ok", False: "portão reprovado", None: "portão sem dado"}[r.portoes_ok]
            kpi(r.nome, _n(r.Atual) if pd.notna(r.Atual) else None, "CALCULADO", status=STATUS_KPI.get(r.situacao),
                nota=f"{r.situacao} · meta ≥ {_n(r.meta)} · piso {_n(r.piso)} (R2) · {ok}")
    ate = av["janelas"]["Atual"][1]
    st.caption(f"Escala de 0 a 1 (1 = melhor). Atual = 27/10 a {ate:%d/%m/%Y}. Situação: 🔴 abaixo do piso (valor da R2) · "
               "🟡 entre o piso e a meta · 🟢 na meta, com todos os portões passando.")

    layout.secao("Resumo das metas", "Quanto cada indicador valia na R1 e na R2 e quanto falta para a meta?", ["CALCULADO"])
    gates = {r.nome: _gates(av["portoes"], r.nome) for r in ind.itertuples()}
    t = pd.DataFrame([{"Indicador": r.nome, "Fatores avaliados": r.avaliados, "R1": r.R1, "R2 (piso)": r.R2,
                       "Atual": r.Atual, "Meta R3": r.meta, "Situação": r.situacao, "Portões": gates[r.nome]}
                      for r in ind.itertuples()])
    st.dataframe(t, use_container_width=True, hide_index=True, column_config={
        **{c: st.column_config.NumberColumn(c, format="%.2f") for c in ("R1", "R2 (piso)", "Atual")},
        "Meta R3": st.column_config.NumberColumn("Meta R3", format="≥ %.2f"),
        "Portões": st.column_config.TextColumn(width="large")})
    st.caption("Blocking na R1 e na R2 usa 2 fatores: a coleta de violações por arquivo (Blocking Code) só existe a "
               "partir de 07/11. Product Readiness em andamento é parcial e só deve ser comparado ao piso no "
               "fechamento da release.")
    csv = t.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Baixar CSV (indicadores)", csv, file_name="qrapids_indicadores.csv", mime="text/csv",
                       key="csv_q_ind")

    layout.secao("Portões obrigatórios", "Quais condições ficam fora da média e precisam passar?",
                 ["SONAR", "GITHUB", "CALCULADO"])
    _portoes(av["portoes"])


def _gates(port: pd.DataFrame, indicador: str) -> str:
    x = port[port["indicador"].str.contains(indicador, regex=False)]
    if x.empty:
        return "—"
    return " · ".join(("✅ " if p is True else "❌ " if p is False else "⚪ ") + g.split(" em cada")[0].split(" em ")[0]
                      for g, p in zip(x["portao"], x["passa"]))


def _portoes(port: pd.DataFrame):
    t = port.assign(Situação=port["passa"].map({True: "✅ Passa", False: "❌ Reprova"}).fillna("⚪ Sem dado"))
    st.dataframe(t.rename(columns={"portao": "Portão", "indicador": "Indicador", "detalhe": "Detalhe"})[
        ["Portão", "Indicador", "Situação", "Detalhe"]], use_container_width=True, hide_index=True,
        column_config={"Detalhe": st.column_config.TextColumn(width="large")})
    st.caption("Os portões não entram na média: são metas globais da disciplina (cobertura, duplicação) ou grandezas "
               "fora de 0–1 (M8). Cobertura e duplicação usam o último valor global de cada repositório no SonarCloud.")


# ───────────────────────── fatores e métricas ─────────────────────────

def _fatores_e_metricas(av: dict):
    res = av["res"]["Atual"]
    met, fat = av["metricas"], av["fatores"].set_index("fator")
    ind = av["indicadores"].set_index("indicador")
    por_fator = {}
    for r in res["metricas"]:
        por_fator.setdefault(r.fator, []).append(r)
    for ic, (nome_i, desc, fatores) in qrapids.INDICADORES.items():
        avaliados = qrapids.AVALIADOS[ic]
        formula = " + ".join(qrapids.FATORES[fc][0] for fc in avaliados)
        layout.secao(f"{nome_i} = {_n(ind.loc[ic, 'Atual'])}",
                     f"{desc}. Fórmula: ({formula}) ÷ {len(avaliados)} · meta ≥ {_n(ind.loc[ic, 'meta'])}")
        for fc in fatores:
            nome_f, tipo, motivo = qrapids.FATORES[fc]
            mets = por_fator.get(fc, [])
            incl = [r for r in mets if r.decisao == qrapids.INCLUIDA]
            calc = [r for r in incl if r.na_media]
            conta = " + ".join(_n(r.valor) for r in calc)
            vf = fat.loc[fc, "Atual"]
            if fc in avaliados:
                titulo = (f"{nome_f} = {_n(vf)}" + (f"  ·  ({conta}) ÷ {len(calc)}" if len(calc) > 1 else "")
                          + f"  ·  meta ≥ {_n(fat.loc[fc, 'meta'])}  ·  fator de {tipo}")
            else:
                titulo = f"{nome_f}  ·  fora do cálculo: {motivo}  ·  fator de {tipo}"
            with st.expander(titulo, expanded=False):
                if not mets:
                    st.caption("Nenhuma métrica incluída nem monitorada neste fator: " + motivo + ".")
                    continue
                _tabela_metricas(mets, met)
                com_dado = [r for r in mets if (r.itens is not None and not r.itens.empty)
                            or (r.por_repo is not None and not r.por_repo.empty)]
                if com_dado:
                    abas = st.tabs([r.nome for r in com_dado])
                    for aba, r in zip(abas, com_dado):
                        with aba:
                            st.caption(f"{r.descricao} · {r.formula}")
                            if r.por_repo is not None and not r.por_repo.empty:
                                st.markdown("**Por repositório**")
                                st.dataframe(r.por_repo, use_container_width=True, hide_index=True)
                            if r.itens is not None and not r.itens.empty:
                                st.markdown(f"**Dado bruto** ({len(r.itens)} itens)")
                                st.dataframe(r.itens, use_container_width=True, hide_index=True,
                                             height=min(380, 38 + 35 * len(r.itens)))
    tab = qrapids.tabela(res["metricas"])
    st.download_button("Baixar CSV (métricas)", tab.to_csv(index=False).encode("utf-8-sig"),
                       file_name="qrapids_metricas.csv", mime="text/csv", key="csv_q_metricas")


def _tabela_metricas(mets: list, met: pd.DataFrame):
    m = met.set_index("chave")
    linhas = []
    for r in mets:
        x = m.loc[r.chave]
        linhas.append({"Métrica": r.nome, "Decisão do plano": ("Incluída: entra no fator" if r.decisao == qrapids.INCLUIDA
                                                               else "Monitorada: sem peso"),
                       "R1": x["R1"], "R2": x["R2"], "Atual": x["Atual"], "Meta R3": x["meta"],
                       "Tipo de meta": x["tipo_meta"], "Situação": qrapids.ROTULO[r.situacao],
                       "Conta atual": r.bruto, "Fórmula": r.formula, "Dado bruto": r.dado_bruto, "Fonte": r.fonte,
                       "Observação": r.motivo})
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True, column_config={
        **{c: st.column_config.NumberColumn(c, format="%.2f") for c in ("R1", "R2", "Atual")},
        "Meta R3": st.column_config.NumberColumn("Meta R3", format="≥ %.2f"),
        "Fórmula": st.column_config.TextColumn(width="medium"),
        "Observação": st.column_config.TextColumn(width="large")})
    if any(r.chave == "ci_feedback_time" for r in mets):
        st.caption("M8 está em minutos (mediana do test.yml): é portão e fica fora da média do fator.")


# ───────────────────────── evolução dos indicadores ─────────────────────────

def _evolucao(av: dict):
    layout.secao("Evolução dos indicadores", "Os indicadores estão melhorando da R1 para hoje e chegam à meta da R3?",
                 ["SONAR", "GITHUB", "ZENHUB", "CALCULADO"])
    ind = av["indicadores"]
    ate = av["janelas"]["Atual"][1]
    ordem = ["R1", "R2", f"Atual ({ate:%d/%m})", "Meta R3"]
    linhas = []
    for r in ind.itertuples():
        for rel, v in (("R1", r.R1), ("R2", r.R2), (ordem[2], r.Atual)):
            linhas.append({"Indicador": r.nome, "Ponto": rel, "Valor": v, "Tipo": "Valor"})
        linhas.append({"Indicador": r.nome, "Ponto": "Meta R3", "Valor": r.meta, "Tipo": "Meta"})
    d = pd.DataFrame(linhas).dropna(subset=["Valor"])
    nomes = list(ind["nome"])
    cor = alt.Color("Indicador:N", scale=alt.Scale(domain=nomes, range=CORES[:len(nomes)]), title="Indicador")
    x = alt.X("Ponto:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y("Valor:Q", scale=alt.Scale(domain=[0, 1]), title="Valor do indicador (0 a 1)")
    tip = [alt.Tooltip("Indicador:N"), alt.Tooltip("Ponto:N"), alt.Tooltip("Valor:Q", format=".2f")]
    linha = alt.Chart(d[d["Tipo"] == "Valor"]).mark_line(point=True, strokeWidth=2).encode(x=x, y=y, color=cor, tooltip=tip)
    meta = alt.Chart(d[d["Tipo"] == "Meta"]).mark_point(shape="diamond", size=140, filled=True, opacity=.9).encode(
        x=x, y=y, color=cor, tooltip=tip)
    charts.mostrar(linha + meta, "Indicadores estratégicos: R1, R2, atual e meta da R3",
                   "losango = meta da R3 · a R2 é o piso de cada indicador",
                   d.drop(columns="Tipo"), altura=320)

    layout.secao("Fatores por release", "Qual fator puxa cada indicador?", ["CALCULADO"])
    f = av["fatores"]
    f = f[f["R1"].notna() | f["R2"].notna() | f["Atual"].notna()]
    st.dataframe(f.rename(columns={"nome": "Fator", "tipo": "Tipo", "meta": "Meta R3", "Atual": "Atual"})[
        ["Fator", "Tipo", "R1", "R2", "Atual", "Meta R3"]], use_container_width=True, hide_index=True,
        column_config={**{c: st.column_config.NumberColumn(c, format="%.2f") for c in ("R1", "R2", "Atual")},
                       "Meta R3": st.column_config.NumberColumn("Meta R3", format="≥ %.2f")})

    layout.secao("Métricas por release", "Quais métricas subiram ou caíram desde a R1?", ["CALCULADO"])
    m = av["metricas"]
    m = m[m["R1"].notna() | m["R2"].notna() | m["Atual"].notna()]
    st.dataframe(m.rename(columns={"codigo": "Código", "nome": "Métrica", "decisao": "Decisão", "meta": "Meta R3",
                                   "tipo_meta": "Tipo de meta"})[
        ["Código", "Métrica", "Decisão", "R1", "R2", "Atual", "Meta R3", "Tipo de meta"]],
        use_container_width=True, hide_index=True,
        column_config={**{c: st.column_config.NumberColumn(c, format="%.2f") for c in ("R1", "R2", "Atual")},
                       "Meta R3": st.column_config.NumberColumn("Meta R3", format="≥ %.2f")})
    st.caption("M8 está em minutos (mediana do test.yml); as demais, de 0 a 1.")

    _m9_por_sprint(av)


def _m9_por_sprint(av: dict):
    layout.secao("M9 Team throughput por sprint", "Cada sprint fecha o que planejou? A meta vale para cada sprint.",
                 ["ZENHUB", "CALCULADO"])
    partes = []
    for rel in JANELAS:
        r = next(x for x in av["res"][rel]["metricas"] if x.chave == "team_throughput")
        if r.itens is not None and not r.itens.empty:
            partes.append(r.itens.assign(release=rel))
    if not partes:
        layout.indisponivel("Sem sprints", "nenhuma sprint com issues no Zenhub nos períodos.")
        return
    d = pd.concat(partes).drop_duplicates("sprint", keep="last").sort_values("fim")
    d["Situação"] = d.apply(lambda x: "parcial" if not x["concluida"] else (
        "na meta" if x["valor"] is not None and x["valor"] >= PLANO["metas"]["team_throughput"] else "abaixo da meta"),
        axis=1)
    meta = PLANO["metas"]["team_throughput"]
    barras = alt.Chart(d.dropna(subset=["valor"])).mark_bar().encode(
        x=alt.X("sprint:N", sort=list(d["sprint"]), title="Sprint"), y=alt.Y("valor:Q", scale=alt.Scale(domain=[0, 1]),
                                                                              title="Fechadas ÷ planejadas"),
        color=alt.Color("Situação:N", scale=alt.Scale(domain=["na meta", "abaixo da meta", "parcial"],
                                                      range=[theme.cor_status("good"), theme.cor_status("critical"),
                                                             theme.NEUTRO_CLARO]), title=None),
        tooltip=[alt.Tooltip("sprint:N", title="Sprint"), alt.Tooltip("fechadas:Q", title="Fechadas"),
                 alt.Tooltip("planejadas:Q", title="Planejadas"), alt.Tooltip("valor:Q", title="M9", format=".2f")])
    charts.mostrar(barras + charts.regra_horizontal(meta, f"meta ≥ {_n(meta)}"), "M9 por sprint",
                   "issues da sprint (sem Epic, pacote de trabalho e Iniciativa) fechadas até 08:00 do dia seguinte ao "
                   "fim da sprint",
                   d[["sprint", "release", "fechadas", "planejadas", "valor", "Situação"]], altura=240)


# ───────────────────────── catálogo das 44 métricas ─────────────────────────

def _catalogo():
    layout.secao("Catálogo das 44 métricas do Q-Rapids", "O que o plano decidiu sobre cada métrica?", ["CALCULADO"])
    cat = qrapids.catalogo()
    incl = [(v[0], v[1]) for v in qrapids.METRICAS.values() if v[3] == qrapids.INCLUIDA]
    cont = {qrapids.INCLUIDA: len(incl), **cat["decisao"].value_counts().to_dict()}
    k = st.columns(4)
    for col, dec, txt in zip(k, (qrapids.INCLUIDA, qrapids.MONITORADA, qrapids.HABILITAVEL, qrapids.EXCLUIDA),
                             ("entram na agregação e têm meta para a R3", "aparecem no painel, sem peso",
                              "entram quando o time adotar a prática ou a coleta", "sem fonte, sem fórmula ou repetidas")):
        with col:
            kpi(dec + "s" if not dec.endswith("l") else dec[:-1] + "eis", str(cont.get(dec, 0)), "CALCULADO", nota=txt)
    if cat.empty:
        layout.indisponivel("Catálogo indisponível", "docs/planejamento/selecaometricas.mdx não foi encontrado neste "
                            "deploy.", "publicar a pasta docs/ junto com o painel")
        return
    st.caption("Texto lido de docs/planejamento/selecaometricas.mdx, para a tela nunca divergir do plano.")
    for dec in (qrapids.MONITORADA, qrapids.HABILITAVEL, qrapids.EXCLUIDA):
        x = cat[cat["decisao"] == dec]
        with st.expander(f"{dec}s ({len(x)})" if dec != qrapids.HABILITAVEL else f"Habilitáveis ({len(x)})",
                         expanded=False):
            cols = {"indicador_fator": "Indicador › Fator", "metrica": "Métrica", "justificativa": "Justificativa"}
            if dec == qrapids.EXCLUIDA:
                cols = {**cols, "motivo": "Motivo"}
            if dec == qrapids.HABILITAVEL:
                cols = {**cols, "condicao": "Condição para incluir"}
            st.dataframe(x[list(cols)].rename(columns=cols), use_container_width=True, hide_index=True, column_config={
                "Justificativa": st.column_config.TextColumn(width="large")})
    st.download_button("Baixar CSV (catálogo)", cat.to_csv(index=False).encode("utf-8-sig"),
                       file_name="qrapids_catalogo.csv", mime="text/csv", key="csv_q_catalogo")


def _seguro(bloco: str, fn, *args):
    """Roda um bloco da página; se ele falhar, mostra o erro só nele e o resto da página continua."""
    try:
        return fn(*args)
    except Exception as erro:  # noqa: BLE001 — um dado inesperado não derruba a página inteira
        import traceback
        traceback.print_exc()   # vai para o log do Streamlit Cloud (Manage app)
        layout.indisponivel(f"{bloco}: erro ao calcular",
                            f"{erro.__class__.__name__}: {str(erro)[:300]}",
                            "avise quem mantém o painel; os outros blocos continuam valendo.")
        return None


def pagina():
    ctx, f = layout.estado()
    layout.titulo_pagina("Qualidade (Q-Rapids)", "Indicadores estratégicos do plano de qualidade: do dado bruto ao "
                         "indicador, com a fórmula, a meta da R3 e o piso de cada passo.", ["SONAR", "GITHUB", "ZENHUB"])
    _menus()
    filters.da_pagina(f, ESCOPO)
    av = _seguro("Indicadores Q-Rapids", qrapids.avaliar_releases, ctx, f)
    if av is None:
        return
    st.caption("Comparação fixa R1 × R2 × atual (o período e a release da barra lateral não mudam esta página) · "
               + (filters.resumo_ativos(f, ESCOPO) or "todos os repositórios"))

    t1, t2, t3, t4 = st.tabs(["Indicadores estratégicos", "Fatores e métricas", "Evolução dos indicadores",
                              "Catálogo das métricas"])
    with t1:
        _seguro("Indicadores estratégicos", _indicadores, av)
    with t2:
        _seguro("Fatores e métricas", _fatores_e_metricas, av)
    with t3:
        _seguro("Evolução dos indicadores", _evolucao, av)
    with t4:
        _seguro("Catálogo", _catalogo)
