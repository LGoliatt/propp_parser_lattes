
import untangle
import zipfile
import glob
import re
import os

path='./data/'
cv = glob.glob(path+'*.zip')

aux='curriculo.xml'

for fn in cv:
    print(fn)    
    zipfile.ZipFile(fn).extractall()
    fl=fn.replace('.zip','.xml')            
    os.system('mv curriculo.xml '+fl)
    
    obj = untangle.parse(fl)
    
    print(obj.CURRICULO_VITAE)
#%%
import xml.etree.ElementTree as ET
import xmltodict
for fn in cv:
    print(fn)    
    zipfile.ZipFile(fn).extractall()
    fl=fn.replace('.zip','.xml')            
    os.system('mv curriculo.xml '+fl)
    
    tree = ET.parse(fl)
    root = tree.getroot()
    
    s=[(x.tag, x.attrib) for x in root]
    #for i in root[1]:
    #    print(i)
    #    for j in i:
    #        print(j)
    with open(fl,  mode='r', encoding='ISO-8859-1') as f:
        contents = f.read()
        print(contents)
        
    doc = xmltodict.parse()
#%%

import xml.etree.ElementTree as ET

def extrair_dados_lattes(arquivo_xml):
    tree = ET.parse(arquivo_xml)
    root = tree.getroot()

    # Extrair dados pessoais
    dados_pessoais = root.find(".//DADOS-GERAIS")
    nome = dados_pessoais.get("NOME-COMPLETO")
    email = dados_pessoais.get("NACIONALIDADE")
    telefone = dados_pessoais.get("ORCID-ID")

    # Extrair informações acadêmicas
    formacao = []
    formacoes = root.findall(".//FORMACAO-ACADEMICA-TITULACAO/GRADUACAO")
    for graduacao in formacoes:
        curso = graduacao.find("NOME-CURSO").text
        instituicao = graduacao.find("NOME-INSTITUICAO").text
        ano_conclusao = graduacao.find("ANO-DE-CONCLUSAO").text
        formacao.append({"curso": curso, "instituicao": instituicao, "ano_conclusao": ano_conclusao})

    # Extrair informações de experiência profissional
    experiencia = []
    experiencias_profissionais = root.findall(".//ATUACAO-PROFISSIONAL")
    for experiencia_profissional in experiencias_profissionais:
        cargo = experiencia_profissional.find("CARGO-FUNCAO").text
        instituicao = experiencia_profissional.find("NOME-INSTITUICAO").text
        experiencia.append({"cargo": cargo, "instituicao": instituicao})

    # Retornar os dados extraídos
    return {
        "nome": nome,
        "email": email,
        "telefone": telefone,
        "formacao": formacao,
        "experiencia": experiencia
    }

# Exemplo de uso
arquivo_xml = "./data/9030707448549156.xml"
dados_lattes = extrair_dados_lattes(arquivo_xml)
    print(dados_lattes)

#%%

import xml.etree.ElementTree as ET

def extrair_dados_lattes(arquivo_xml):
    # Faz o parsing do arquivo XML
    tree = ET.parse(arquivo_xml)
    root = tree.getroot()

    # Extrai os dados do currículo Lattes
    dados = {}

    # Extrai informações pessoais
    dados['nome'] = root.findtext('.//DADOS-GERAIS/NOME-COMPLETO')
    dados['nacionalidade'] = root.findtext('.//DADOS-GERAIS/NACIONALIDADE')

    # Extrai formação acadêmica
    formacao = []
    for formacao_elem in root.findall('.//FORMACAO-ACADEMICA-TITULACAO/GRADUACAO'):
        formacao.append({
            'instituicao': formacao_elem.findtext('NOME-INSTITUICAO'),
            'curso': formacao_elem.findtext('NOME-CURSO'),
            'ano_conclusao': formacao_elem.findtext('ANO-DE-CONCLUSAO')
        })
    dados['formacao'] = formacao

    # Extrai experiência profissional
    experiencia = []
    for experiencia_elem in root.findall('.//ATUACAO-PROFISSIONAL'):
        experiencia.append({
            'instituicao': experiencia_elem.findtext('NOME-INSTITUICAO'),
            'cargo': experiencia_elem.findtext('NOME-DO-CARGO')
        })
    dados['experiencia'] = experiencia

    return dados

# Exemplo de uso
arquivo_xml = "./data/9030707448549156.xml"
dados_lattes = extrair_dados_lattes(arquivo_xml)

# Imprime os dados extraídos
print('Nome:', dados_lattes['nome'])
print('Nacionalidade:', dados_lattes['nacionalidade'])
print('Formação Acadêmica:')
for formacao in dados_lattes['formacao']:
    print('- Instituição:', formacao['instituicao'])
    print('  Curso:', formacao['curso'])
    print('  Ano de Conclusão:', formacao['ano_conclusao'])
print('Experiência Profissional:')
for experiencia in dados_lattes['experiencia']:
    print('- Instituição:', experiencia['instituicao'])
    print('  Cargo:', experiencia['cargo'])

