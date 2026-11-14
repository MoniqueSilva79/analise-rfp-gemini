"""Análise de RFP com Gemini (Vertex AI) para times de pré-vendas.

Lê o edital/RFP (PDF, TXT ou MD), extrai requisitos, prazos, critérios de
avaliação e riscos, calcula uma nota de Go/No-Go e gera:
  - matriz_conformidade.csv  (para o time preencher "atende / não atende")
  - resumo_rfp.md            (resumo executivo para a reunião de qualificação)

Uso:
    python analisar_rfp.py exemplo/rfp_exemplo.md
    python analisar_rfp.py edital.pdf --saida resultado/
"""
import argparse
import csv
import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Tipo(str, Enum):
    OBRIGATORIO = "obrigatório"
    DESEJAVEL = "desejável"


class Area(str, Enum):
    TECNICA = "técnica"
    COMERCIAL = "comercial"
    JURIDICA = "jurídica"
    SLA = "SLA e suporte"


class Requisito(BaseModel):
    codigo: str = Field(description="Item do edital, ex.: 4.2.1. Se não houver, use R01, R02...")
    descricao: str
    tipo: Tipo
    area: Area


class Prazo(BaseModel):
    data: str = Field(description="Data no formato DD/MM/AAAA, ou 'não informada'")
    evento: str


class Risco(BaseModel):
    descricao: str
    gravidade: int = Field(description="1 baixa, 2 média, 3 alta")


class AnaliseRFP(BaseModel):
    cliente: str
    objeto: str = Field(description="O que está sendo contratado, em uma frase")
    vigencia_meses: int | None
    prazos: list[Prazo]
    requisitos: list[Requisito]
    criterios_avaliacao: list[str] = Field(description="Como as propostas serão julgadas (ex.: menor preço, técnica e preço 60/40)")
    riscos: list[Risco] = Field(description="Multas altas, SLAs agressivos, exigências fora do padrão, prazos curtos")
    perguntas_esclarecimento: list[str] = Field(description="Dúvidas a enviar ao cliente no prazo de esclarecimentos")


PROMPT = """Você é especialista em pré-vendas de telecom e cloud no Brasil.
Analise a RFP abaixo e extraia as informações pedidas, sem inventar nada que não esteja no texto.
Liste TODOS os requisitos, um por item. Seja literal nas datas e valores."""


def analisar(arquivo: Path) -> AnaliseRFP:
    from google import genai
    from google.genai import types

    cliente = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    if arquivo.suffix.lower() == ".pdf":
        documento = types.Part.from_bytes(data=arquivo.read_bytes(), mime_type="application/pdf")
    else:
        documento = arquivo.read_text(encoding="utf-8")

    resposta = cliente.models.generate_content(
        model=os.environ.get("MODELO", "gemini-2.5-flash"),
        contents=[PROMPT, documento],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=AnaliseRFP,
        ),
    )
    return AnaliseRFP.model_validate_json(resposta.text)


def nota_go_no_go(a: AnaliseRFP) -> tuple[int, str]:
    """Nota de 0 a 100. Começa em 100 e desconta por risco e complexidade.

    Os pesos são um ponto de partida: ajuste para a realidade da sua empresa.
    """
    nota = 100
    nota -= sum({1: 3, 2: 8, 3: 15}[min(3, max(1, r.gravidade))] for r in a.riscos)
    obrigatorios = sum(r.tipo == Tipo.OBRIGATORIO for r in a.requisitos)
    nota -= max(0, obrigatorios - 15)              # muitos obrigatórios = mais chance de não conformidade
    if any("menor preço" in c.lower() for c in a.criterios_avaliacao):
        nota -= 10                                 # disputa só por preço reduz margem
    nota = max(0, min(100, nota))
    decisao = "GO" if nota >= 70 else "AVALIAR COM A DIRETORIA" if nota >= 50 else "NO-GO"
    return nota, decisao


def salvar(a: AnaliseRFP, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)

    with open(pasta / "matriz_conformidade.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item", "requisito", "tipo", "área", "atende (S/N/Parcial)", "observação / evidência"])
        for r in a.requisitos:
            w.writerow([r.codigo, r.descricao, r.tipo.value, r.area.value, "", ""])

    nota, decisao = nota_go_no_go(a)
    md = [f"# Análise da RFP – {a.cliente}", "",
          f"**Objeto:** {a.objeto}  ",
          f"**Vigência:** {a.vigencia_meses or 'não informada'} meses  ",
          f"**Nota Go/No-Go:** {nota}/100 → **{decisao}**", "",
          "## 📅 Prazos"] + [f"- {p.data} – {p.evento}" for p in a.prazos] + [
          "", "## ✅ Requisitos",
          f"{len(a.requisitos)} no total, "
          f"{sum(r.tipo == Tipo.OBRIGATORIO for r in a.requisitos)} obrigatórios. "
          "Detalhes em `matriz_conformidade.csv`.", "",
          "## ⚖️ Critérios de avaliação"] + [f"- {c}" for c in a.criterios_avaliacao] + [
          "", "## ⚠️ Riscos"] + [f"- {'🔴' if r.gravidade == 3 else '🟠' if r.gravidade == 2 else '🟡'} {r.descricao}"
                                  for r in sorted(a.riscos, key=lambda r: -r.gravidade)] + [
          "", "## ❓ Perguntas de esclarecimento"] + [f"{i}. {q}" for i, q in enumerate(a.perguntas_esclarecimento, 1)]
    (pasta / "resumo_rfp.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Nota Go/No-Go: {nota}/100 → {decisao}")
    print(f"{len(a.requisitos)} requisitos · {len(a.riscos)} riscos · {len(a.prazos)} prazos")
    print(f"Arquivos gerados em {pasta.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Análise de RFP com Gemini")
    parser.add_argument("arquivo", type=Path, help="RFP em PDF, TXT ou MD")
    parser.add_argument("--saida", type=Path, default=Path("resultado"))
    args = parser.parse_args()
    salvar(analisar(args.arquivo), args.saida)


if __name__ == "__main__":
    main()
