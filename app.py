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

# --- 🛠️ FUNCIONES ---

def obtener_ruta_segura(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}] #

def cargar_datos(hoja):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() #
        return df
    except: return pd.DataFrame()

# --- 📱 INTERFAZ ---
st.markdown('<h1 style="text-align:center;">🚖 TAXI SEGURO</h1>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular = st.text_input("WhatsApp")
        ref_cli = st.text_input("Referencia")
        tipo_veh = st.selectbox("Vehículo", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        if st.form_submit_button("🚖 SOLICITAR"):
            # Lógica de búsqueda simplificada
            st.session_state.viaje_confirmado = True
            st.session_state.datos_pedido = {"chof": "ADRIAN", "t_chof": "593", "id": "TX-123", "lat_cli": lat_actual, "lon_cli": lon_actual}
            st.rerun()

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    # Coordenadas de prueba para el taxi (puedes vincular a tu Excel)
    lat_t, lon_t = lat_actual + 0.005, lon_actual + 0.005 
    
    ruta_data = obtener_ruta_segura(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)

    # MAPA CON ESTILO VOYAGER (Gratis y muy real)
    st.pydeck_chart(pdk.Deck(
        map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', 
        initial_view_state=pdk.ViewState(
            latitude=(dp['lat_cli']+lat_t)/2, 
            longitude=(dp['lon_cli']+lon_t)/2, 
            zoom=14,
            pitch=0
        ),
        layers=[
            pdk.Layer(
                "PathLayer", 
                data=ruta_data, 
                get_path="path", 
                get_color=[0, 150, 255], 
                get_width=15
            ),
            pdk.Layer(
                "ScatterplotLayer", 
                data=[{"p": [dp['lon_cli'], dp['lat_cli']], "c": [0, 200, 0]}, {"p": [lon_t, lat_t], "c": [255, 0, 0]}], 
                get_position="p", 
                get_color="c", 
                get_radius=200
            )
        ]
    ))
    
    if st.button("❌ NUEVO PEDIDO"):
        st.session_state.viaje_confirmado = False
        st.rerun()
