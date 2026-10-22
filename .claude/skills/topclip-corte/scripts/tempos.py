"""Tempos de clipe recalculados pela posição na fonte.

O candidato (06) e o plano (11) guardam tempo em duas bases: a FONTE
(`source_start`/`source_end`, o que o render corta) e o CLIPE (`clip_start`,
`clip_t`, `events.*_at` — onde legenda, card e motion entram). Mover uma borda
na fonte desliza todo tempo de clipe depois dela. Recalcular isso à mão, com
script avulso, foi o que fez a fase 3 levar 25 min para 2 clipes (docs/12).

Regra do mapeamento, de um tempo de clipe da versão antiga para a nova:

* tempo que cai numa borda de segmento (até 20 ms) acompanha a borda — o
  punch-in que entra no corte continua entrando no corte;
* tempo dentro de um segmento acompanha a FALA: vira posição na fonte pela
  versão antiga e volta a tempo de clipe pela nova. Se aquela fala saiu do
  corte, gruda na borda mais próxima.

Cada segmento do plano ganha `synced_source` — a faixa da fonte com que os seus
`clip_start`/`clip_end` foram calculados. É o que permite recalcular quando
alguém edita `source_start`/`source_end` à mão: a versão antiga continua
conhecida.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from scripts.utils import now_iso

TOL_BORDA = 0.02
# O mesmo gap_eps do render: abaixo disso dois segmentos seguidos na fonte são
# decupagem interna, não corte.
GAP_CONTIGUO = 0.05
# Diferença entre duração no clipe e duração na fonte que denuncia borda movida
# sem recalcular. Folga para o arredondamento de 2 casas do Edit Director.
TOL_DURACAO = 0.03


@dataclass
class Faixa:
    fonte_ini: float
    fonte_fim: float
    clipe_ini: float
    clipe_fim: float


def ordenar(segmentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A ordem do render: `order`, estável (mesmo critério de render_clip)."""
    return sorted(segmentos, key=lambda item: item.get("order", 0))


def faixas_cumulativas(segmentos: list[dict[str, Any]]) -> list[Faixa]:
    """Tempos de clipe que o render produz: soma das durações na fonte, em ordem."""
    faixas, t = [], 0.0
    for seg in segmentos:
        a, b = float(seg["source_start"]), float(seg["source_end"])
        dur = max(0.0, b - a)
        faixas.append(Faixa(a, b, t, t + dur))
        t += dur
    return faixas


def _tem_tempo_de_clipe(seg: dict[str, Any]) -> bool:
    return isinstance(seg.get("clip_start"), (int, float)) and isinstance(seg.get("clip_end"), (int, float))


def faixas_registradas(segmentos: list[dict[str, Any]]) -> tuple[list[Faixa], list[str]]:
    """A versão com que os tempos de clipe ATUAIS do plano foram escritos.

    Com `synced_source`, é exata. Sem ele, vale o `clip_start`/`clip_end` gravado
    quando bate com a duração na fonte; sem tempo de clipe gravado, vale a soma
    das durações. Segmento com tempo de clipe que não bate e sem `synced_source`
    não tem referência: assume a borda de início fixa e avisa.
    """
    cumulativas = faixas_cumulativas(segmentos)
    if not segmentos or not all(_tem_tempo_de_clipe(s) for s in segmentos):
        return cumulativas, []
    faixas, avisos = [], []
    for idx, seg in enumerate(segmentos):
        c0, c1 = float(seg["clip_start"]), float(seg["clip_end"])
        a, b = float(seg["source_start"]), float(seg["source_end"])
        sync = seg.get("synced_source")
        if isinstance(sync, list) and len(sync) == 2:
            faixas.append(Faixa(float(sync[0]), float(sync[1]), c0, c1))
        elif abs((c1 - c0) - (b - a)) <= TOL_DURACAO:
            faixas.append(Faixa(a, b, c0, c1))
        else:
            faixas.append(Faixa(a, a + (c1 - c0), c0, c1))
            avisos.append(
                f"tempos_sem_referencia: segmento {idx + 1} tinha clip {c0:.2f}–{c1:.2f} "
                f"para fonte {a:.2f}–{b:.2f}; tempos internos dele recalculados supondo o "
                "início fixo — confira legenda/cards desse trecho"
            )
    return faixas, avisos


