# -*- coding: utf-8 -*-
"""Passo 0 — registra a fonte antes de extrair qualquer número.

Salva em metadata/ o schema do modelo semântico e a identificação do pacote
publicado (nome do .pbix, versão, data do último refresh). Esses arquivos são
a prova de qual era o estado do painel no momento da coleta: se o órgão
republicar o painel com números revisados, a diferença fica documentada.
"""
import json
import os

import _caminho
from dadoscaged import client, config, extract

os.makedirs(_caminho.DIR_META, exist_ok=True)


def salvar(nome, obj):
    caminho = os.path.join(_caminho.DIR_META, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("  gravado: metadata/%s (%d bytes)" % (nome, os.path.getsize(caminho)))


print("Consultando o painel...")
modelo = client.obter_modelo()
schema = client.obter_schema()

# O documento de exploração (layout das páginas) é grande e não é usado pela
# extração; guardamos só o que identifica a fonte.
resumo_modelo = {
    "package": modelo.get("package"),
    "models": [{"id": m.get("id"), "dbName": m.get("dbName")} for m in modelo.get("models", [])],
    "paginas": [s.get("displayName") for s in modelo.get("exploration", {}).get("sections", [])],
}
salvar("modelo.json", resumo_modelo)
salvar("schema_modelo.json", schema)
salvar("proveniencia.json", extract.carimbo_execucao())

# Inventário legível do modelo, para conferência humana.
linhas = ["# Inventário do modelo semântico", "",
          "Gerado por `scripts/00_inventario_fonte.py`. Não editar à mão.", ""]
for s in schema["schemas"]:
    for e in s["schema"]["Entities"]:
        props = e.get("Properties", [])
        linhas.append("## `%s`" % e["Name"])
        linhas.append("")
        for p in props:
            tipo = "medida" if "Measure" in p else "coluna"
            linhas.append("- `%s` — %s" % (p["Name"], tipo))
        linhas.append("")
caminho = os.path.join(_caminho.RAIZ, "docs", "MODELO.md")
with open(caminho, "w", encoding="utf-8") as f:
    f.write("\n".join(linhas))
print("  gravado: docs/MODELO.md")

pac = modelo.get("package", {})
print("\nFonte identificada:")
print("  pacote        : %s" % pac.get("name"))
print("  versao        : %s" % pac.get("version"))
print("  ultimo refresh: %s" % pac.get("LastRefreshTime"))
print("  competencias  : %d meses" % len(extract.listar_competencias()))
