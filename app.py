import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import json
import random
import math
import re
import pydeck as pdk

# --- ⚙️ CONFIGURACIÓN ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    """Obtiene el trayecto real por calles."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}] # Respaldo línea recta

def cargar_datos(hoja):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Limpieza de columnas
        return df
    except: return pd.DataFrame()

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c, df_u = cargar_datos("CHOFERES"), cargar_datos("UBICACIONES")
    if df_c.empty or df_u.empty: return None, None, None
    tipo_b = tipo_sol.split(" ")[0].upper()
    libres = df_c[(df_c['Estado'].astype(str).str.upper() == 'LIBRE') & (df_c['Tipo_Vehiculo'].astype(str).str.upper().str.contains(tipo_b))]
    if libres.empty: return None, None, None
    mejor, menor = None, float('inf')
    for _, chofer in libres.iterrows():
        nom = f"{chofer['Nombre']} {chofer['Apellido']}"
        ubi = df_u[df_u['Conductor'] == nom]
        if not ubi.empty:
            d = math.sqrt((lat_cli-float(ubi.iloc[-1]['Latitud']))**2 + (lon_cli-float(ubi.iloc[-1]['Longitud']))**2)
            if d < menor: menor, mejor = d, chofer
    if mejor is not None:
        t = str(mejor['Telefono']).split(".")[0]
        if t.startswith("09"): t = "593" + t[1:]
        return f"{mejor['Nombre']} {mejor['Apellido']}", t, str(mejor['Foto_Perfil'])
    return None, None, None

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular = st.text_input("WhatsApp")
        ref_cli = st.text_input("Referencia")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad..."):
            chof, t_chof, foto = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            if chof:
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {
                    "chof": chof, "t_chof": t_chof, "id": f"TX-{random.randint(1000, 9999)}",
                    "lat_cli": lat_actual, "lon_cli": lon_actual, "nombre": nombre_cli, "ref": ref_cli
                }
                st.rerun()

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    df_u = cargar_datos("UBICACIONES")
    pos_t = df_u[df_u['Conductor'] == dp['chof']].iloc[-1]
    lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])
    
    ruta_data = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)

    # --- DATOS DE ICONOS: PERSONA Y TAXI AMARILLO ---
    ICON_DATA = [
        {
            "pos": [dp['lon_cli'], dp['lat_cli']],
            "icon_url": "https://img.icons8.com/fluency/96/person-male.png", # Icono de Persona
            "label": "Tú"
        },
        {
            "pos": [lon_t, lat_t],
            "icon_url": "https://img.icons8.com/color/96/taxi.png", # Icono de Taxi Amarillo
            "label": f"Taxi: {dp['chof']}"
        }
    ]

    st.pydeck_chart(pdk.Deck(
        map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
        initial_view_state=pdk.ViewState(latitude=(dp['lat_cli']+lat_t)/2, longitude=(dp['lon_cli']+lon_t)/2, zoom=15, pitch=0),
        layers=[
            pdk.Layer("PathLayer", data=ruta_data, get_path="path", get_color=[0, 150, 255], get_width=10),
            pdk.Layer(
                "IconLayer",
                data=ICON_DATA,
                get_icon='icon_url',
                get_size=4,
                size_scale=15, # Tamaño refinado
                get_position='pos',
                pickable=True
            )
        ],
        tooltip={"text": "{label}"}
    ))
    
    if st.button("🔄 ACTUALIZAR MAPA"): st.rerun()
    if st.button("❌ CANCELAR PEDIDO"):
        st.session_state.viaje_confirmado = False
        st.rerun()
