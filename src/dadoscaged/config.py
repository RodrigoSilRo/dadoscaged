# -*- coding: utf-8 -*-
"""Identificação da fonte de dados.

Todos os identificadores abaixo são públicos: constam do link de divulgação do
painel e das respostas não autenticadas da API. Nenhuma credencial é usada ou
necessária — o relatório foi publicado pelo órgão com a opção "Publicar na web"
do Power BI, que expõe o modelo semântico para consulta anônima.
"""

# --- Link público divulgado pelo Ministério do Trabalho e Emprego -------------
PAINEL_URL = (
    "https://app.powerbi.com/view?r=eyJrIjoiNWI5NWI0ODEtYmZiYy00Mjg3LTkzNWUt"
    "Y2UyYjIwMDE1YWI2IiwidCI6IjNlYzkyOTY5LTVhNTEtNGYxOC04YWM5LWVmOThmYmFmYTk3OCJ9"
)

# O parâmetro "r" do link é um JSON em base64: {"k": <resource key>, "t": <tenant>}
RESOURCE_KEY = "5b95b481-bfbc-4287-935e-ce2b20015ab6"
TENANT_ID = "3ec92969-5a51-4f18-8ac9-ef98fbafa978"

# --- Backend do Power BI -----------------------------------------------------
# O cluster é declarado no HTML da página do relatório. O host "-redirect"
# encerra a conexão para clientes não-navegador; o host "-api" responde.
CLUSTER_HOST = "https://wabi-brazil-south-d-primary-api.analysis.windows.net"

# Identificadores do modelo semântico, obtidos de /modelsAndExploration.
MODEL_ID = 528307
DATASET_ID = "4859b5fd-e3ad-4a7c-95fe-aa62fc046d96"
REPORT_ID = "534733"
PACKAGE_NAME = "Painel Novo CAGED.pbix"

# --- Endpoints ---------------------------------------------------------------
EP_MODELO = "/public/reports/{key}/modelsAndExploration?preferReadOnlySession=true"
EP_SCHEMA = "/public/reports/conceptualschema"
EP_QUERY = "/public/reports/querydata?synchronous=true"

# --- Estrutura do modelo (ver docs/DICIONARIO.md) ----------------------------
TAB_ECONOMICO = "Econômico"
TAB_TEMPO = "TabelaDeDatas"
TAB_MEDIDAS = "Medidas"
TAB_GEOGRAFICO = "Geográfico"

# Coluna usada para recorte por unidade da federação (sigla: "SC", "SP", ...).
COL_UF = "UF Sigla"

# Hierarquia setorial, do nível mais agregado ao mais desagregado.
HIERARQUIA_SETORIAL = [
    "Grande Grupamento",
    "Grupamento",
    "CNAE 2.0 Seção",
    "CNAE 2.0 Divisão",
    "CNAE 2.0 Grupo",
    "CNAE 2.0 Classe",
    "CNAE 2.0 Subclasse",
]

# Níveis que possuem coluna de código no modelo.
CODIGO_DE = {
    "Grande Grupamento": "Código Grande Grupamento",
    "CNAE 2.0 Seção": "Código CNAE 2.0 Seção",
    "CNAE 2.0 Divisão": "Código CNAE 2.0 Divisão",
    "CNAE 2.0 Grupo": "Código CNAE 2.0 Grupo",
    "CNAE 2.0 Classe": "Código CNAE 2.0 Classe",
    "CNAE 2.0 Subclasse": "Código CNAE 2.0 Subclasse",
}

MEDIDAS_PADRAO = ["Admitidos", "Desligados", "Saldo",
                  "Tempo de Emprego (Desligados)", "Estoque Mensal", "Vr. Relativa"]

# Classificação das medidas quanto ao comportamento sob agregação. Ela determina
# COMO cada medida pode ser validada e como o usuário pode reagregar a saída.
#
#   aditiva  — contagem; a soma entre categorias reproduz o agregado. Conferida
#              por igualdade exata contra o total do painel.
#   composta — média ou razão calculada em DAX. NÃO é somável: reagregar exige
#              recalcular a partir das medidas aditivas. Conferida célula a
#              célula contra uma consulta independente, no mesmo nível.
#
# Verificado empiricamente (ver docs/METODOLOGIA.md, seção 6).
MEDIDAS_ADITIVAS = ["Admitidos", "Desligados", "Saldo", "Estoque Mensal"]
MEDIDAS_COMPOSTAS = ["Tempo de Emprego (Desligados)", "Vr. Relativa",
                     "Taxa de Rotatividade", "Saldo Acumulado"]

# `Estoque Mensal` é aditiva com igualdade EXATA até o nível de Classe, nos 78
# meses. Só no nível de Subclasse a soma excede o agregado, e apenas nos anos
# iniciais da série (máx. 0,162% em 2020-06; exatamente zero de 2023 em diante).
# É um desvio da própria fonte, no período de transição do Novo CAGED, e não da
# extração — ver docs/LIMITACOES.md, seção 12.
#
# Ele não é "tolerado" no escuro: para essas medidas a conferência exige
# igualdade exata no NÍVEL PAI do extraído, e mede o resíduo do nível extraído
# em vez de ignorá-lo. Se o desvio aparecesse também no nível pai, seria falha.
MEDIDAS_COM_DESVIO_NO_NIVEL_MAIS_FINO = ["Estoque Mensal"]

# Limite de linhas por consulta. O backend aplica seu próprio teto; consultas
# são particionadas por ano em extract.py para ficar bem abaixo dele.
JANELA_PADRAO = 60000
