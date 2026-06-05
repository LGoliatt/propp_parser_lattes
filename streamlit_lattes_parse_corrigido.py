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
from typing import BinaryIO, Iterable

import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET


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


def summarize_counts(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    por_item = (
        df.groupby(["GRUPO", "ITEM"], dropna=False)
        .size()
        .reset_index(name="CONTAGEM")
        .sort_values(["GRUPO", "CONTAGEM", "ITEM"], ascending=[True, False, True])
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


# -----------------------------------------------------------------------------
# Interface Streamlit
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Leitor XML Lattes", layout="wide")
st.title("Leitor de Currículo Lattes")
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

if uploaded_file is not None:
    try:
        tree, xml_name = read_uploaded_lattes(uploaded_file)
        root = tree.getroot()
        ident = extract_identification(root)
        df = extract_records(root, int(ano_ref), selected_tags)
        por_item, por_item_natureza, por_ano = summarize_counts(df)

        st.subheader("Identificação")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Nome", ident["nome"])
        m2.metric("ID Lattes", ident["id_lattes"] or "-")
        m3.metric("ORCID", ident["orcid"] or "-")
        m4.metric("Atualização", format_lattes_date(ident["atualizacao"]) or "-")
        st.caption(f"Arquivo lido: {xml_name}")

        st.subheader("Resumo")
        c1, c2, c3 = st.columns(3)
        c1.metric("Registros contabilizados", len(df))
        c2.metric("Tipos de item", df["ITEM"].nunique() if not df.empty else 0)
        c3.metric("Ano inicial", int(ano_ref))

        if df.empty:
            st.warning("Nenhum registro encontrado para os grupos e ano inicial selecionados.")
        else:
            st.subheader("Contagem por item")
            st.dataframe(por_item, use_container_width=True, hide_index=True)

            st.subheader("Contagem por item e natureza")
            st.dataframe(por_item_natureza, use_container_width=True, hide_index=True)

            st.subheader("Contagem por ano e grupo")
            st.dataframe(por_ano, use_container_width=True, hide_index=True)

            st.subheader("Registros detalhados")
            st.dataframe(df, use_container_width=True, hide_index=True)

            base_name = normalize_space(ident["nome"]).lower().replace(" ", "_") or "lattes"
            st.download_button(
                "Baixar registros detalhados CSV",
                data=to_csv_bytes(df),
                file_name=f"{base_name}_detalhado.csv",
                mime="text/csv",
            )
            st.download_button(
                "Baixar contagem por item CSV",
                data=to_csv_bytes(por_item),
                file_name=f"{base_name}_contagem_por_item.csv",
                mime="text/csv",
            )

        with st.expander("Diagnóstico: todas as tags encontradas no XML"):
            tag_counts = pd.DataFrame(Counter(e.tag for e in root.iter()).most_common(), columns=["TAG", "FREQUENCIA"])
            st.dataframe(tag_counts, use_container_width=True, hide_index=True)
            st.download_button(
                "Baixar diagnóstico de tags CSV",
                data=to_csv_bytes(tag_counts),
                file_name="diagnostico_tags_lattes.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"Erro ao processar o arquivo: {exc}")
