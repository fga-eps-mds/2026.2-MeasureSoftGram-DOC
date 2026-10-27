"""Qualidade (Q-Rapids) — nota de qualidade do produto e modelo completo, do dado bruto à nota.

Duas visões, cada número com fórmula, peso, limiar e de onde veio:

1. **Nota do notebook (oficial)** — o mesmo cálculo do notebook da disciplina
   (``src/metrics/qualidade.py``; o teste ``tests/test_qualidade_notebook.py`` garante que o número é
   igual ao do notebook em todas as coletas). Árvore: nota total → aspecto → fator → métrica → arquivos.
2. **Modelo Q-Rapids completo** — todas as métricas do *Q-Rapids Quality Model* (``src/metrics/qrapids.py``):
   indicadores estratégicos → fatores → métricas → dado bruto, com o que não tem fonte explicado.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
from src.components import charts, filters, layout, rastreio
from src.components.kpi import kpi
from src.data.sonar import nome_curto
from src.metrics import qrapids
from src.metrics import qualidade as nq
from src.metrics.calculations import data_br

ESCOPO = {
    "release": "define o período padrão e a comparação R1 × R2",
    "periodo": "nota na última coleta até o fim do período; evolução e métricas de processo dentro do período",
    "repos": "repositórios avaliados (métricas do Sonar, CI e issues)",
    "branch": "coletas do pipeline desta branch",
}
TODOS = "Todos (média dos repositórios)"
PESOS, LIM = config.QRAPIDS["pesos"], config.QRAPIDS["limiares"]
JSON_BASE = "https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC/blob/main/Analytics/data/"


def _n(v, casas=2) -> str:
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{casas}f}".replace(".", ",")


def _status(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    return "good" if v >= 0.7 else ("warning" if v >= 0.5 else "critical")


def _menus():
    layout.menus([
        ("Métrica avaliada", "proporção de 0 a 1 (1 = melhor) calculada a partir do dado bruto",
         "ex.: arquivos não complexos ÷ total de arquivos", [("q-rapids model-doc.pdf",
                                                            "https://github.com/fga-eps-mds/Analytics")]),
        ("Fator", "agrupa métricas de um mesmo assunto (qualidade do código, situação dos testes...)",
         "Σ peso × métrica", []),
        ("Aspecto / indicador", "característica de qualidade (ISO 25010) ou indicador estratégico do Q-Rapids",
         "nota oficial: fator × peso do aspecto; modelo completo: média dos fatores calculados", []),
        ("0 por falta de dado", "regra do notebook: métrica que não pode ser calculada vale 0",
         "marcada na tela para não ser confundida com 0 medido", []),
        ("Situação da métrica (modelo completo)", "Calculada, Sem dado no recorte, Coleta pendente, Sem fonte no "
         "projeto, Repete outra métrica, Só informativa", "só as Calculadas entram na média", []),
    ], [
        *[(f"Limiar · {k}", str(v), "config.py · QRAPIDS['limiares']", rastreio.codigo()) for k, v in LIM.items()],
        *[(f"Peso · {k}", str(v), "config.py · QRAPIDS['pesos']", rastreio.codigo()) for k, v in PESOS.items()],
    ], fontes=["SONAR", "GITHUB", "ZENHUB", "CALCULADO"])


# ───────────────────────── nota do notebook ─────────────────────────

def _media(notas: dict, caminho, metrica: str | None = None) -> float | None:
    return qrapids.media_repos(notas, caminho, metrica)[0]


def _tabela_repos(notas: dict) -> pd.DataFrame:
    linhas = []
    for repo, n in sorted(notas.items()):
        a = n["avaliacao"]
        sg = a["seguranca"]
        linhas.append({"Repositório": nome_curto(repo), "Nota total": a["total"],
                       "Nota com segurança": a["total_seguranca"],
                       "Manutenibilidade": a["aspectos"]["manutenibilidade"]["valor"],
                       "Confiabilidade": a["aspectos"]["confiabilidade"]["valor"],
                       "Segurança": sg["valor"],
                       "Nota de segurança (Sonar)": (sg["letra"] or "—") + (" · crítico (veto)" if a["veto_seguranca"]
                                                                              else ""),
                       "Vulnerabilidades": sg["vulnerabilidades"],
                       **{nq.METRICAS[m][0].split(" (")[0]: r["valor"] for m, r in a["metricas"].items()},
                       "Arquivos na base": a["arquivos_base"], "Linguagem": a["linguagem"],
                       "Zeros por falta de dado": ", ".join(nq.METRICAS[m][0].split(" (")[0]
                                                            for m, r in a["metricas"].items() if r["zero_por_falta"]),
                       "Coleta": n["coleta"], "Arquivo .json": layout.link_celula(JSON_BASE + n["arquivo"],
                                                                                  n["arquivo"])})
    return pd.DataFrame(linhas)


def _notebook(notas: dict, sel: str | None):
    a_sel = notas[sel]["avaliacao"] if sel else None

    def val(fn, metrica=None):
        return fn(a_sel) if a_sel else _media(notas, fn, metrica)

    fora = qrapids.media_repos(notas, lambda a: a["total"])[1]

    total = val(lambda a: a["total"])
    man = val(lambda a: a["aspectos"]["manutenibilidade"]["valor"])
    con = val(lambda a: a["aspectos"]["confiabilidade"]["valor"])
    if a_sel:
        seg, total_seg = a_sel["seguranca"]["valor"], a_sel["total_seguranca"]
        vetados = [nome_curto(sel)] if a_sel["veto_seguranca"] else []
    else:
        seg = qrapids.media_seguranca(notas, "seguranca")[0]
        total_seg, _, vetados = qrapids.media_seguranca(notas)
    ps = nq.PESOS_SEG
    alvo = nome_curto(sel) if sel else f"média de {len(notas) - len(fora)} repositórios"
    layout.secao("Nota de qualidade", f"Qual é a qualidade do produto ({alvo}) e de onde vem a nota?",
                 ["SONAR", "CALCULADO"])
    k = st.columns(5)
    with k[0]:
        kpi("Nota total", _n(total), "CALCULADO", status=_status(total),
            nota=f"{PESOS['manutenibilidade']:g} × Manutenibilidade + {PESOS['confiabilidade']:g} × Confiabilidade"
                 f" = {PESOS['manutenibilidade']:g} × {_n(man)} + {PESOS['confiabilidade']:g} × {_n(con)}")
    with k[1]:
        kpi("Manutenibilidade", _n(man), "CALCULADO", status=_status(man), nota="= Qualidade do código")
    with k[2]:
        kpi("Confiabilidade", _n(con), "CALCULADO", status=_status(con), nota="= Situação dos testes")
    with k[3]:
        kpi("Segurança", _n(seg), "SONAR", status="critical" if vetados else _status(seg),
            nota="(5 − nota de segurança do Sonar) ÷ 4 · A = 1 … E = 0"
                 + (f" · crítico: {', '.join(vetados)}" if vetados else ""))
    with k[4]:
        kpi("Nota com segurança", _n(total_seg), "CALCULADO", status="critical" if vetados else _status(total_seg),
            nota=f"{ps['manutenibilidade']:g} × Manut. + {ps['confiabilidade']:g} × Conf. + {ps['seguranca']:g} × "
                 "Segurança · extensão do time")
    if vetados:
        layout.alerta("critical", f"Nota de segurança D ou E no SonarCloud: {', '.join(vetados)}. Pela regra de veto, "
                                  "o repositório é crítico mesmo com nota total alta. Ver vulnerabilidades no "
                                  "SonarCloud.")
    if fora and not sel:
        layout.alerta("warning", f"Fora da média por não terem nenhum dado no .json do pipeline: {', '.join(fora)}. "
                                 "No notebook a nota deles seria 0 (regra: métrica sem dado vale 0). Ver o motivo na "
                                 "tabela por repositório.")
    st.caption("Escala de 0 a 1 (1 = melhor). Status: ≥ 0,7 conforme · 0,5 a 0,7 atenção · < 0,5 crítico "
               "(faixas de leitura do painel, não do notebook). No notebook, Manutenibilidade e Confiabilidade já "
               "saem multiplicadas por 0,5; aqui elas aparecem de 0 a 1 e o 0,5 entra na nota total — o total é o "
               "mesmo. **Nota total** = a do notebook (oficial da disciplina). **Nota com segurança** = extensão do "
               "time: o notebook não tem segurança, e uma nota E no Sonar não mudava a nota. Pesos e veto em "
               "config.py · QRAPIDS['seguranca'].")

    layout.secao("Por repositório", "Como cada repositório se sai e de qual coleta veio o número?", ["SONAR"])
    t = _tabela_repos(notas)
    num = {c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="%.2f")
           for c in ("Nota total", "Nota com segurança", "Manutenibilidade", "Confiabilidade", "Segurança")}
    num["Vulnerabilidades"] = st.column_config.NumberColumn(format="%d")
    num.update({nq.METRICAS[m][0].split(" (")[0]: st.column_config.NumberColumn(format="%.2f") for m in nq.METRICAS})
    st.dataframe(t, use_container_width=True, hide_index=True, column_config={
        **num, "Coleta": st.column_config.DatetimeColumn("Coleta", format="DD/MM/YYYY HH:mm"),
        "Arquivo .json": layout.coluna_link("Arquivo .json", help="abre o .json do pipeline no GitHub")})
    csv = t.assign(**{"Arquivo .json": t["Arquivo .json"].map(layout.texto_de_link)})
    st.download_button("Baixar CSV (nota por repositório)", csv.to_csv(index=False).encode("utf-8-sig"),
                       file_name="qualidade_notebook_por_repositorio.csv", mime="text/csv", key="csv_q_repos")

    layout.secao("Como a nota foi calculada", "Do aspecto até o arquivo: qual número entra em qual conta?",
                 ["SONAR", "CALCULADO"])
    st.caption(f"Detalhando: **{alvo}**. Escolha um repositório em *Repositório do detalhamento*, na barra lateral, "
               "para ver os arquivos de cada métrica.")
    for asp, (nome_asp, fator) in nq.ASPECTOS.items():
        nome_f, _, metricas = nq.FATORES[fator]
        vf = val(lambda a, fator=fator: a["fatores"][fator]["valor"])
        partes = [(m, val(lambda a, m=m: a["metricas"][m]["valor"], m)) for m in metricas]
        conta = " + ".join(f"{PESOS[m]:g} × {_n(v)}" for m, v in partes)
        with st.expander(f"{nome_asp} = {_n(vf)}  ·  {nome_f} = {conta} (× {PESOS[fator]:g})", expanded=True):
            linhas = []
            for m, v in partes:
                nome, _, _, regra, formula = nq.METRICAS[m]
                if a_sel:
                    r = a_sel["metricas"][m]
                    calc = (f"{int(r['numerador']) if r['numerador'] is not None else '—'} ÷ "
                            f"{int(r['denominador']) if r['denominador'] is not None else '—'}")
                    obs = r["zero_por_falta"] or r.get("observacao", "")
                else:
                    calc = "média dos repositórios com o dado"
                    obs = ", ".join(nome_curto(rp) for rp, n in notas.items()
                                    if n["avaliacao"]["metricas"][m]["zero_por_falta"])
                    obs = f"fora da média (sem o dado; no notebook valeria 0): {obs}" if obs else ""
                linhas.append({"Métrica": nome, "Regra (limiar)": regra, "Fórmula": formula, "Conta": calc,
                               "Valor": v, "Peso": PESOS[m], "Contribuição": (v or 0) * PESOS[m] * PESOS[fator],
                               "Observação": obs})
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True, column_config={
                "Valor": st.column_config.ProgressColumn("Valor", min_value=0, max_value=1, format="%.2f"),
                "Contribuição": st.column_config.NumberColumn(format="%.3f"),
                "Fórmula": st.column_config.TextColumn(width="medium"),
                "Observação": st.column_config.TextColumn(width="large")})
            abas = st.tabs([nq.METRICAS[m][0].split(" (")[0] for m in metricas])
            for aba, m in zip(abas, metricas):
                with aba:
                    _dado_bruto(notas, sel, m)

    # Segurança (extensão do time): repo a repo, a nota A–E do Sonar convertida em 0 a 1
    reps = [sel] if sel else sorted(notas)
    seg_t = pd.DataFrame([{"Repositório": nome_curto(r), "Nota de segurança (Sonar)": notas[r]["avaliacao"]["seguranca"]["letra"] or "—",
                           "Segurança (0 a 1)": notas[r]["avaliacao"]["seguranca"]["valor"],
                           "Vulnerabilidades": notas[r]["avaliacao"]["seguranca"]["vulnerabilidades"],
                           "Veto": "crítico" if notas[r]["avaliacao"]["veto_seguranca"] else "",
                           "Avaliada em": notas[r]["avaliacao"]["seguranca"]["coleta"]} for r in reps])
    with st.expander(f"Segurança = {_n(seg)}  ·  (5 − nota do Sonar) ÷ 4 · extensão do time, fora da nota oficial",
                     expanded=True):
        st.dataframe(seg_t, use_container_width=True, hide_index=True, column_config={
            "Segurança (0 a 1)": st.column_config.ProgressColumn("Segurança (0 a 1)", min_value=0, max_value=1,
                                                                 format="%.2f"),
            "Vulnerabilidades": st.column_config.NumberColumn(format="%d"),
            "Avaliada em": st.column_config.DatetimeColumn("Avaliada em", format="DD/MM/YYYY HH:mm")})
        st.caption("A nota de segurança do SonarCloud depende da vulnerabilidade mais grave: A = nenhuma, B = menor, "
                   "C = maior, D = crítica, E = bloqueante. Vem da última avaliação até o fim do período (pipeline "
                   f"ou API), que pode ser mais recente que a coleta da nota. Veto: nota ≥ {nq.LETRA[nq.RATING_VETO]} "
                   "→ repositório crítico.")


def _dado_bruto(notas, sel, m):
    nome, _, _, regra, _ = nq.METRICAS[m]
    if not sel:
        d = pd.DataFrame([{"Repositório": nome_curto(rp), "Numerador": n["avaliacao"]["metricas"][m]["numerador"],
                           "Denominador": n["avaliacao"]["metricas"][m]["denominador"],
                           "Valor": n["avaliacao"]["metricas"][m]["valor"],
                           "0 por falta de dado": n["avaliacao"]["metricas"][m]["zero_por_falta"] or ""}
                          for rp, n in sorted(notas.items())])
        st.dataframe(d, use_container_width=True, hide_index=True, column_config={
            "Valor": st.column_config.NumberColumn(format="%.2f")})
        return
    r = notas[sel]["avaliacao"]["metricas"][m]
    st.caption(f"Regra: **{regra}** · {nome_curto(sel)}, coleta {data_br(notas[sel]['coleta'], True)} "
               f"(`{notas[sel]['arquivo']}`)" + (f" · {r['observacao']}" if r.get("observacao") else ""))
    if r["zero_por_falta"]:
        layout.indisponivel(f"{nome}: 0 por falta de dado", r["zero_por_falta"])
        return
    itens = r["itens"]
    if itens is None or itens.empty:
        st.caption("Sem itens.")
        return
    t = itens.rename(columns={"componente": "Arquivo / pasta / suíte", "valor": "Valor medido",
                              "passa": "Passa no limiar", "sem_tempo": "Sem tempo (conta 0 ms)",
                              "testes": "Testes", "erros": "Erros", "falhas": "Falhas"})
    if "Passa no limiar" in t:
        n_nao = int((~t["Passa no limiar"]).sum())
        st.caption(f"{len(t)} itens · {n_nao} não passam — são eles que puxam a métrica para baixo.")
    st.dataframe(t, use_container_width=True, hide_index=True, height=min(420, 38 + 35 * len(t)),
                 column_config={"Valor medido": st.column_config.NumberColumn(format="%.2f")})
    st.download_button("Baixar CSV", t.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"qualidade_{m}_{nome_curto(sel)}.csv", mime="text/csv", key=f"csv_q_{m}")


# ───────────────────────── modelo completo ─────────────────────────

def _completo(res: dict):
    layout.secao("Indicadores estratégicos do Q-Rapids", "Como está o produto e o processo em cada indicador?",
                 ["SONAR", "GITHUB", "ZENHUB", "CALCULADO"])
    ind = res["indicadores"]
    k = st.columns(len(ind))
    for col, r in zip(k, ind.itertuples()):
        with col:
            kpi(r.nome.split(" (")[0], _n(r.valor) if r.valor is not None and not pd.isna(r.valor) else None,
                "CALCULADO", status=_status(r.valor),
                nota=f"média de {r.fatores_na_media} de {r.fatores} fatores" if r.fatores_na_media else
                "nenhum fator com métrica calculada")
    cont = qrapids.resumo_situacao(res["metricas"])
    st.caption(f"{len(res['metricas'])} métricas do model-doc · " + " · ".join(f"{k}: {v}" for k, v in cont.items() if v)
               + ". O model-doc não fixa pesos: fator = média das métricas calculadas; indicador = média dos fatores.")

    por_fator = {}
    for r in res["metricas"]:
        por_fator.setdefault(r.fator, []).append(r)
    fat = res["fatores"].set_index("fator")
    for ic, (nome_i, desc, fatores) in qrapids.INDICADORES.items():
        vi = ind.set_index("indicador").loc[ic, "valor"]
        layout.secao(f"{nome_i} = {_n(vi)}", desc)
        for fc in fatores:
            nome_f, aspecto, tipo = qrapids.FATORES[fc]
            vf = fat.loc[fc, "valor"]
            mets = por_fator.get(fc, [])
            calc = [r for r in mets if r.situacao == qrapids.CALCULADA]
            conta = " + ".join(_n(r.valor) for r in calc)
            titulo = (f"{nome_f} = {_n(vf)}" + (f"  ·  ({conta}) ÷ {len(calc)}" if len(calc) > 1 else "")
                      + f"  ·  aspecto {aspecto}, fator de {tipo}")
            with st.expander(titulo, expanded=False):
                t = pd.DataFrame([{"Métrica": r.nome, "Situação": qrapids.ROTULO[r.situacao], "Valor (0–1)": r.valor,
                                   "Número bruto": r.bruto, "Fórmula": r.formula, "Dado bruto": r.dado_bruto,
                                   "Fonte": r.fonte, "Observação": r.motivo} for r in mets])
                st.dataframe(t, use_container_width=True, hide_index=True, column_config={
                    "Valor (0–1)": st.column_config.ProgressColumn("Valor (0–1)", min_value=0, max_value=1,
                                                                  format="%.2f"),
                    "Fórmula": st.column_config.TextColumn(width="medium"),
                    "Observação": st.column_config.TextColumn(width="large")})
                com_dado = [r for r in mets if (r.itens is not None and not r.itens.empty)
                            or (r.por_repo is not None and not r.por_repo.empty)]
                if com_dado:
                    abas = st.tabs([r.nome.split(" — ")[0] for r in com_dado])
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
    st.download_button("Baixar CSV (modelo completo)", tab.to_csv(index=False).encode("utf-8-sig"),
                       file_name="qrapids_modelo_completo.csv", mime="text/csv", key="csv_q_completo")


# ───────────────────────── evolução e R1 × R2 ─────────────────────────

def _evolucao(ctx, f, rec):
    layout.secao("Evolução da nota", "A qualidade está melhorando ao longo das coletas?", ["SONAR", "CALCULADO"])
    s = qrapids.serie_notebook(ctx, f, rec)
    if s.empty:
        layout.indisponivel("Sem coletas no período", "nenhum .json do pipeline no período escolhido.")
    else:
        s = s.assign(repo=s["repositorio"].map(nome_curto), dia=pd.to_datetime(s["coleta"]).dt.normalize())
        d = s.sort_values("coleta").drop_duplicates(["repo", "dia"], keep="last")
        linha = (alt.Chart(d).mark_line(point=True, strokeWidth=2)
                 .encode(x=alt.X("dia:T", title="Data da coleta", axis=alt.Axis(format="%d/%m")),
                         y=alt.Y("total:Q", title="Nota total (0 a 1)", scale=alt.Scale(domain=[0, 1])),
                         color=alt.Color("repo:N", title="Repositório"),
                         tooltip=[alt.Tooltip("repo:N", title="Repositório"),
                                  alt.Tooltip("dia:T", title="Data", format="%d/%m/%Y"),
                                  alt.Tooltip("total:Q", title="Nota", format=".2f"),
                                  alt.Tooltip("total_seguranca:Q", title="Nota com segurança", format=".2f"),
                                  alt.Tooltip("seguranca:Q", title="Segurança", format=".2f"),
                                  alt.Tooltip("manutenibilidade:Q", format=".2f"),
                                  alt.Tooltip("confiabilidade:Q", format=".2f")]))
        charts.mostrar(linha + charts.marcos_release(d["dia"].min(), d["dia"].max()),
                       "Nota total por repositório", "última coleta de cada dia · pontilhado: entregas das releases",
                       d[["repo", "dia", "total", "total_seguranca", "manutenibilidade", "confiabilidade", "seguranca",
                          *nq.METRICAS, "arquivo"]],
                       altura=300)

    layout.secao("Comparação entre releases", "A nota melhorou da R1 para a R2?", ["SONAR", "CALCULADO"])
    linhas = []
    for rel in config.RELEASES:
        ini, fim = filters.janela_release(rel)
        if ini > ctx.hoje:
            continue
        f2 = {**f, "periodo": (ini, fim)}
        notas = qrapids.notas_por_repo(ctx, f2, filters.sonar(ctx, f2))
        for repo, n in notas.items():
            a = n["avaliacao"]
            linhas.append({"release": rel, "repositorio": nome_curto(repo), "total": a["total"],
                           "manutenibilidade": a["aspectos"]["manutenibilidade"]["valor"],
                           "confiabilidade": a["aspectos"]["confiabilidade"]["valor"],
                           "seguranca": a["seguranca"]["valor"], "total com segurança": a["total_seguranca"],
                           "coleta": n["coleta"]})
    if not linhas:
        layout.indisponivel("Sem releases com coleta", "nenhuma release com .json do pipeline até a entrega.")
        return
    d = pd.DataFrame(linhas)
    piv = d.pivot_table(index="repositorio", columns="release", values="total").reset_index()
    rels = [r for r in config.RELEASES if r in piv]
    if len(rels) >= 2:
        piv[f"Variação {rels[-2]}→{rels[-1]}"] = piv[rels[-1]] - piv[rels[-2]]
    st.dataframe(piv.rename(columns={"repositorio": "Repositório"}), use_container_width=True, hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.2f") for c in piv.columns
                                if c != "repositorio"})
    st.caption("Nota total na última coleta até a entrega de cada release (a R2 em andamento usa a coleta mais "
               "recente). Detalhe com coletas usadas:")
    layout.tabela(d.assign(coleta=d["coleta"].map(lambda x: data_br(x, True))), "Ver as coletas de cada release")


# ───────────────────────── parâmetros e dados ─────────────────────────

def _parametros(ctx, f, rec, res):
    layout.secao("Parâmetros e justificativas", "Por que esses limiares e pesos?", ["CALCULADO"])
    j = config.QRAPIDS["justificativa"]
    linhas = [{"Parâmetro": k, "Valor": v, "Origem": "notebook da disciplina / model-doc" if k in (
        "complexidade_por_funcao", "comentarios_min", "comentarios_max", "duplicacao_max", "cobertura_min",
        "teste_rapido_ms") else "definido pelo time (model-doc: 'user defined')",
               "Justificativa do time": j.get(k, "a preencher pelo time")} for k, v in LIM.items()]
    linhas += [{"Parâmetro": f"peso · {k}", "Valor": v, "Origem": "notebook da disciplina",
                "Justificativa do time": j.get("pesos", "a preencher pelo time")} for k, v in PESOS.items()]
    linhas += [{"Parâmetro": f"segurança · peso {k}", "Valor": v, "Origem": "definido pelo time (extensão)",
                "Justificativa do time": j.get("seguranca_pesos", "a preencher pelo time")}
               for k, v in nq.PESOS_SEG.items()]
    linhas.append({"Parâmetro": "segurança · veto (security_rating ≥)", "Valor": nq.RATING_VETO,
                   "Origem": "definido pelo time (extensão)",
                   "Justificativa do time": j.get("seguranca_veto", "a preencher pelo time")})
    t = pd.DataFrame(linhas)
    st.dataframe(t, use_container_width=True, hide_index=True,
                 column_config={"Justificativa do time": st.column_config.TextColumn(width="large")})
    faltam = int((t["Justificativa do time"] == "a preencher pelo time").sum())
    if faltam:
        layout.alerta("warning", f"{faltam} parâmetro(s) sem justificativa do time: a R2 pede métricas "
                                 "interpretadas pelo time. Preencher em config.py · QRAPIDS['justificativa'].",
                      link=("config.py", rastreio.codigo()))

    layout.secao("Fidelidade ao notebook", "O número do painel é o mesmo do notebook?", ["CALCULADO"])
    st.markdown(f"""
