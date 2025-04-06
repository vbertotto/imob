import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime
import os
import shutil
from io import BytesIO
import requests

# Configuração inicial
st.set_page_config(layout="wide")
DATA_FILE = "data/imoveis.csv"
IMAGES_DIR = "data/uploaded_images"
DOCS_DIR = "data/uploaded_docs"

# Garantir que a pasta data existe
os.makedirs("data", exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Função para extrair texto com OCR.space
def extract_text_from_pdf(pdf_path):
    api_key = 'K88752272288957'
    with open(pdf_path, 'rb') as f:
        r = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': f},
            data={
                'apikey': api_key,
                'language': 'por',
                'isOverlayRequired': False,
                'OCREngine': 2,
                'filetype': 'pdf'
            }
        )
    result = r.json()
    if result.get("IsErroredOnProcessing"):
        return "Erro ao processar OCR"
    return "\n".join([x["ParsedText"] for x in result.get("ParsedResults", []) if x.get("ParsedText")])

# Função para carregar dados
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE)
            if not df.empty:
                df['data_cadastro'] = pd.to_datetime(df['data_cadastro'])
            return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
    return pd.DataFrame(columns=[
        "corretor", "endereco", "lat", "lon",
        "data_cadastro", "fotos", "documentos", "status", "duplicado", "texto_ocr"
    ])

# Função para salvar dados
def save_data(df):
    try:
        temp_file = DATA_FILE + ".tmp"
        df.to_csv(temp_file, index=False)
        if os.path.exists(temp_file):
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            os.rename(temp_file, DATA_FILE)
            return True
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")
    return False

# Salvar arquivos
def save_uploaded_files(uploaded_files, target_dir):
    saved_paths = []
    try:
        for file in uploaded_files:
            if file is not None:
                file_path = os.path.join(target_dir, file.name)
                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())
                saved_paths.append(file_path)
    except Exception as e:
        st.error(f"Erro ao salvar arquivos: {e}")
    return saved_paths

# Interface para corretores
def corretor_interface():
    st.header("📤 Cadastro de Imóvel")
    with st.form("imovel_form", clear_on_submit=True):
        corretor = st.text_input("Seu Nome*", key="corretor")
        endereco = st.text_input("Endereço*", key="endereco")

        m = folium.Map(location=[-15.788497, -47.879873], zoom_start=12)
        m.add_child(folium.LatLngPopup())
        folium_static(m, width=700, height=300)

        col1, col2 = st.columns(2)
        lat = col1.number_input("Latitude*", format="%.6f", key="lat")
        lon = col2.number_input("Longitude*", format="%.6f", key="lon")

        fotos = st.file_uploader("Fotos do Imóvel", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="fotos")
        documentos = st.file_uploader("Documentos (PDF)", type=["pdf"], accept_multiple_files=True, key="documentos")

        submitted = st.form_submit_button("Cadastrar Imóvel")

        if submitted:
            if not corretor or not endereco or (lat == 0 and lon == 0):
                st.error("Por favor, preencha todos os campos obrigatórios (*)")
            else:
                with st.spinner("Salvando dados..."):
                    try:
                        foto_paths = save_uploaded_files(fotos, IMAGES_DIR)
                        doc_paths = save_uploaded_files(documentos, DOCS_DIR)

                        texto_extraido = ""
                        for doc in doc_paths:
                            texto_extraido += extract_text_from_pdf(doc) + "\n---\n"

                        df = load_data()
                        new_data = {
                            "corretor": corretor,
                            "endereco": endereco,
                            "lat": lat,
                            "lon": lon,
                            "data_cadastro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "fotos": ";".join(foto_paths) if foto_paths else "",
                            "documentos": ";".join(doc_paths) if doc_paths else "",
                            "status": "Pendente",
                            "duplicado": False,
                            "texto_ocr": texto_extraido.strip()
                        }
                        new_df = pd.DataFrame([new_data])
                        df = pd.concat([df, new_df], ignore_index=True)

                        duplicated_coords = df.duplicated(subset=["lat", "lon"], keep=False)
                        df["duplicado"] = duplicated_coords

                        if save_data(df):
                            st.success("✅ Imóvel cadastrado com sucesso!")
                            st.balloons()
                        else:
                            st.error("❌ Falha ao salvar os dados")
                    except Exception as e:
                        st.error(f"Erro durante o cadastro: {str(e)}")

