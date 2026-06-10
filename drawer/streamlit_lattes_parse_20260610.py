# -*- coding: utf-8 -*-
"""
Streamlit app para ler Currículo Lattes em XML ou ZIP, extrair produções/orientações/bancas/eventos
mais frequentes e apresentar tabelas de contagem e uma planilha detalhada.

Execução:
    streamlit run streamlit_lattes_parse_corrigido.py
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import BinaryIO, Iterable

import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom


# -----------------------------------------------------------------------------
# Funções de busca de dados
# -----------------------------------------------------------------------------

def carregar_e_agrupar_planilha(url_ou_caminho):
    """
    Carrega a planilha (via link de exportação do Google Sheets ou arquivo local)
    """
    try:
        df = pd.read_csv(url_ou_caminho)
    except Exception:
        df = pd.read_excel(url_ou_caminho)
    
    # Colunas de referência geral que sempre acompanham o grupo
    colunas_base = ['TAG', 'PESO', 'SAT']
    
    # Mapeamento dos grupos/subcomitês da PROPP identificados na planilha
    grupos_areas = {
        'BIO': 'Ciências Biológicas e Ciências Agrárias',
        'SAU': 'Ciências da Saúde',
        'EXA': 'Ciências Exatas e da Terra',
        'HUM': 'Ciências Humanas',
        'CSA': 'Ciências Sociais Aplicadas',
        'ENG': 'Engenharias e Ciência da Computação',
        'LLA': 'Linguística, Letras e Artes'
    }
    
    return df, colunas_base, grupos_areas

def buscar_grupo_especifico(df, colunas_base, sigla_grupo):
    """
    Busca e filtra apenas um grupo de cada vez, trazendo os dados gerais + os pesos do grupo
    """
    col_peso = f'PESO-{sigla_grupo}'
    col_sat = f'SAT-{sigla_grupo}'
    
    # Monta a lista de colunas que queremos extrair para este grupo
    colunas_filtradas = []
    for col in colunas_base:
        if col in df.columns:
            colunas_filtradas.append(col)
            
    if col_peso in df.columns:
        colunas_filtradas.append(col_peso)
    if col_sat in df.columns:
        colunas_filtradas.append(col_sat)
        
    return df[colunas_filtradas]

# -----------------------------------------------------------------------------
# Gera um xml sintético
# -----------------------------------------------------------------------------

def gerar_xml_teste(item_specs, output="lattes_teste_completo.xml", n_por_tag=5): 

    root = ET.Element(
        "CURRICULO-VITAE",
        {
            "NUMERO-IDENTIFICADOR": "9999999999999999",
            "DATA-ATUALIZACAO": "01012025",
        },
    )

    ET.SubElement(
        root,
        "DADOS-GERAIS",
        {
            "NOME-COMPLETO": "CURRICULO TESTE",
            "ORCID-ID": "0000-0000-0000-0000",
        },
    )

    for tag, spec in item_specs.items():

        grupo = ET.SubElement(
            root,
            "GRUPO-SINTETICO",
            {
                "NOME": str(spec.get("grupo", "OUTROS")),
                "ITEM": str(tag),
            },
        )

        for i in range(1, n_por_tag + 1):

            item = ET.SubElement(
                grupo,
                tag,
                {
                    "ID-SINTETICO": str(i),
                },
            )

            attrs = {}

            for campo in spec.get("ano", []):
                attrs[campo] = "2025"

            for campo in spec.get("natureza", []):
                attrs[campo] = "TESTE"

            for campo in spec.get("titulo", []):
                attrs[campo] = f"{tag} TESTE {i}"

            for campo in spec.get("extras", []):
                attrs[campo] = "5"

            ET.SubElement(
                item,
                "DADOS-BASICOS-SINTETICOS",
                attrs,
            )

    ET.indent(root, space="    ")

    tree = ET.ElementTree(root)

    tree.write(
        output,
        encoding="utf-8",
        xml_declaration=True,
    )

    print(f"Arquivo salvo: {output}")


# -----------------------------------------------------------------------------
# Configuração dos itens contabilizáveis do Lattes
# -----------------------------------------------------------------------------
# Cada item aponta para a tag-pai do registro e para os campos onde, no XML,
# normalmente ficam ano, natureza, título e dados complementares.
ITEM_SPECS: dict[str, dict] = {
    # Produção bibliográfica
    "ARTIGO-PUBLICADO": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO-DO-ARTIGO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-ARTIGO"],
        "extras": ["ISSN", "TITULO-DO-PERIODICO-OU-REVISTA", "DOI"],
    },
    "ARTIGO-ACEITO-PARA-PUBLICACAO": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO-DO-ARTIGO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-ARTIGO"],
        "extras": ["ISSN", "TITULO-DO-PERIODICO-OU-REVISTA", "DOI"],
    },
    "TRABALHO-EM-EVENTOS": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO-DO-TRABALHO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["CLASSIFICACAO-DO-EVENTO", "NOME-DO-EVENTO", "DOI"],
    },
    "LIVRO-PUBLICADO-OU-ORGANIZADO": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO"],
        "natureza": ["TIPO", "NATUREZA"],
        "titulo": ["TITULO-DO-LIVRO"],
        "extras": ["ISBN", "NOME-DA-EDITORA"],
    },
    "CAPITULO-DE-LIVRO-PUBLICADO": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO"],
        "natureza": ["TIPO", "NATUREZA"],
        "titulo": ["TITULO-DO-CAPITULO-DO-LIVRO"],
        "extras": ["TITULO-DO-LIVRO", "ISBN", "NOME-DA-EDITORA", "DOI"],
    },
    "TEXTO-EM-JORNAL-OU-REVISTA": {
        "grupo": "Produção bibliográfica",
        "ano": ["ANO-DO-TEXTO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TEXTO"],
        "extras": ["TITULO-DO-JORNAL-OU-REVISTA"],
    },

    # Produção técnica / tecnológica
    "SOFTWARE": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-SOFTWARE", "TITULO"],
        "extras": ["FINALIDADE", "PLATAFORMA", "AMBIENTE"],
    },
    "PATENTE": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO-DESENVOLVIMENTO", "ANO"],
        "natureza": ["CATEGORIA", "NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["CODIGO-DO-REGISTRO-OU-PATENTE", "INSTITUICAO-DEPOSITO-REGISTRO"],
    },
    "PRODUTO-TECNOLOGICO": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["TIPO-PRODUTO", "NATUREZA"],
        "titulo": ["TITULO-DO-PRODUTO", "TITULO"],
        "extras": ["FINALIDADE"],
    },
    "PROCESSOS-OU-TECNICAS": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-PROCESSO", "TITULO"],
        "extras": ["FINALIDADE"],
    },
    "TRABALHO-TECNICO": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO-TECNICO", "TITULO"],
        "extras": ["FINALIDADE", "DURACAO-EM-MESES"],
    },
    "CURSO-DE-CURTA-DURACAO-MINISTRADO": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO", "TITULO-DO-CURSO"],
        "extras": ["DURACAO", "INSTITUICAO-PROMOTORA-DO-CURSO"],
    },
    "DESENVOLVIMENTO-DE-MATERIAL-DIDATICO-OU-INSTRUCIONAL": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["FINALIDADE"],
    },
    "ORGANIZACAO-DE-EVENTO": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["INSTITUICAO-PROMOTORA", "LOCAL"],
    },
    "APRESENTACAO-DE-TRABALHO": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-EVENTO"],
    },
    "RELATORIO-DE-PESQUISA": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-PROJETO"],
    },
    "OUTRA-PRODUCAO-TECNICA": {
        "grupo": "Produção técnica/tecnológica",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["FINALIDADE"],
    },

    # Orientações concluídas
    "ORIENTACOES-CONCLUIDAS-PARA-MESTRADO": {
        "grupo": "Orientações concluídas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-ORIENTADO", "NOME-DA-INSTITUICAO"],
    },
    "ORIENTACOES-CONCLUIDAS-PARA-DOUTORADO": {
        "grupo": "Orientações concluídas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-ORIENTADO", "NOME-DA-INSTITUICAO"],
    },
    "ORIENTACOES-CONCLUIDAS-PARA-POS-DOUTORADO": {
        "grupo": "Orientações concluídas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-ORIENTADO", "NOME-DA-INSTITUICAO"],
    },
    "OUTRAS-ORIENTACOES-CONCLUIDAS": {
        "grupo": "Orientações concluídas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-ORIENTADO", "NOME-DA-INSTITUICAO"],
    },

    # Orientações em andamento
    "ORIENTACAO-EM-ANDAMENTO-DE-MESTRADO": {
        "grupo": "Orientações em andamento",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["NOME-DO-ORIENTANDO", "NOME-DA-INSTITUICAO"],
    },
    "ORIENTACAO-EM-ANDAMENTO-DE-DOUTORADO": {
        "grupo": "Orientações em andamento",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["NOME-DO-ORIENTANDO", "NOME-DA-INSTITUICAO"],
    },
    "ORIENTACAO-EM-ANDAMENTO-DE-INICIACAO-CIENTIFICA": {
        "grupo": "Orientações em andamento",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["NOME-DO-ORIENTANDO", "NOME-DA-INSTITUICAO"],
    },
    "ORIENTACAO-EM-ANDAMENTO-DE-GRADUACAO": {
        "grupo": "Orientações em andamento",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["NOME-DO-ORIENTANDO", "NOME-DA-INSTITUICAO"],
    },
    "OUTRAS-ORIENTACOES-EM-ANDAMENTO": {
        "grupo": "Orientações em andamento",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO-DO-TRABALHO"],
        "extras": ["NOME-DO-ORIENTANDO", "NOME-DA-INSTITUICAO"],
    },

    # Bancas e eventos
    "PARTICIPACAO-EM-BANCA-DE-MESTRADO": {
        "grupo": "Bancas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-CANDIDATO", "NOME-INSTITUICAO"],
    },
    "PARTICIPACAO-EM-BANCA-DE-DOUTORADO": {
        "grupo": "Bancas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-CANDIDATO", "NOME-INSTITUICAO"],
    },
    "PARTICIPACAO-EM-BANCA-DE-EXAME-QUALIFICACAO": {
        "grupo": "Bancas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-CANDIDATO", "NOME-INSTITUICAO"],
    },
    "PARTICIPACAO-EM-BANCA-DE-GRADUACAO": {
        "grupo": "Bancas",
        "ano": ["ANO"],
        "natureza": ["NATUREZA"],
        "titulo": ["TITULO"],
        "extras": ["NOME-DO-CANDIDATO", "NOME-INSTITUICAO"],
    },
    "PARTICIPACAO-EM-CONGRESSO": {
        "grupo": "Participação em eventos",
        "ano": ["ANO"],
        "natureza": ["FORMA-PARTICIPACAO", "NATUREZA"],
        "titulo": ["NOME-DO-EVENTO", "TITULO"],
        "extras": ["LOCAL-DO-EVENTO", "CIDADE-DO-EVENTO"],
    },
    "OUTRAS-PARTICIPACOES-EM-EVENTOS-CONGRESSOS": {
        "grupo": "Participação em eventos",
        "ano": ["ANO"],
        "natureza": ["FORMA-PARTICIPACAO", "NATUREZA"],
        "titulo": ["NOME-DO-EVENTO", "TITULO"],
        "extras": ["LOCAL-DO-EVENTO", "CIDADE-DO-EVENTO"],
    },
}

GENERIC_SPEC = {
    "grupo": "Outros / agregado",
    "ano": ["ANO", "ANO-DO-ARTIGO", "ANO-DO-TRABALHO", "ANO-DESENVOLVIMENTO"],
    "natureza": ["NATUREZA", "TIPO", "CATEGORIA", "FORMA-PARTICIPACAO"],
    "titulo": [
        "TITULO",
        "TITULO-DO-ARTIGO",
        "TITULO-DO-TRABALHO",
        "TITULO-DO-LIVRO",
        "TITULO-DO-CAPITULO-DO-LIVRO",
        "TITULO-DO-TEXTO",
        "TITULO-DO-SOFTWARE",
        "TITULO-DO-TRABALHO",
        "NOME-DO-EVENTO",
    ],
    "extras": [],
}

# depois de definir seu ITEM_SPECS original:
TAGS_TXT = [
    "CULTIVAR-REGISTRADA",
    "CULTIVAR-PROTEGIDA",
    "DESENHO-INDUSTRIAL",
    "MARCA",
    "TOPOGRAFIA-DE-CIRCUITO-INTEGRADO",
    "ORIENTACAO-EM-ANDAMENTO-DE-POS-DOUTORADO",
    "ORIENTACAO-EM-ANDAMENTO-DE-APERFEICOAMENTO-ESPECIALIZACAO",
    "APRESENTACAO-DE-OBRA-ARTISTICA",
    "APRESENTACAO-EM-RADIO-OU-TV",
    "ARRANJO-MUSICAL",
    "COMPOSICAO-MUSICAL",
    "CURSO-DE-CURTA-DURACAO",
    "CURSO-DE-CURTA-DURACAO-MINISTRADO",
    "OBRA-DE-ARTES-VISUAIS",
    "OUTRA-PRODUCAO-ARTISTICA-CULTURAL",
    "SONOPLASTIA",
    "ARTES-CENICAS",
    "ARTES-VISUAIS",
    "MUSICA",
    "CARTA-MAPA-OU-SIMILAR",
    "EDITORACAO",
    "MANUTENCAO-DE-OBRA-ARTISTICA",
    "MAQUETE",
    "PROGRAMA-DE-RADIO-OU-TV",
    "MIDIA-SOCIAL-WEBSITE-BLOG",
    "DEMAIS-TIPOS-DE-PRODUCAO-TECNICA",
    "TRABALHOS-EM-EVENTOS",
    "ARTIGOS-PUBLICADOS",
    "LIVROS-E-CAPITULOS",
    "TEXTOS-EM-JORNAIS-OU-REVISTAS",
    "DEMAIS-TIPOS-DE-PRODUCAO-BIBLIOGRAFICA",
    "ARTIGOS-ACEITOS-PARA-PUBLICACAO",
    "LIVROS-PUBLICADOS-OU-ORGANIZADOS",
    "CAPITULOS-DE-LIVROS-PUBLICADOS",
    "PRODUCAO-ARTISTICA-CULTURAL",
    "ORIENTACOES-CONCLUIDAS",
    "FORMACAO-COMPLEMENTAR",
    "PARTICIPACAO-EM-BANCA-TRABALHOS-CONCLUSAO",
    "PARTICIPACAO-EM-BANCA-JULGADORA",
    "PARTICIPACAO-EM-EVENTOS-CONGRESSOS",
    "ORIENTACOES-EM-ANDAMENTO",
]

for tag in TAGS_TXT:
    ITEM_SPECS.setdefault(tag, GENERIC_SPEC.copy())  



def normalize_space(value: object) -> str:
    """Converte None/NaN em string vazia e normaliza espaços."""
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def first_non_empty(attributes: dict[str, str], keys: Iterable[str]) -> str:
    """Retorna o primeiro atributo não vazio em uma lista de possíveis chaves."""
    for key in keys:
        value = normalize_space(attributes.get(key, ""))
        if value:
            return value
    return ""


def safe_int_year(value: object) -> int | None:
    """Extrai um ano de 4 dígitos, quando possível."""
    text = normalize_space(value)
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None
    return int(match.group(0))


def flatten_attributes(element: ET.Element) -> dict[str, str]:
    """Une atributos da tag-pai e dos filhos em um único dicionário.

    Em caso de repetição de chave, preserva o primeiro valor não vazio. Isso evita
    que atributos vazios de tags secundárias sobrescrevam os dados principais.
    """
    merged: dict[str, str] = {}
    for node in [element, *list(element.iter())]:
        for key, value in node.attrib.items():
            value = normalize_space(value)
            if value and not merged.get(key):
                merged[key] = value
    return merged


def read_uploaded_lattes(uploaded_file: BinaryIO) -> tuple[ET.ElementTree, str]:
    """Lê XML Lattes enviado diretamente ou compactado em ZIP."""
    raw = uploaded_file.read()
    name = getattr(uploaded_file, "name", "arquivo")

    if zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                raise ValueError("O ZIP não contém arquivo .xml.")
            xml_name = xml_names[0]
            with zf.open(xml_name) as f:
                return ET.parse(f), xml_name

    return ET.parse(io.BytesIO(raw)), name


def extract_identification(root: ET.Element) -> dict[str, str]:
    dados = root.find("DADOS-GERAIS")
    if dados is None:
        return {
            "nome": "Não identificado",
            "orcid": "",
            "id_lattes": root.attrib.get("NUMERO-IDENTIFICADOR", ""),
            "atualizacao": root.attrib.get("DATA-ATUALIZACAO", ""),
        }
    return {
        "nome": dados.attrib.get("NOME-COMPLETO", "Não identificado"),
        "orcid": dados.attrib.get("ORCID-ID", ""),
        "id_lattes": root.attrib.get("NUMERO-IDENTIFICADOR", ""),
        "atualizacao": root.attrib.get("DATA-ATUALIZACAO", ""),
    }


def extract_records(root: ET.Element, ano_ref: int, selected_tags: set[str] | None = None) -> pd.DataFrame:
    """Extrai registros detalhados a partir das tags configuradas em ITEM_SPECS."""
    rows: list[dict[str, object]] = []
    selected_tags = selected_tags or set(ITEM_SPECS)

    for elem in root.iter():
        tag = elem.tag
        if tag not in selected_tags or tag not in ITEM_SPECS:
            continue

        spec = ITEM_SPECS[tag]
        attrs = flatten_attributes(elem)
        ano = safe_int_year(first_non_empty(attrs, spec["ano"]))

        if ano is not None and ano < int(ano_ref):
            continue

        extras = {k: attrs.get(k, "") for k in spec.get("extras", [])}
        rows.append(
            {
                "GRUPO": spec["grupo"],
                "ITEM": tag,
                "NATUREZA": first_non_empty(attrs, spec["natureza"]) or "Não informado",
                "ANO": ano,
                "TITULO": first_non_empty(attrs, spec["titulo"]),
                **extras,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["GRUPO", "ITEM", "NATUREZA", "ANO", "TITULO"])

    df = pd.DataFrame(rows)
    # Remove duplicações reais causadas por eventuais tags repetidas no XML.
    dedup_cols = [c for c in ["GRUPO", "ITEM", "NATUREZA", "ANO", "TITULO"] if c in df.columns]
    df = df.drop_duplicates(subset=dedup_cols).sort_values(["GRUPO", "ITEM", "ANO", "TITULO"], na_position="last")
    return df.reset_index(drop=True)


def summarize_counts(
            df: pd.DataFrame,
            pesos_tags: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        
    if df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    #por_item = (
    #    df.groupby(["GRUPO", "ITEM"], dropna=False)
    #    .size()
    #    .reset_index(name="CONTAGEM")
    #    .sort_values(["GRUPO", "CONTAGEM", "ITEM"], ascending=[True, False, True])
    #)

    por_item = (
        df.groupby(["GRUPO", "ITEM"], dropna=False)
        .size()
        .reset_index(name="CONTAGEM")
    )

    # junta pesos
    por_item = por_item.merge(
        pesos_tags[["TAG", "PESO", "SAT"]],
        left_on="ITEM",
        right_on="TAG",
        how="left"
    )

    por_item["PESO"] = (
        pd.to_numeric(
            por_item["PESO"],
            errors="coerce"
        )
        .fillna(0)
    )

    por_item["SAT"] = (
        pd.to_numeric(
            por_item["SAT"],
            errors="coerce"
        )
    )

    # frequência efetivamente pontuada
    por_item["CONTAGEM_PONTUADA"] = por_item.apply(
        lambda row: min(
            row["CONTAGEM"],
            row["SAT"]
        )
        if pd.notna(row["SAT"])
        else row["CONTAGEM"],
        axis=1
    )

    # valor final
    por_item["VALOR"] = (
        por_item["CONTAGEM_PONTUADA"]
        * por_item["PESO"]
    )

    por_item = por_item.sort_values(
        ["VALOR", "CONTAGEM"],
        ascending=[False, False]
    )


    por_item_natureza = (
        df.groupby(["GRUPO", "ITEM", "NATUREZA"], dropna=False)
        .size()
        .reset_index(name="CONTAGEM")
        .sort_values(["GRUPO", "ITEM", "CONTAGEM"], ascending=[True, True, False])
    )

    por_ano = (
        df.dropna(subset=["ANO"])
        .assign(ANO=lambda x: x["ANO"].astype(int))
        .groupby(["ANO", "GRUPO"], dropna=False)
        .size()
        .reset_index(name="CONTAGEM")
        .sort_values(["ANO", "GRUPO"])
    )
    return por_item, por_item_natureza, por_ano


@st.cache_data
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


def format_lattes_date(value: str) -> str:
    value = normalize_space(value)
    if len(value) == 8 and value.isdigit():
        return f"{value[:2]}/{value[2:4]}/{value[4:]}"
    return value


def read_pesos_tags(path: str | Path = "pesos_tags_lattes.csv") -> pd.DataFrame:
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    if not path.exists():
        return pd.DataFrame(columns=["TAG", "PESO", "SAT"])


    # ler a planilha como xls
    sheet_id = "1rW1U0nG9Ua6Y5VOwzWxXfpSaLEKFrUp5XqXwGcuetjw"

    url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{sheet_id}/export?format=xlsx"
    )

    pesos = pd.read_excel(url)

    pesos = pd.read_excel(
        url,
        sheet_name="REF"
    )


    #pesos = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    #pesos.dropna(inplace=True)
    pesos.columns = [normalize_space(c).upper() for c in pesos.columns]

    if "TAG" not in pesos.columns or "PESO" not in pesos.columns:
        raise ValueError("O arquivo deve conter TAG e PESO.")

    if "SAT" not in pesos.columns:
        pesos["SAT"] = pd.NA

    pesos = pesos[["TAG", "PESO", "SAT"]].copy()
    pesos["TAG"] = pesos["TAG"].map(normalize_space)
    pesos["PESO"] = pd.to_numeric(pesos["PESO"], errors="coerce").fillna(0.0)
    pesos["SAT"] = pd.to_numeric(pesos["SAT"], errors="coerce")

    pesos = pesos[pesos["TAG"] != ""]
    pesos = pesos.drop_duplicates(subset=["TAG"], keep="last")

    return pesos.reset_index(drop=True)



def read_pesos_tags_por_area(area: str, path: str | Path = "pesos_tags_lattes.csv") -> pd.DataFrame:
    """
    Lê a planilha do Lattes e retorna as TAGs com os PESOs e SATurações 
    específicos da área informada (ex: 'BIO', 'HUM', 'EXA').
    """
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    # Mantido a verificação de existência física apenas se necessário, 
    # mas como você está lendo da URL do Google, o foco é o download online.
    sheet_id = "1rW1U0nG9Ua6Y5VOwzWxXfpSaLEKFrUp5XqXwGcuetjw"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    try:
        # Lê diretamente a aba 'REF' do Excel online
        pesos = pd.read_excel(url, sheet_name="REF")
    except Exception:
        # Fallback caso queira ler do arquivo local se a internet falhar
        if path.exists():
            pesos = pd.read_excel(path, sheet_name="REF")
        else:
            return pd.DataFrame(columns=["TAG", "PESO", "SAT"])

    # Normaliza os nomes das colunas
    pesos.columns = [normalize_space(c).upper() for c in pesos.columns]

    # Validação das colunas obrigatórias globais
    if "TAG" not in pesos.columns or "PESO" not in pesos.columns:
        raise ValueError("O arquivo deve conter as colunas bases TAG e PESO.")

    # Trata o nome da área fornecida (garante que está em maiúsculo)
    area_busca = normalize_space(area).upper()
    col_peso_area = f"PESO-{area_busca}"
    col_sat_area = f"SAT-{area_busca}"

    # Define qual coluna de PESO usar (se a da área existir, usa ela, senão usa a geral)
    if col_peso_area in pesos.columns:
        pesos["PESO_FINAL"] = pd.to_numeric(pesos[col_peso_area], errors="coerce")
    else:
        pesos["PESO_FINAL"] = pd.to_numeric(pesos["PESO"], errors="coerce")

    # Define qual coluna de SAT usar (se a da área existir, usa ela, senão usa a geral)
    if col_sat_area in pesos.columns:
        pesos["SAT_FINAL"] = pd.to_numeric(pesos[col_sat_area], errors="coerce")
    elif "SAT" in pesos.columns:
        pesos["SAT_FINAL"] = pd.to_numeric(pesos["SAT"], errors="coerce")
    else:
        pesos["SAT_FINAL"] = pd.NA

    # Cria o DataFrame final padronizado com os dados da área escolhida
    df_area = pesos[["TAG", "PESO_FINAL", "SAT_FINAL"]].copy()
    df_area.columns = ["TAG", "PESO", "SAT"]  # Renomeia de volta para o padrão esperado pelo seu sistema

    # Limpeza de strings e remoção de nulos/duplicados (mantendo a última ocorrência)
    df_area["TAG"] = df_area["TAG"].map(normalize_space)
    df_area["PESO"] = df_area["PESO"].fillna(0.0)
    
    df_area = df_area[df_area["TAG"] != ""]
    df_area = df_area.drop_duplicates(subset=["TAG"], keep="last")

    return df_area.reset_index(drop=True)



def calcular_pontuacao_ponderada(tag_counts: pd.DataFrame, pesos: pd.DataFrame) -> pd.DataFrame:
    if tag_counts.empty:
        tag_counts = pd.DataFrame(columns=["TAG", "FREQUENCIA"])
    else:
        tag_counts = tag_counts[["TAG", "FREQUENCIA"]].copy()
        tag_counts["TAG"] = tag_counts["TAG"].map(normalize_space)
        tag_counts["FREQUENCIA"] = pd.to_numeric(
            tag_counts["FREQUENCIA"], errors="coerce"
        ).fillna(0).astype(int)

    if pesos.empty:
        pesos = pd.DataFrame(columns=["TAG", "PESO", "SAT"])

    todas_tags = pd.DataFrame(
        {"TAG": sorted(set(tag_counts["TAG"].dropna()) | set(pesos["TAG"].dropna()))}
    )

    resultado = (
        todas_tags
        .merge(tag_counts, on="TAG", how="left")
        .merge(pesos, on="TAG", how="left")
    )

    resultado["FREQUENCIA"] = resultado["FREQUENCIA"].fillna(0).astype(int)
    resultado["PESO"] = pd.to_numeric(resultado["PESO"], errors="coerce").fillna(0.0)
    resultado["SAT"] = pd.to_numeric(resultado["SAT"], errors="coerce")

    resultado["FREQUENCIA_PONTUADA"] = resultado.apply(
        lambda row: min(row["FREQUENCIA"], row["SAT"])
        if pd.notna(row["SAT"])
        else row["FREQUENCIA"],
        axis=1,
    )

    resultado["PONTOS"] = resultado["FREQUENCIA_PONTUADA"] * resultado["PESO"]

    resultado = resultado.sort_values(
        ["PONTOS", "FREQUENCIA", "TAG"],
        ascending=[False, False, True],
    )

    return resultado.reset_index(drop=True)


# -----------------------------------------------------------------------------
# Interface Streamlit
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Extrator XML Lattes", layout="wide")
st.title("Extrator de Currículo Lattes - Pontuação por Comitê")
st.caption("Aceita arquivo .xml ou .zip contendo o XML do Lattes e gera tabelas de contagem por item.")

uploaded_file = st.file_uploader(
    "Escolha o arquivo XML ou ZIP do Currículo Lattes",
    type=["xml", "zip"],
    accept_multiple_files=False,
)

col_a, col_b = st.columns([1, 2])
with col_a:
    current_year = dt.date.today().year
    ano_ref = st.number_input(
        "Ano inicial para contabilização", 
        min_value=1900,
        max_value=current_year,
        value=max(current_year - 3, 1900),
        step=1,
    )

with col_b:
    grupos_disponiveis = sorted({spec["grupo"] for spec in ITEM_SPECS.values()})
    grupos = st.multiselect(
        "Grupos a contabilizar",
        options=grupos_disponiveis,
        default=grupos_disponiveis,
    )

selected_tags = {tag for tag, spec in ITEM_SPECS.items() if spec["grupo"] in set(grupos)}


#gerar_xml_teste(ITEM_SPECS,"lattes_teste_completo.xml")

df_pontos = []
if uploaded_file is not None:
    try:
        tree, xml_name = read_uploaded_lattes(uploaded_file)
        root = tree.getroot()
        ident = extract_identification(root)
        df = extract_records(root, int(ano_ref), selected_tags)


        st.subheader("Identificação")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Nome", ident["nome"])
        m2.metric("ID Lattes", ident["id_lattes"] or "-")
        m3.metric("ORCID", ident["orcid"] or "-")
        m4.metric("Atualização", format_lattes_date(ident["atualizacao"]) or "-")
        st.caption(f"Arquivo lido: {xml_name}")
        base_name = normalize_space(ident["nome"]).lower().replace(" ", "_") or "lattes"

        st.subheader("Resumo")
        c1, c2, c3 = st.columns(3)
        c1.metric("Registros contabilizados", len(df))
        c2.metric("Tipos de item", df["ITEM"].nunique() if not df.empty else 0)
        c3.metric("Ano inicial", int(ano_ref))

        tag_counts = pd.DataFrame(
            Counter(e.tag for e in root.iter()).most_common(),
            columns=["TAG", "FREQUENCIA"],
        )
        
        pesos_tags = read_pesos_tags("pesos_tags_lattes.csv")
                    
        #--
        grupos_para_buscar = ['BIO', 'SAU', 'EXA', 'HUM', 'CSA', 'ENG', 'LLA']
        
        dic_pontos={'Nome':ident["nome"]}
        for grupo_alvo in grupos_para_buscar:
            st.header(f"\n[BUSCA] Isolando dados do grupo: {grupo_alvo} ")
            st.write(f"\n[BUSCA] Isolando dados do grupo: {grupo_alvo} ")
            pesos_tags = read_pesos_tags_por_area(grupo_alvo, "pesos_tags_lattes.csv")
                
            #--
            tabela_pontos = calcular_pontuacao_ponderada(tag_counts, pesos_tags)
            total_pontos = float(tabela_pontos["PONTOS"].sum()) if not tabela_pontos.empty else 0.0
            dic_pontos[grupo_alvo] = total_pontos
            
            # cria dicionário TAG -> PESO
            pesos_dict = dict(
                zip(
                    pesos_tags["TAG"],
                    pesos_tags["PESO"]
                )
            )
    
            # peso individual de cada registro
            df["VALOR"] = (
                df["ITEM"]
                .map(pesos_dict)
                .fillna(0)
            )
            df["VALOR"] = df["VALOR"].astype(float)
    
            df["PONTOS_ITEM"] = (
                df["ITEM"]
                .map(pesos_dict)
                .fillna(0)
            )
    
            #df["PONTOS_ACUMULADOS"] = (
            #    df["ITEM"]
            #    .map(pesos_dict)
            #    .fillna(0)
            #    .cumsum()
            #)
    
    
            por_item, por_item_natureza, por_ano = summarize_counts(df, pesos_tags)
    
    
            if df.empty:
                st.warning("Nenhum registro encontrado para os grupos e ano inicial selecionados.")
            else:
                st.subheader("Contagem por item")
                total_pontos = por_item['VALOR'].sum() 
                por_item.drop(['TAG'], axis=1, inplace=True)
                st.metric("Pontuação total ponderada", f"{total_pontos:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.dataframe(por_item, use_container_width=True, hide_index=True)
    
                #st.subheader("Contagem por item e natureza")
                #st.dataframe(por_item_natureza, use_container_width=True, hide_index=True)
    
                #st.subheader("Contagem por ano e grupo")
                #st.dataframe(por_ano, use_container_width=True, hide_index=True)
    
                st.subheader("Registros detalhados")
                st.dataframe(df, use_container_width=True, hide_index=True)
    
                #st.download_button(
                #    "Baixar registros detalhados CSV",
                #    data=to_csv_bytes(df),
                #    file_name=f"{base_name}_detalhado.csv",  
                #    mime="text/csv",
                #)
                #st.download_button(
                #    "Baixar contagem por item CSV",
                #    data=to_csv_bytes(por_item),
                #    file_name=f"{base_name}_contagem_por_item.csv",
                #    mime="text/csv",
                #)
    
        
        # ... (código anterior permanece igual até o final do loop)

        # CORREÇÃO: Remova a linha df_pontos.append(dic_pontos) e substitua por:
        if 'lista_pontuacoes' not in st.session_state:
            st.session_state.lista_pontuacoes = []
        
        st.session_state.lista_pontuacoes.append(dic_pontos)
    
    except Exception as exc:
        st.error(f"Erro ao processar o arquivo: {exc}")
    
    # CORREÇÃO: Crie o DataFrame corretamente
    if 'lista_pontuacoes' in st.session_state and st.session_state.lista_pontuacoes:
        # Método 1: Usar pd.DataFrame.from_dict com orient='index' (recomendado)
        df_pontos = pd.DataFrame.from_dict(st.session_state.lista_pontuacoes)
        
        # OU Método 2: Se preferir o formato atual (uma linha por grupo)
        # df_pontos = pd.DataFrame([st.session_state.lista_pontuacoes[0]], index=[0])
        
        st.subheader("🏆 Pontuação por Grupo/Área")
        
        # Estilizar o DataFrame
        st.dataframe(
            df_pontos.style
            .format('{:.2f}', subset=grupos_para_buscar)
            .background_gradient(cmap='Blues', subset=grupos_para_buscar)
            .set_properties(**{'text-align': 'center'})
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]),
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico de barras com Plotly
        st.subheader("📊 Distribuição de Pontuação por Grupo")
        
        # Preparar dados para o gráfico
        df_plot = df_pontos.melt(
            id_vars=['Nome'],
            var_name='Grupo',
            value_name='Pontuação'
        )
        
        import plotly.express as px
        
        fig = px.bar(
            df_plot,
            x='Grupo',
            y='Pontuação',
            title='Pontuação Total por Grupo/Área',
            color='Grupo',
            text='Pontuação',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig.update_traces(
            texttemplate='%{text:.2f}',
            textposition='outside'
        )
        fig.update_layout(
            showlegend=False,
            xaxis_title="Grupo/Área",
            yaxis_title="Pontuação Total",
            height=500,
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis={'categoryorder':'total descending'}  # Ordenar por pontuação
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Opcional: Mostrar métricas adicionais
        st.subheader("📈 Métricas por Grupo")
        cols = st.columns(len(grupos_para_buscar))
        for idx, grupo in enumerate(grupos_para_buscar):
            with cols[idx]:
                pontuacao = df_pontos[grupo].iloc[0] if not df_pontos.empty else 0
                st.metric(
                    label=grupo,
                    value=f"{pontuacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    delta=None
                )
    else:
        st.warning("Nenhuma pontuação calculada ainda.")