def pais_por_sequencia(antigas: list[Faixa], novas: list[Faixa], eps: float = 0.01) -> list[int]:
    """De qual faixa antiga veio cada nova, quando o autoframe divide segmentos.

    O autoframe emite os subsegmentos de cada segmento em sequência, todos
    dentro da faixa de origem. Andar as duas listas juntas resolve até o hook
    repetido no corpo (mesma fonte em dois segmentos): o subsegmento que volta
    na fonte já é do segmento seguinte.
    """
    pais: list[int] = []
    k, fim_anterior = 0, None
    for nova in novas:
        while k < len(antigas) - 1:
            a = antigas[k]
            comeca_dentro = a.fonte_ini - eps <= nova.fonte_ini < a.fonte_fim - eps
            recuou = bool(pais) and pais[-1] == k and fim_anterior is not None and nova.fonte_ini < fim_anterior - eps
            if comeca_dentro and not recuou:
                break
            k += 1
        pais.append(k)
        fim_anterior = nova.fonte_fim
    return pais


class Remapeador:
    """Leva tempos de clipe de uma versão do corte para outra, pela fonte."""

    def __init__(self, antigas: list[Faixa], novas: list[Faixa], pais: list[int] | None = None):
        if pais is None:
            if len(antigas) != len(novas):
                raise ValueError("sem `pais`, as duas versões precisam ter o mesmo número de segmentos")
            pais = list(range(len(novas)))
        self.antigas = antigas
        self.novas = novas
        self.filhas: dict[int, list[int]] = {}
        for j, k in enumerate(pais):
            self.filhas.setdefault(k, []).append(j)
        self.total_antigo = antigas[-1].clipe_fim if antigas else 0.0
        self.total_novo = novas[-1].clipe_fim if novas else 0.0

    def _de(self, k: int) -> list[Faixa]:
        return [self.novas[j] for j in self.filhas.get(k, [])]

    def _borda(self, t: float, lado: str) -> tuple[Faixa, float] | None:
        """Tempo colado numa borda antiga -> a mesma borda na versão nova."""
        def inicio_de(k: int) -> tuple[Faixa, float] | None:
            filhas = self._de(k)
            return (filhas[0], filhas[0].fonte_ini) if filhas else None

        def fim_de(k: int) -> tuple[Faixa, float] | None:
            filhas = self._de(k)
            return (filhas[-1], filhas[-1].fonte_fim) if filhas else None

        inicios = [k for k, f in enumerate(self.antigas) if abs(t - f.clipe_ini) <= TOL_BORDA]
        fins = [k for k, f in enumerate(self.antigas) if abs(t - f.clipe_fim) <= TOL_BORDA]
        # Na emenda entre dois segmentos, o fim de algo fica no segmento da
        # esquerda; início e ponto, no da direita.
        tentativas = [(fins, fim_de), (inicios, inicio_de)] if lado == "fim" else [(inicios, inicio_de), (fins, fim_de)]
        for ks, pega in tentativas:
            for k in ks:
                achado = pega(k)
                if achado:
                    return achado
        return None

    def _localizar(self, t: float, lado: str) -> tuple[Faixa, float] | None:
        if not self.antigas or not self.novas:
            return None
        colado = self._borda(t, lado)
        if colado:
            return colado
        if t <= self.antigas[0].clipe_ini:
            primeira = self._de(0) or self.novas[:1]
            return primeira[0], primeira[0].fonte_ini
        if t >= self.total_antigo:
            ultima = self._de(len(self.antigas) - 1) or self.novas[-1:]
            return ultima[-1], ultima[-1].fonte_fim
        k = next(
            (i for i, f in enumerate(self.antigas) if f.clipe_ini < t < f.clipe_fim),
            min(range(len(self.antigas)), key=lambda i: min(abs(t - self.antigas[i].clipe_ini), abs(t - self.antigas[i].clipe_fim))),
        )
        velha = self.antigas[k]
        fonte = velha.fonte_ini + (t - velha.clipe_ini)
        filhas = self._de(k)
        if not filhas:
            return None
        for faixa in filhas:
            if faixa.fonte_ini <= fonte <= faixa.fonte_fim:
                return faixa, fonte
        if fonte < filhas[0].fonte_ini:
            return filhas[0], filhas[0].fonte_ini
        if fonte > filhas[-1].fonte_fim:
            return filhas[-1], filhas[-1].fonte_fim
        # num buraco entre dois subsegmentos: o fim gruda à esquerda, o resto à direita
        for antes, depois in zip(filhas, filhas[1:]):
            if antes.fonte_fim < fonte < depois.fonte_ini:
                return (antes, antes.fonte_fim) if lado == "fim" else (depois, depois.fonte_ini)
        return filhas[-1], filhas[-1].fonte_fim

    def tempo(self, t: float, lado: str = "ponto") -> float:
        achado = self._localizar(float(t), lado)
        if achado is None:
            return max(0.0, min(float(t), self.total_novo))
        faixa, fonte = achado
        return faixa.clipe_ini + (fonte - faixa.fonte_ini)

    def fonte(self, t: float, lado: str = "ponto") -> float | None:
        achado = self._localizar(float(t), lado)
        return achado[1] if achado else None