# Checklist de terrenos analisados
def analisados_checklist():
    st.header("✅ Checklist de Terrenos Analisados")
    df = load_data()

    if df.empty:
        st.info("Nenhum imóvel cadastrado ainda.")
        return

    df_analisados = df[df['status'] == 'Analisado'].copy()

    if df_analisados.empty:
        st.info("Nenhum terreno analisado ainda.")
        return

    st.subheader("Lista de Terrenos Analisados")

    col1, col2 = st.columns(2)
    with col1:
        corretor_filter = st.multiselect(
            "Filtrar por corretor",
            options=df_analisados['corretor'].unique()
        )

    with col2:
        data_filter = st.date_input(
            "Filtrar por data de cadastro",
            value=[]
        )

    if corretor_filter:
        df_analisados = df_analisados[df_analisados['corretor'].isin(corretor_filter)]

    if data_filter:
        if isinstance(data_filter, list) and len(data_filter) == 2:
            start_date, end_date = data_filter
            df_analisados = df_analisados[
                (pd.to_datetime(df_analisados['data_cadastro']).dt.date >= start_date) &
                (pd.to_datetime(df_analisados['data_cadastro']).dt.date <= end_date)
            ]
        else:
            df_analisados = df_analisados[
                pd.to_datetime(df_analisados['data_cadastro']).dt.date == data_filter]

    st.dataframe(
        df_analisados[['corretor', 'endereco', 'data_cadastro', 'status']].rename(columns={
            'corretor': 'Corretor',
            'endereco': 'Endereço',
            'data_cadastro': 'Data de Cadastro',
            'status': 'Status'
        }),
        use_container_width=True,
        hide_index=True
    )

    if st.button("Exportar para Excel"):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_analisados.to_excel(writer, index=False, sheet_name='Terrenos Analisados')
        st.download_button(
            label="Baixar arquivo Excel",
            data=output.getvalue(),
            file_name="terrenos_analisados.xlsx",
            mime="application/vnd.ms-excel"
        )

# Painel do administrador
def admin_panel():
    st.header("📊 Painel do Administrador")
    df = load_data()

    if df.empty:
        st.info("Nenhum imóvel cadastrado ainda.")
        return

    tab1, tab2 = st.tabs(["📋 Painel Principal", "✅ Checklist Analisados"])

    with tab1:
        st.subheader("📍 Mapa de Imóveis")
        map_center = [df["lat"].mean(), df["lon"].mean()]
        m = folium.Map(location=map_center, zoom_start=12)

        for _, row in df.iterrows():
            popup_text = f"{row['endereco']}<br>Status: {row['status']}<br>Corretor: {row['corretor']}"
            color = 'red' if row.get("duplicado") else 'green'
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=popup_text,
                icon=folium.Icon(color=color)
            ).add_to(m)

        folium_static(m, width=800, height=500)

        st.subheader("📁 Lista de Imóveis")

        for idx, row in df.iterrows():
            with st.expander(f"📌 {row['endereco']} - Status: {row['status']}"):
                st.write(f"**Corretor:** {row['corretor']}")
                st.write(f"**Coordenadas:** ({row['lat']}, {row['lon']})")
                st.write(f"**Data de Cadastro:** {row['data_cadastro']}")
                st.write(f"**Status:** {row['status']}")
                if row.get("duplicado"):
                    st.warning("⚠️ Coordenada Duplicada")

                fotos = str(row['fotos']).split(";") if pd.notna(row['fotos']) and row['fotos'] != '' else []
                documentos = str(row['documentos']).split(";") if pd.notna(row['documentos']) and row['documentos'] != '' else []

                if fotos:
                    st.markdown("**Fotos:**")
                    cols = st.columns(3)
                    for i, foto in enumerate(fotos):
                        cols[i % 3].image(foto, width=200)

                if documentos:
                    st.markdown("**Documentos:**")
                    for doc in documentos:
                        st.markdown(f"[📄 {os.path.basename(doc)}]({doc})", unsafe_allow_html=True)

                if row.get("texto_ocr"):
                    st.markdown("**Texto OCR extraído:**")
                    st.text(row["texto_ocr"])

                if st.button("Marcar como Analisado", key=f"analisado_{idx}"):
                    df.at[idx, 'status'] = 'Analisado'
                    save_data(df)
                    st.rerun()

    with tab2:
        analisados_checklist()

# Inicialização principal
def main():
    st.sidebar.title("Acesso")
    user_type = st.sidebar.radio("Selecione o tipo de acesso:", ["Corretor", "Administrador"])

    if user_type == "Corretor":
        corretor_interface()
    else:
        admin_panel()

if __name__ == "__main__":
    main()
