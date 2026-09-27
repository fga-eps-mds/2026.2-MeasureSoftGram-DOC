"""Paleta e constantes visuais do dashboard.

As cores categóricas vêm de uma paleta validada para daltonismo (deuteranopia,
protanopia e tritanopia). A ordem dos slots é o mecanismo de segurança: atribua
sempre na ordem, nunca cicle. Até três séries simultâneas por gráfico.
"""

# Slots categóricos — atribuir em ordem, nunca ciclar
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

# Status — reservados, nunca usados como "série 4".
# Acompanham sempre rótulo ou ícone: a cor nunca carrega o significado sozinha.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Rampa sequencial (magnitude), azul claro -> escuro
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

INK = {
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "surface": "#fcfcfb",
}

# Limiares da disciplina. Ver docs/disciplina/avaliacao.mdx
METAS = {
    "coverage": {"R1": 85.0, "R2": 85.0, "R3": 90.0},
    "duplicated_lines_density": {"R1": 5.0, "R2": 5.0, "R3": 3.0},
}

# Nome legível de cada métrica do SonarCloud e se "maior é melhor"
METRICAS = {
    "coverage": ("Cobertura de testes", "%", True),
    "duplicated_lines_density": ("Densidade de duplicação", "%", False),
    "comment_lines_density": ("Densidade de comentários", "%", True),
    "complexity": ("Complexidade ciclomática", "", False),
    "ncloc": ("Linhas de código", "", None),
    "files": ("Arquivos", "", None),
    "functions": ("Funções", "", None),
    "tests": ("Testes", "", True),
    "test_errors": ("Erros de teste", "", False),
    "test_failures": ("Falhas de teste", "", False),
    "test_success_density": ("Sucesso dos testes", "%", True),
    "test_execution_time": ("Tempo de execução dos testes", "ms", False),
    "reliability_rating": ("Rating de confiabilidade", "", False),
    "security_rating": ("Rating de segurança", "", False),
}


def status_por_meta(metrica: str, valor: float, release: str = "R1") -> str:
    """Devolve a chave de status de um valor frente à meta da release."""
    meta = METAS.get(metrica, {}).get(release)
    if meta is None or valor is None:
        return "neutral"
    maior_melhor = METRICAS.get(metrica, (None, None, None))[2]
    if maior_melhor is None:
        return "neutral"
    if maior_melhor:
        if valor >= meta:
            return "good"
        return "warning" if valor >= meta * 0.9 else "critical"
    if valor <= meta:
        return "good"
    return "warning" if valor <= meta * 1.5 else "critical"
