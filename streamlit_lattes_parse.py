# -*- coding: utf-8 -*-
#%%: streamlit run /home/goliatt/cpa_ufjf/streamlit_app.py 
import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

#%%
ano_ref=2001

#%%
def get_attr(xml):
    attributes = []
    for child in (xml):
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
    list_tags = tags['Tag'][idx].values

    return list_tags
#%% page setup
st.set_page_config(layout="wide")  # this needs to be the first Streamlit command
st.title('PROPP - XML Lattes')
flag_anonymous=True
#add title
st.header("Universidade Federal de Juiz de Fora")


st.markdown('**Leitura do arquivo XML**')
uploaded_file = st.file_uploader(
     label=':violet[Escolha o arquivo XML]',
     type=['xml'],
     accept_multiple_files=False, key='uploaded_file',
     label_visibility='hidden',
     )
    
#uploaded_file = './data/9030707448549156.zip'
#uploaded_file = './data/9030707448549156.xml'

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

    with st.status("Buscando lista de tags..."):
        st.write("Fazendo download das tags...")
        list_tags = read_tags()
        st.write("Tags atualizadas...")
        
    
    for elem in xmlTree.iter():
        if elem.tag in list_tags:   
            attributes = get_attr(elem)
            if len(attributes)>0:
                aux=attributes
                aux[0]['TIPO-PRODUCAO']=elem.tag
                #st.write(aux)
                #json_string = json.dumps(aux,indent=True)
                #print(elem.tag, len(aux),aux[0])
                #aux[0]['ANO-DO-ARTIGO']
                for s in aux:
                    if ('NATUREZA' in s) or ('TIPO' in s):
                        #print('**')                    
                        for i in s:                    
                            if 'ANO' in i:
                                k=i
                                                            
                        if k!=None:
                            ano=int(s[k])
                                   
                            if ano>=ano_ref:
                                #print(ano)
                                #print(aux[0])            
                                # st.write(elem.tag, s.keys())
                                l=list(s.keys()); l=l[-1:]+l[:-1]; 
                                s={k: s[k] for k in l}
                                st.write(s)
                                #st.write('-'*80)
                                ss='NATUREZA' if 'NATUREZA' in s else 'TIPO'
                                #st.write(elem.tag, s[ss]) 
                                A.append({'TIPO-PRODUCAO':elem.tag, 'NATUREZA':s[ss]})
#%%
A=pd.DataFrame(A)
A.drop_duplicates(inplace=True)
st.dataframe(A, hide_index=True)
#%%     

#%%     


