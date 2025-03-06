import streamlit as st

# Título da página
st.title('Gestão de Insumos')

# Descrição da página
st.write('Bem-vindo à página de gestão de insumos. Aqui você pode gerenciar todos os insumos necessários para o seu projeto.')

# Formulário para adicionar novos insumos
st.header('Adicionar Novo Insumo')
with st.form(key='add_insumo_form'):
    nome_insumo = st.text_input('Nome do Insumo')
    quantidade = st.number_input('Quantidade', min_value=0, step=1)
    unidade = st.selectbox('Unidade de Medida', ['kg', 'litros', 'unidades'])
    submit_button = st.form_submit_button(label='Adicionar')

    if submit_button:
        st.success(f'Insumo {nome_insumo} adicionado com sucesso!')

# Lista de insumos (exemplo estático)
st.header('Lista de Insumos')
insumos = [
    {'nome': 'Insumo 1', 'quantidade': 10, 'unidade': 'kg'},
    {'nome': 'Insumo 2', 'quantidade': 5, 'unidade': 'litros'},
    {'nome': 'Insumo 3', 'quantidade': 20, 'unidade': 'unidades'}
]

for insumo in insumos:
    st.write(f"{insumo['nome']} - {insumo['quantidade']} {insumo['unidade']}")

# Rodapé
st.write('© 2023 Gestão de Insumos')