def _r(valor: float, casas: int = 3) -> float:
    return round(float(valor) + 0.0, casas)


def _remapear_itens(no: Any, mapa: Remapeador, contagem: list[int]) -> None:
    """Todo `clip_start`/`clip_end`/`clip_t` fora da timeline, em qualquer nível."""
    if isinstance(no, list):
        for item in no:
            _remapear_itens(item, mapa, contagem)
        return
    if not isinstance(no, dict):
        return
    for chave, lado in (("clip_start", "inicio"), ("clip_end", "fim"), ("clip_t", "ponto")):
        valor = no.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            novo = _r(mapa.tempo(valor, lado))
            fonte = mapa.fonte(valor, lado)
            par = {"clip_start": "source_start", "clip_end": "source_end"}.get(chave)
            if par and isinstance(no.get(par), (int, float)) and fonte is not None and _r(fonte) != no[par]:
                no[par] = _r(fonte)  # punch-in: a faixa da fonte acompanha
            if novo != valor:
                contagem[0] += 1
                no[chave] = novo
    for chave, valor in no.items():
        if isinstance(valor, (dict, list)):
            _remapear_itens(valor, mapa, contagem)


def _mapa_de_bordas(antigas: list[Faixa], novas: list[Faixa], pais: list[int]) -> dict[float, float]:
    """Borda antiga na fonte -> borda nova, para listas de bordas documentais."""
    mapa: dict[float, float] = {}
    filhas: dict[int, list[int]] = {}
    for j, k in enumerate(pais):
        filhas.setdefault(k, []).append(j)
    for k, velha in enumerate(antigas):
        js = filhas.get(k)
        if not js:
            continue
        mapa[round(velha.fonte_ini, 3)] = novas[js[0]].fonte_ini
        mapa[round(velha.fonte_fim, 3)] = novas[js[-1]].fonte_fim
    return mapa


def recalcular_plano(
    plan: dict[str, Any],
    timeline_antiga: list[dict[str, Any]] | None = None,
    *,
    dividido: bool = False,
    origem: str = "recalcular",
) -> dict[str, Any]:
    """Reescreve todo tempo de clipe do plano a partir da timeline atual.

    `timeline_antiga`: a timeline antes da mudança (cópia). Sem ela, a versão
    antiga é a registrada no próprio plano (`synced_source`), o que cobre a
    borda editada à mão. `dividido=True` quando a nova timeline tem
    subsegmentos (autoframe).
    """
    timeline = ordenar(plan.get("timeline") or [])
    if not timeline:
        return {"clip_id": plan.get("clip_id"), "mudou": False}
    antiga = ordenar(copy.deepcopy(timeline_antiga)) if timeline_antiga is not None else timeline
    antigas, avisos = faixas_registradas(antiga)
    novas = faixas_cumulativas(timeline)
    if dividido:
        pais = pais_por_sequencia(antigas, novas)
    elif len(antigas) == len(novas):
        pais = list(range(len(novas)))
    else:
        pais = pais_por_sequencia(antigas, novas)
    mapa = Remapeador(antigas, novas, pais)

    antes = copy.deepcopy(plan)
    primeira_da_origem = {pais.index(k) for k in set(pais)}
    ultima_da_origem = {len(pais) - 1 - pais[::-1].index(k) for k in set(pais)}

    contagem = [0]
    resto = {k: v for k, v in plan.items() if k != "timeline"}
    _remapear_itens(resto, mapa, contagem)
    plan.update(resto)

    for j, (seg, faixa) in enumerate(zip(timeline, novas)):
        seg["clip_start"] = _r(faixa.clipe_ini)
        seg["clip_end"] = _r(faixa.clipe_fim)
        seg["synced_source"] = [_r(faixa.fonte_ini), _r(faixa.fonte_fim)]
        if dividido and isinstance(seg.get("edge_audio"), dict):
            registro = dict(seg["edge_audio"])
            if j not in primeira_da_origem:
                registro.pop("start", None)
            if j not in ultima_da_origem:
                registro.pop("end", None)
            if registro:
                seg["edge_audio"] = registro
            else:
                seg.pop("edge_audio", None)
        respiro = seg.get("breath_cut_before")
        if isinstance(respiro, dict):
            if j not in primeira_da_origem:
                seg.pop("breath_cut_before", None)
            elif j > 0:
                fim_anterior = float(timeline[j - 1]["source_end"])
                inicio = float(seg["source_start"])
                respiro["removed_source"] = [_r(fim_anterior), _r(inicio)]
                respiro["removed_s"] = _r(max(0.0, inicio - fim_anterior))

    total = mapa.total_novo
    decupagem = plan.get("breath_decupage")
    if isinstance(decupagem, dict):
        decupagem["final_duration_s"] = _r(total, 2)
        candidato = decupagem.get("candidate_duration_s")
        if isinstance(candidato, (int, float)) and candidato > 0:
            removido = max(0.0, float(candidato) - total)
            decupagem["removed_s"] = _r(removido, 2)
            decupagem["removed_pct"] = _r(100.0 * removido / float(candidato), 1)
        bordas = decupagem.get("untouched_edges")
        if isinstance(bordas, list):
            troca = _mapa_de_bordas(antigas, novas, pais)
            decupagem["untouched_edges"] = [
                _r(troca.get(round(float(v), 3), v)) if isinstance(v, (int, float)) else v for v in bordas
            ]

    if avisos:
        existentes = [w for w in plan.get("warnings", []) if not str(w).startswith("tempos_sem_referencia")]
        plan["warnings"] = existentes + avisos

    mudou = plan != antes
    if mudou:
        plan["timing_sync"] = {
            "updated_at": now_iso(),
            "by": origem,
            "note": "tempos de clipe recalculados pela posição na fonte (scripts/tempos.py); "
                    "números citados em texto livre podem ser da versão anterior",
        }
    return {
        "clip_id": plan.get("clip_id"),
        "mudou": mudou,
        "duracao_antiga": _r(mapa.total_antigo, 2),
        "duracao_nova": _r(total, 2),
        "itens_remapeados": contagem[0],
        "avisos": avisos,
    }


