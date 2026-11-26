"""Evidências de uso de IA generativa: o que foi pedido, onde, se o resultado foi aceito ou descartado e por quê.

Fonte: ``data/ia/evidencias.json``, curado à mão pela equipe (não há coleta automática).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ARQUIVO = Path(__file__).resolve().parents[2] / "data" / "ia" / "evidencias.json"
CAMPOS = ("data", "area", "pedido", "onde", "link", "resultado", "motivo")
AREAS = ("Código", "Documentação", "Análise de dados do dashboard")
RESULTADOS = ("aceito", "descartado")


def evidencias(caminho: Path = ARQUIVO) -> pd.DataFrame:
    """Lê e valida o arquivo; um registro malformado interrompe a leitura com o número da linha e o campo."""
    itens = json.loads(Path(caminho).read_text(encoding="utf-8"))
    for n, item in enumerate(itens, 1):
        faltando = [c for c in CAMPOS if not str(item.get(c) or "").strip()]
        if faltando:
            raise ValueError(f"evidência {n}: campo(s) vazio(s) ou ausente(s): {', '.join(faltando)}")
        if item["area"] not in AREAS:
            raise ValueError(f"evidência {n}: área '{item['area']}' fora de {AREAS}")
        if item["resultado"] not in RESULTADOS:
            raise ValueError(f"evidência {n}: resultado '{item['resultado']}' fora de {RESULTADOS}")
    df = pd.DataFrame(itens, columns=list(CAMPOS))
    df["data"] = pd.to_datetime(df["data"], format="%Y-%m-%d")
    return df.sort_values("data", ascending=False, kind="stable").reset_index(drop=True)