#%%
from bs4 import BeautifulSoup

# lendo do zipfile
zipname = fn

zipfilepath = str(zipname); 
archive = zipfile.ZipFile(zipfilepath, 'r')
lattesxmldata = archive.open('curriculo.xml')
soup = BeautifulSoup(lattesxmldata, 'lxml',
                     from_encoding='ISO-8859-1')
# capturando nome completo para ordem de autoria
cv = soup.find_all('curriculo-vitae')
if len(cv) == 0:
    print('curriculo vitae nao encontrado para', zipname)
else:
    # listas para armazenamento de dados producao tecnica
    for i in range(len(cv)):
        dg = cv[i].find_all('dados-gerais')
        # VERIFICANDO se ha dados gerais
        if len(dg) == 0:
            print('Dados gerais nao encontrados para', zipname)
        else:
            for j in range(len(dg)):
                # definindo nome completo
                gendata = str(dg[j])
                result = re.search('nome-completo=\"(.*)\" nome-em-citacoes',
                                   gendata)
                #cc = fun_result(result)
                #fullname = cc
#%%
import xml.etree.ElementTree as ET
# load and parse the file


def get_attr(xml):
    attributes = []
    for child in (xml):
        if len(child.attrib)!= 0:
            attributes.append(child.attrib)
    
        get_attr(child)
    return attributes


xmlTree = ET.parse(fl)


list_tags=["ARTIGOS-PUBLICADOS","LIVROS-E-CAPITULOS","TRABALHOS-EM-EVENTOS",
           'ARTIGO-ACEITO-PARA-PUBLICACAO',
           "TRABALHOS-EM-EVENTOS",
           "TEXTOS-EM-JORNAIS-OU-REVISTAS",
           "DEMAIS-TIPOS-DE-PRODUCAO-BIBLIOGRAFICA",
           "LIVROS-PUBLICADOS-OU-ORGANIZADOS",
           "CAPITULOS-DE-LIVROS-PUBLICADOS",
           ]

list_tags=[]
for elem in xmlTree.iter():
    list_tags.append(elem.tag)

list_tags = list(set(list_tags))


'1U7K2TGPz6YPLJPKgjOp-io0an94dSVQvtq9-lttYH4M''

   
for elem in xmlTree.iter():
    if elem.tag in list_tags:   
        attributes = get_attr(elem)
        if len(attributes)>0:
            aux=attributes
            aux[0]['TIPO']=elem.tag
            print(aux[0])
            print(elem.tag, len(aux),aux[0])
            #aux[0]['ANO-DO-ARTIGO']
            #for s in aux:
            #    if 'NATUREZA' in s:
            #        print(s)
                    
# now I remove duplicities - by convertion to set and back to list
#elemList = list(set(elemList))

# Just printing out the result
#print(elemList)
    

#%%
import xml.etree.ElementTree as etree
xmlString= "<feed xml:lang='en'><title>World Wide Web</title><subtitle lang='en'>Programming challenges</subtitle><link rel='alternate' type='text/html' href='http://google.com/'/><updated>2019-12-25T12:00:00</updated></feed>"

with open(fl,  mode='r', encoding='ISO-8859-1') as f:
      xmlString = f.read()
      #print(xmlString)
      
xml= etree.fromstring(xmlString)  

def get_attr(xml):
    attributes = []
    for child in (xml):
        if len(child.attrib)!= 0:
            attributes.append(child.attrib)
    
        get_attr(child)
    return attributes

attributes = get_attr(xml)
print(attributes)          
                    
#%%                    

import untangle
import zipfile
import glob
import re
import os
import xml.etree.ElementTree as ET


path='./data/'
cv = glob.glob(path+'*.zip')
aux='curriculo.xml'
fn='./data/9030707448549156.zip'



print(fn)    
zipfile.ZipFile(fn).extractall()
fl=fn.replace('.zip','.xml')            
os.system('mv curriculo.xml '+fl)
    
tree = ET.parse(fl)

elemList = []
for elem in tree.iter():
    elemList.append(elem.tag)

elemList = list(set(elemList))

for i in (elemList): 
    print(i)

#%%

list_tags=[
    "PRODUCAO-BIBLIOGRAFICA",
]
tag="ARTIGOS-PUBLICADOS"
    
for element in tree.iter():
    if   element.tag in list_tags:  
        print(f"Tipo: {element.tag} - Tag: {element.attrib}")
        for aux in element.iter():
            if aux.tag==tag:
                print(f"Tipo: {aux.tag}")
                for aux1 in aux.iter():
                    print(f"Tipo: {aux1.tag}")
                    
        #     print(f"Tipo: {element.tag} - Tag: {aux.tag}")
        #     if aux.attrib:  # Check if element has attributes
        #         print("Attributes:")
        #         for attr_name, attr_value in aux.attrib.items():
        #             print(f"\t- {attr_name}: {attr_value}")
        #         if aux.text:  # Check if element has text content (optional)
        #             print(f"Content: {element.text}")
          
        print('-'*80)
#%%