def remapear_candidato(clip: dict[str, Any], segmentos_antigos: list[dict[str, Any]]) -> dict[str, Any]:
    """O mesmo recálculo no candidato (06): eventos, beats e duração estimada."""
    antigos = ordenar(copy.deepcopy(segmentos_antigos))
    novos = ordenar(clip.get("segments") or [])
    if not novos or len(antigos) != len(novos):
        return {"clip_id": clip.get("id"), "mudou": False}
    mapa = Remapeador(faixas_cumulativas(antigos), faixas_cumulativas(novos))
    antes = copy.deepcopy(clip)
    contagem = [0]

    def ponto(valor: Any) -> Any:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            novo = _r(mapa.tempo(valor, "ponto"))
            if novo != valor:
                contagem[0] += 1
                return novo
        return valor

    eventos = clip.get("events")
    if isinstance(eventos, dict) and str(eventos.get("timebase", "final")) != "source":
        for chave in list(eventos):
            if chave.endswith("_at"):
                eventos[chave] = ponto(eventos[chave])
    for beat in clip.get("semantic_beats") or []:
        if isinstance(beat, dict) and "at" in beat:
            beat["at"] = ponto(beat["at"])
    resto = {k: v for k, v in clip.items() if k not in {"segments", "events", "semantic_beats"}}
    _remapear_itens(resto, mapa, contagem)
    clip.update(resto)
    if isinstance(clip.get("estimated_final_duration_seconds"), (int, float)):
        clip["estimated_final_duration_seconds"] = _r(mapa.total_novo, 2)
    return {
        "clip_id": clip.get("id"),
        "mudou": clip != antes,
        "duracao_antiga": _r(mapa.total_antigo, 2),
        "duracao_nova": _r(mapa.total_novo, 2),
        "itens_remapeados": contagem[0],
    }


def verificar_plano(plan: dict[str, Any]) -> list[str]:
    """Tempo de clipe que não bate com a fonte = borda mudou sem recalcular."""
    problemas = []
    timeline = ordenar(plan.get("timeline") or [])
    esperado = faixas_cumulativas(timeline)
    for idx, (seg, faixa) in enumerate(zip(timeline, esperado), start=1):
        if not _tem_tempo_de_clipe(seg):
            continue
        c0, c1 = float(seg["clip_start"]), float(seg["clip_end"])
        dur_clipe, dur_fonte = c1 - c0, faixa.fonte_fim - faixa.fonte_ini
        sync = seg.get("synced_source")
        fonte_mudou = isinstance(sync, list) and len(sync) == 2 and (
            abs(float(sync[0]) - faixa.fonte_ini) > 0.0005 or abs(float(sync[1]) - faixa.fonte_fim) > 0.0005
        )
        if abs(dur_clipe - dur_fonte) > TOL_DURACAO or fonte_mudou:
            problemas.append(
                f"{plan.get('clip_id')}: timeline[{idx}] clip {c0:.2f}–{c1:.2f} não corresponde à fonte "
                f"{faixa.fonte_ini:.2f}–{faixa.fonte_fim:.2f} (pela fonte: {faixa.clipe_ini:.2f}–{faixa.clipe_fim:.2f})"
            )
    return problemas