- O cálculo está em [`src/metrics/qualidade.py`]({rastreio.codigo('src/metrics/qualidade.py')}) e segue as funções do
  notebook `internal_quality_analysis-sonarqube.ipynb` (fga-eps-mds/Analytics).
- O teste [`tests/test_qualidade_notebook.py`]({rastreio.codigo('tests/test_qualidade_notebook.py')}) roda as funções
  **copiadas do notebook** (`tests/referencia_notebook.py`) e o painel nos mesmos `.json` de `Analytics/data/` e
  exige o mesmo resultado em todas as coletas. O teste roda no workflow de coleta a cada atualização dos dados.
- Regras do notebook mantidas: só arquivos da linguagem do repositório com linhas de código; o mesmo conjunto de
  arquivos para complexidade, comentários, duplicação e cobertura; testes que passam pela pasta com mais testes;
  suíte sem tempo conta como rápida; métrica sem dado vale 0 (aqui marcada).
""")

    layout.secao("Os dados existem?", "Cada métrica do modelo completo tem dado coletado?", ["SONAR", "GITHUB", "ZENHUB"])
    t = qrapids.tabela(res["metricas"])
    sit = t.groupby("situacao").size().reset_index(name="métricas")
    st.dataframe(sit.rename(columns={"situacao": "Situação"}), hide_index=True)
    pend = t[t["situacao"].isin([qrapids.ROTULO[qrapids.PENDENTE], qrapids.ROTULO[qrapids.SEM_DADO],
                                 qrapids.ROTULO[qrapids.SEM_FONTE]])]
    layout.tabela_html(pend, {"fator": "Fator", "metrica": "Métrica", "situacao": "Situação",
                              "observacao": "O que falta"}, altura=None)


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
    layout.titulo_pagina("Qualidade (Q-Rapids)", "Nota de qualidade do produto pelo modelo Q-Rapids: do arquivo "
                         "à nota, com a fórmula de cada passo.", ["SONAR", "GITHUB", "ZENHUB"])
    _menus()
    rec = filters.sonar(ctx, f)
    rec = {**rec, "repos": [r for r in rec["repos"] if r in config.QRAPIDS["linguagem"]]}
    caixa = filters.da_pagina(f, ESCOPO)
    notas = qrapids.notas_por_repo(ctx, f, rec)
    opcoes = [TODOS] + sorted(notas, key=nome_curto)
    sel = caixa.selectbox("Repositório do detalhamento", opcoes, format_func=lambda r: r if r == TODOS
                          else nome_curto(r), key="q_repo",
                          help="a árvore da nota oficial mostra os arquivos deste repositório")
    sel = None if sel == TODOS else sel
    st.caption(f"Situação no fim do período ({data_br(rec['fim'])}) · {filters.resumo_ativos(f, ESCOPO)}")

    t1, t2, t3, t4 = st.tabs(["Nota do notebook (oficial)", "Modelo Q-Rapids completo", "Evolução e releases",
                              "Parâmetros e dados"])
    with t1:
        if not notas:
            layout.indisponivel("Sem nota de qualidade", "nenhuma coleta do pipeline até o fim do período para os "
                                "repositórios escolhidos.", "rodar o metrics.yml nos repositórios.")
        else:
            _seguro("Nota do notebook", _notebook, notas, sel)
    res = _seguro("Modelo Q-Rapids completo", qrapids.calcular, ctx, f, rec)
    with t2:
        if res is not None:
            _seguro("Modelo Q-Rapids completo", _completo, res)
    with t3:
        _seguro("Evolução e releases", _evolucao, ctx, f, rec)
    with t4:
        if res is not None:
            _seguro("Parâmetros e dados", _parametros, ctx, f, rec, res)
