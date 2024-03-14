# -*- coding: utf-8 -*-
#%%: streamlit run /home/goliatt/cpa_ufjf/streamlit_app.py 
import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

#%%

#%%
def get_all_tags(filename):
  """
  This function parses an XML file and returns a list of all tag names encountered.

  Args:
      filename: The path to the XML file.

  Returns:
      A list of all unique tag names in the XML file.
  """
  try:
    tree = ET.parse(filename)
    root = tree.getroot()

    all_tags = set()  # Use a set to ensure unique tags

    def explore_element(element):
      """
      Recursive function to traverse the element tree and collect tags.
  
      Args:
          element: The current element to explore.
      """
      all_tags.add(element.tag)  # Add current element's tag to the set
      for child in element:
        explore_element(child)  # Recursively explore child elements

    explore_element(root)
    return list(all_tags)  # Convert the set to a list

  except FileNotFoundError:
    print(f"Error: File '{filename}' not found.")
  except ET.ParseError as e:
    print(f"Error parsing XML file: {e}")
    
    
def get_attr(xmldata):
    attributes = []
    for child in (xmldata):
        if len(child.attrib)!= 0:
            attributes.append(child.attrib)
    
        get_attr(child)
    return attributes

def atualiza_qualis():
    qn='./qualis/classificações_publicadas_todas_as_areas_avaliacao1672761192111.xlsx'
    Q=pd.read_excel(qn)
    Q[['ISSN','Estrato']].drop_duplicates().to_csv('./qualis/qualis.csv', sep=';', index=False)
    return None

def read_qualis(fn='./qualis/qualis.csv'):
   qualis=pd.read_csv(fn,sep=';')
   qualis['ISSN'] = [i.replace('-','') for i in qualis['ISSN'].values]
   qualis=dict(zip(qualis['ISSN'], qualis['Estrato']))
   return qualis
    
def read_tags():
    
    key='1U7K2TGPz6YPLJPKgjOp-io0an94dSVQvtq9-lttYH4M'
    link='https://docs.google.com/spreadsheet/ccc?key='+key+'&output=csv'
    tags = pd.read_csv(link, sep=',')
    
    idx=[i=='Sim' for i in  tags['Contabilizar'].values]
    list_tags = list(tags['Tag'][idx].values)

    return list_tags

def get_properties(tag,attributes,ref):
    
    if tag=='ARTIGO-PUBLICADO':
        print(tag)
        natureza=attributes[0]['NATUREZA']
        issn=attributes[1]['ISSN']
        issn_qualis=qualis.get(issn)
        ano=attributes[0]['ANO-DO-ARTIGO']
        titulo=attributes[0]['TITULO-DO-ARTIGO']
        if int(ano)<int(ref):
            return {}
        
        return {'TIPO-PRODUCAO':tag, 'NATUREZA':natureza,'ANO':ano, 
                #'ISSN':issn, 
                'ESTRATO':issn_qualis,
                'PONTOS':0, 'TITULO':titulo}
    
    if tag=='TRABALHO-EM-EVENTOS':
        print(tag)
        natureza=attributes[0]['NATUREZA']
        ano=attributes[0]['ANO-DO-TRABALHO']
        titulo=attributes[0]['TITULO-DO-TRABALHO']
        if int(ano)<int(ref):
            return {}
        
        return {'TIPO-PRODUCAO':tag, 'NATUREZA':natureza,'ANO':ano, 
                'PONTOS':0, 'TITULO':titulo}
    
    if tag=='CAPITULO-DE-LIVRO-PUBLICADO':
        print(tag)
        natureza=attributes[0]['TIPO']
        ano=attributes[0]['ANO']
        titulo=attributes[0]['TITULO-DO-CAPITULO-DO-LIVRO']
        if int(ano)<int(ref):
            return {}
        
        return {'TIPO-PRODUCAO':tag, 'NATUREZA':natureza,'ANO':ano, 
                'PONTOS':0, 'TITULO':titulo}
    
    if tag=='PATENTE':
        print(tag)
        natureza=attributes[1]['CATEGORIA']
        ano=attributes[0]['ANO-DESENVOLVIMENTO']
        titulo=attributes[0]['TITULO']
        if int(ano)<int(ref):
            return {}
        
        return {'TIPO-PRODUCAO':tag, 'NATUREZA':natureza,'ANO':ano, 
                'PONTOS':0, 'TITULO':titulo}
    
    if tag=='PRODUCAO-ARTISTICA-CULTURAL':
        print(tag)
        natureza=attributes[1]['CATEGORIA']
        ano=attributes[0]['ANO-DESENVOLVIMENTO']
        titulo=attributes[0]['TITULO']
        if int(ano)<int(ref):
            return {}
        
        return {'TIPO-PRODUCAO':tag, 'NATUREZA':natureza,'ANO':ano, 
                'PONTOS':0, 'TITULO':titulo}
    else:
        return {}
    
    
#%% page setup
st.set_page_config(layout="wide")  # this needs to be the first Streamlit command
st.title('PROPP - XML Lattes')
flag_anonymous=True
#add title
st.header("Universidade Federal de Juiz de Fora")


