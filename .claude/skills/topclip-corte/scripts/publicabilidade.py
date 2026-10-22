"""Nota de publicabilidade — a conta do gate do `finalize`, antecipada.

O `finalize` (`reports.consolidate_final`) só dá a nota no fim da fase 3, quando
já não dá mais para trocar de momento. Esta é a mesma conta, para usar antes:

* fase 1 — sobre as notas que o Clip Hunter estima para cada momento
  (`estimated_scores` em `05-viral-moments.json`);
* fase 2 — sobre as notas do Clip Builder somadas às da revisão de feed, como o
  `finalize` faz (`06-candidates.json` + `07-feed-review.json`).

`tests/test_publicabilidade.py` confere que esta conta e a do `finalize` dão o
mesmo número — se uma mudar sem a outra, o teste quebra.
"""
from __future__ import annotations

from typing import Any

CRITICOS = ("proposition_clarity", "payoff", "self_contained", "truthfulness")
NOME_CRITICO = {
    "proposition_clarity": "clareza da proposta",
    "payoff": "payoff",
    "self_contained": "se sustenta sozinho",
    "truthfulness": "fidelidade",
}


def _num(v: Any, casas: int = 1) -> str:
    """7.0 -> "7", 7.5 -> "7,5", 7.483 com 2 casas -> "7,48" (vírgula, como o painel mostra)."""
    texto = f"{float(v):.{casas}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def nota(scores: dict[str, Any], pesos: dict[str, Any]) -> float:
    """Média ponderada × (0,70 + 0,30 × pior item crítico / 10). Item crítico ausente vale 0."""
    soma = total = 0.0
    for nome, peso in pesos.items():
        if nome in scores:
            soma += float(scores[nome]) * float(peso)
            total += float(peso)
    media = soma / total if total else 0.0
    piso = min(float(scores.get(k, 0)) for k in CRITICOS)
    return round(media * (0.70 + 0.30 * piso / 10.0), 3)


def abaixo_do_gate(scores: dict[str, Any], valor: float, selecao: dict[str, Any]) -> list[str]:
    """Por que a nota não passaria no gate do `finalize`. Lista vazia = passaria."""
    minimo = float(selecao.get("minimum_publishability_score", 7.5))
    critico = float(selecao.get("minimum_critical_score", 7.0))
    fidelidade = float(selecao.get("truthfulness_gate", 9.0))
    motivos = []
    infiel = float(scores.get("truthfulness", 0)) < fidelidade
    if infiel:
        motivos.append(f"fidelidade {_num(scores.get('truthfulness', 0))} < {_num(fidelidade)}")
    pior = min(CRITICOS, key=lambda k: float(scores.get(k, 0)))
    if float(scores.get(pior, 0)) < critico and not (pior == "truthfulness" and infiel):
        motivos.append(f"{NOME_CRITICO[pior]} {_num(scores.get(pior, 0))} < {_num(critico)}")
    if valor < minimo:
        motivos.append(f"nota {_num(valor, 2)} < {_num(minimo)}")
    return motivos


def faltando(scores: dict[str, Any] | None, pesos: dict[str, Any]) -> list[str]:
    """Notas que a conta usa e não vieram."""
    scores = scores or {}
    return [k for k in list(pesos) + [c for c in CRITICOS if c not in pesos] if k not in scores]


def estimar_momentos(doc: dict[str, Any], config: dict[str, Any]) -> dict[str, list[str]]:
    """Grava `publishability_estimate` e `estimate_below_gate` em cada momento.

    Devolve {id: notas faltando} dos momentos que ficaram sem nota.
    """
    pesos = config.get("scoring_weights", {})
    selecao = config.get("selection", {})
    incompletos = {}
    for m in doc.get("moments", []):
        scores = m.get("estimated_scores")
        falta = faltando(scores, pesos)
        if falta:
            incompletos[str(m.get("id"))] = falta
            m.pop("publishability_estimate", None)
            m.pop("estimate_below_gate", None)
            continue
        valor = nota(scores, pesos)
        m["publishability_estimate"] = valor
        m["estimate_below_gate"] = abaixo_do_gate(scores, valor, selecao)
    doc["estimate_gate"] = float(selecao.get("minimum_publishability_score", 7.5))
    return incompletos


def estimar_cortes(candidatos: dict[str, Any], feed: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """Grava a nota em cada corte de `06-candidates.json`, com as notas do feed por cima
    das do Builder (como o `finalize`). Devolve os ids que ainda não têm revisão de feed."""
    pesos = config.get("scoring_weights", {})
    selecao = config.get("selection", {})
    revisoes = {str(r.get("clip_id")): r for r in feed.get("reviews", []) if r.get("clip_id") is not None}
    sem_feed = []
    for c in candidatos.get("clips", []):
        scores = dict(c.get("scores", {}))
        revisao = revisoes.get(str(c.get("id")))
        if revisao:
            scores.update(revisao.get("scores", {}))
        else:
            sem_feed.append(str(c.get("id")))
        valor = nota(scores, pesos)
        c["publishability_estimate"] = valor
        c["estimate_below_gate"] = abaixo_do_gate(scores, valor, selecao)
    candidatos["estimate_gate"] = float(selecao.get("minimum_publishability_score", 7.5))
    return sem_feed
