"""Versão de cada corte e revisões feitas sobre versão velha.

Uma revisão (07 feed, 09 cega, 12 qualidade) vale para os segmentos que o
revisor viu. Na run de docs/12, o `finalize` consolidou um 07 feito sobre a
versão anterior do corte e deu REBUILD indevido — a revisão de feed foi refeita
DEPOIS do Quality Controller, que também teve de rodar de novo.

Versão do corte = hash da cobertura na fonte, em ordem (segmentos seguidos na
fonte contam como um: a emenda interna do autoframe não muda a versão). Borda
que o `bordas` levou ao vale entra com o valor de antes do ajuste: o ajuste não
tira nem põe palavra, então não é versão nova e não manda revisar de novo. Base:

* 07 e 09 revisam o candidato -> hash dos `segments` do 06;
* 12 revisa o plano -> hash da `timeline` do 11 (o 06 se o clipe não tem plano).

Os revisores são subagentes e não escrevem hash. Quem carimba é o script: cada
entrada sem carimbo ganha o hash da versão em vigor quando o arquivo de revisão
foi gravado. Para saber qual era, o manifesto guarda, por clipe, o hash atual e
desde quando ele vale (mtime do 06/11 que o mudou). Revisão gravada antes disso
é de versão velha e recebe `segments_hash: "versao-anterior"`. O carimbo leva
também `stamped_content`, a impressão do texto da entrada: se o revisor
reescreve a entrada por cima (mantendo o carimbo velho), a impressão não bate e
ela é carimbada de novo.

Todo `./topclip corte` de fase 2/3 sincroniza (o `bordas`, logo depois do Clip
Builder, abre o registro antes de qualquer revisão); `revisoes` e `finalize`
cobram. Run que já existia antes deste registro tem as revisões aceitas na
primeira passada — sem histórico, não há como provar que são velhas.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.tempos import GAP_CONTIGUO, ordenar
from scripts.utils import HarnessError, load_json, update_manifest, write_json

REVISOES = (
    ("07-feed-review.json", "06", "feed-psychologist"),
    ("09-blind-review.json", "06", "blind-reviewer"),
    ("12-quality-review.json", "11", "quality-controller"),
)
BASES = {"06": ("06-candidates.json", "clips", "id", "segments"), "11": ("11-edit-plans.json", "plans", "clip_id", "timeline")}
VERSAO_ANTERIOR = "versao-anterior"
CHAVE_MANIFESTO = "cut_versions"
CAMPOS_CARIMBO = ("segments_hash", "stamped_content")


def _borda_autoral(seg: dict[str, Any], lado: str, chave: str) -> float:
    """O valor que quem escreveu o corte deu à borda (antes do ajuste do `bordas`)."""
    valor = float(seg[chave])
    registro = (seg.get("edge_audio") or {}).get(lado)
    if (
        isinstance(registro, dict) and registro.get("action") == "moved" and "from" in registro
        and abs(float(registro.get("t", -1)) - valor) < 0.0005
    ):
        return float(registro["from"])
    return valor


def cobertura(segmentos: list[dict[str, Any]]) -> list[list[float]]:
    faixas: list[list[float]] = []
    for seg in ordenar(segmentos):
        a, b = _borda_autoral(seg, "start", "source_start"), _borda_autoral(seg, "end", "source_end")
        if faixas and abs(a - faixas[-1][1]) < GAP_CONTIGUO:
            faixas[-1][1] = b
        else:
            faixas.append([a, b])
    return [[round(a, 2), round(b, 2)] for a, b in faixas]


def hash_corte(segmentos: list[dict[str, Any]]) -> str:
    texto = json.dumps(cobertura(segmentos), separators=(",", ":"))
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


def impressao(review: dict[str, Any]) -> str:
    """Hash do conteúdo da entrada de revisão, sem os campos do próprio carimbo."""
    conteudo = {k: v for k, v in review.items() if k not in CAMPOS_CARIMBO}
    texto = json.dumps(conteudo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


def _ler(path: Path) -> Any:
    try:
        return load_json(path) if path.exists() else None
    except HarnessError:
        return None  # JSON quebrado é problema do validate-artifact, não daqui


def hashes_atuais(run: Path) -> dict[str, dict[str, str]]:
    atuais: dict[str, dict[str, str]] = {}
    for base, (nome, lista, chave, campo) in BASES.items():
        doc = _ler(run / nome) or {}
        atuais[base] = {}
        for item in doc.get(lista, []) if isinstance(doc, dict) else []:
            segmentos = item.get(campo) or []
            try:
                atuais[base][str(item.get(chave))] = hash_corte(segmentos)
            except (KeyError, TypeError, ValueError):
                continue
    return atuais


def hash_para(run: Path, clip_id: str, base: str = "11") -> str | None:
    atuais = hashes_atuais(run)
    return atuais.get(base, {}).get(clip_id) or atuais["06"].get(clip_id)


def relevantes(run: Path) -> set[str] | None:
    """Clipes que importam agora: os do 11 (aprovados para vertical) quando ele existe."""
    plano = _ler(run / "11-edit-plans.json")
    if isinstance(plano, dict) and plano.get("plans"):
        return {str(p.get("clip_id")) for p in plano["plans"]}
    return None


def sincronizar(run: Path, carimbar: bool = True) -> dict[str, Any]:
    """Atualiza o registro de versões, carimba revisões e lista as desatualizadas."""
    run = Path(run)
    manifest = _ler(run / "00-manifest.json") or {}
    registro = {base: dict(v) for base, v in (manifest.get(CHAVE_MANIFESTO) or {}).items()}
    atuais = hashes_atuais(run)
    registro_mudou = False
    for base, (nome, *_rest) in BASES.items():
        caminho = run / nome
        if not caminho.exists():
            continue
        # Primeira passada nesta run: sem histórico, não há como saber se uma
        # revisão já gravada é velha. Aceita o que existe ("desde sempre") em vez
        # de travar run antiga; daqui em diante cada mudança tem data.
        primeira_vez = base not in registro
        desde = 0.0 if primeira_vez else caminho.stat().st_mtime
        livro = registro.setdefault(base, {})
        for clip_id, h in atuais[base].items():
            if (livro.get(clip_id) or {}).get("hash") != h:
                livro[clip_id] = {"hash": h, "since": desde}
                registro_mudou = True
        registro_mudou = registro_mudou or primeira_vez
    if registro_mudou:
        update_manifest(run, **{CHAVE_MANIFESTO: registro})

    desatualizadas: list[dict[str, Any]] = []
    carimbadas: list[dict[str, str]] = []
    for nome, base, agente in REVISOES:
        caminho = run / nome
        doc = _ler(caminho)
        if not isinstance(doc, dict) or not isinstance(doc.get("reviews"), list):
            continue
        gravada_em = caminho.stat().st_mtime
        alterou = False
        for review in doc["reviews"]:
            if not isinstance(review, dict):
                continue
            clip_id = str(review.get("clip_id"))
            usada = base if clip_id in atuais.get(base, {}) else "06"
            atual = atuais.get(usada, {}).get(clip_id)
            if atual is None:
                continue  # clipe não existe mais na base
            carimbo = review.get("segments_hash")
            if not carimbo or review.get("stamped_content") != impressao(review):
                # sem carimbo, ou reescrita depois do carimbo: vale a data do arquivo
                desde = (registro.get(usada, {}).get(clip_id) or {}).get("since", 0.0)
                carimbo = atual if gravada_em + 1e-6 >= desde else VERSAO_ANTERIOR
                if carimbar:
                    review["segments_hash"] = carimbo
                    review["stamped_content"] = impressao(review)
                    alterou = True
                    carimbadas.append({"arquivo": nome, "clip_id": clip_id, "segments_hash": carimbo})
            if carimbo != atual:
                desatualizadas.append({
                    "arquivo": nome,
                    "clip_id": clip_id,
                    "refazer_com": agente,
                    "motivo": (
                        "feita antes da última mudança do corte" if carimbo == VERSAO_ANTERIOR
                        else f"feita sobre outra versão do corte ({carimbo}; atual {atual})"
                    ),
                })
        if alterou:
            write_json(caminho, doc)
    return {"hashes": atuais, "desatualizadas": desatualizadas, "carimbadas": carimbadas}


def tentar_sincronizar(run: Path) -> dict[str, Any] | None:
    """Para os comandos que só aproveitam a passagem: nunca derruba o comando."""
    try:
        return sincronizar(run)
    except (HarnessError, OSError, ValueError):
        return None


def mensagem_desatualizadas(desatualizadas: list[dict[str, Any]]) -> str:
    linhas = ["Revisão feita sobre versão anterior do corte — refaça antes do Quality Controller/finalize:"]
    for item in desatualizadas:
        linhas.append(f"  - {item['arquivo']} · {item['clip_id']}: {item['motivo']} → refazer com `{item['refazer_com']}`")
    linhas.append("Depois de refazer, rode `./topclip corte revisoes --run <run>` até sair limpo.")
    return "\n".join(linhas)