st.markdown('**Leitura do arquivo XML**')
uploaded_file = st.file_uploader(
     label='Escolha o arquivo XML do Currículo Lattes',
     type=['xml'],
     accept_multiple_files=False, key='uploaded_file',
     #label_visibility='hidden',
     )

ano_ref = st.number_input(label="Entre com o ano de referência",
                min_value=1980, max_value=2024, value=2021, 
                step=1, format="%d")  

qualis=read_qualis()
#uploaded_file = './data/9030707448549156.zip'
#uploaded_file = './data/9030707448549156.xml'
#uploaded_file = 'data/xml_cvbase_src_main_resources_CurriculoLattes.xsd'
#uploaded_file = '/home/goliatt/Downloads/6885901755516721.xml'
#uploaded_file = '/home/goliatt/Downloads/5673981788072449.xml'
#       uploaded_file = '/home/goliatt/Downloads/0633665122312619.xml'

#%%
A=[]    
if uploaded_file is not None:
    # Read the uploaded file content
    #bytes_data = uploaded_file.read()

    # Display some information about the uploaded file (optional)
    #st.write("Filename:", uploaded_file.name)
    #st.write("File size:", uploaded_file.size, "bytes")

    #archive = zipfile.ZipFile(uploaded_file, 'r')
    #xmlfile = archive.open('curriculo.xml')
    
    xmlTree = ET.parse(uploaded_file)

    dados_gerais = []
    root=xmlTree.getroot()
    for child in (root):
        if len(child.attrib)!= 0:
            dados_gerais.append(child.attrib)

    nome_completo=dados_gerais[0]['NOME-COMPLETO']    
    orcid_id=dados_gerais[0]['ORCID-ID']    

    st.metric(label="Nome", value=nome_completo, delta=orcid_id)
    with st.status("Buscando lista de tags..."):
        st.write("Fazendo download das tags...")
        list_tags = read_tags()
        st.write("Tags atualizadas...")
        
    list_tags=[
    # -- SEGMENTO DA PRODUCAO TECNICA
    "CULTIVAR-REGISTRADA",
    "SOFTWARE",
    "PATENTE",
    "CULTIVAR-PROTEGIDA",
    "DESENHO-INDUSTRIAL",
    "MARCA",
    "TOPOGRAFIA-DE-CIRCUITO-INTEGRADO",
    "PRODUTO-TECNOLOGICO",
    "PROCESSOS-OU-TECNICAS",
     #"TRABALHO-TECNICO",
    "DEMAIS-TIPOS-DE-PRODUCAO-TECNICA",
    # -- SEGMENTO DA PRODUCAO BIBLIOGRAFICA
    "TRABALHOS-EM-EVENTOS",
    "ARTIGOS-PUBLICADOS",
    "LIVROS-E-CAPITULOS",
    "TEXTOS-EM-JORNAIS-OU-REVISTAS",
    "DEMAIS-TIPOS-DE-PRODUCAO-BIBLIOGRAFICA",
    "ARTIGOS-ACEITOS-PARA-PUBLICACAO",
    # -- SEGMENTO DE OUTRA PRODUCAO
    "PRODUCAO-ARTISTICA-CULTURAL",
    "ORIENTACOES-CONCLUIDAS",
    #"DEMAIS-TRABALHOS",
    # -- SEGMENTO DE DADOS-COMPLEMENTARES
    #"FORMACAO-COMPLEMENTAR",
    "PARTICIPACAO-EM-BANCA-TRABALHOS-CONCLUSAO",
    "PARTICIPACAO-EM-BANCA-JULGADORA",
    "PARTICIPACAO-EM-EVENTOS-CONGRESSOS",
    "ORIENTACOES-EM-ANDAMENTO",
    #"INFORMACOES-ADICIONAIS-INSTITUICOES",
    #"INFORMACOES-ADICIONAIS-CURSOS",
    ]
    
   
    for elem in xmlTree.iter():
        #print(elem.tag, end='\t\t')
        #attributes = get_attr(elem)
        #if 'PAT' in elem.tag:
        #    print(elem.tag,elem.getchildren())        
        
        if elem.tag in list_tags:   
            attributes = get_attr(elem)
            #print(attributes)
            if len(attributes)>0:
                attributes[0]['TIPO-PRODUCAO']=elem.tag
                if len(elem.items())!=0:
                    line=get_properties(elem.tag, attributes, ano_ref)              
                    A.append(line)
                else:
                    for e in elem:
                        attribute = get_attr(e)
                        #print(f"{elem.tag} \t\t--\t {e.tag}")
                        line=get_properties(e.tag, attribute, ano_ref)              
                        A.append(line)
                    
                #line=get_properties(elem.tag, attributes, ano_ref)
                #A.append(line)
                
#%%
    A=pd.DataFrame(A)
    A.dropna(inplace=True,how='all')
    A.drop_duplicates(inplace=True)
    B=A[['TIPO-PRODUCAO', 'NATUREZA',]].value_counts()
    st.table(B)
    #st.dataframe(A, hide_index=True)
    st.table(A)
#%%     

#%%     


