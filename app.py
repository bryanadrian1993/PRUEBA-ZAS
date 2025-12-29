import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import random
import math
import re
import pydeck as pdk

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

# --- 🔄 GESTIÓN DE ESTADO (PERSISTENCIA) ---
# Esto evita que el mapa desaparezca al actualizar
if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Limpieza de columnas
        return df
    except: return pd.DataFrame()

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
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
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

# Mostrar formulario solo si no hay un viaje activo
if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad..."):
            chof, t_chof, foto_chof = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            if chof:
                # Guardamos todo en la sesión para que no se borre
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {
                    "chof": chof, "t_chof": t_chof, "foto": foto_chof,
                    "id": f"TX-{random.randint(1000, 9999)}",
                    "lat_cli": lat_actual, "lon_cli": lon_actual,
                    "nombre_cli": nombre_cli, "ref": ref_cli
                }
                st.rerun()
            else: st.error("❌ No hay unidades libres.")

# --- 🗺️ MOSTRAR MAPA (Solo si el viaje está confirmado) ---
if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    
    try:
        df_u = cargar_datos("UBICACIONES")
        pos_t = df_u[df_u['Conductor'] == dp['chof']].iloc[-1]
        lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

        st.markdown('<div class="step-header">📍 RASTREO EN TIEMPO REAL</div>', unsafe_allow_html=True)
        
        # Mapa Pydeck Estilo Google Maps
        puntos_df = pd.DataFrame([
            {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [0, 200, 0, 255], "tag": "Tú"},
            {"lon": lon_t, "lat": lat_t, "color": [255, 0, 0, 255], "tag": f"Taxi: {dp['chof']}"}
        ])

        st.pydeck_chart(pdk.Deck(
            map_style='road',
            initial_view_state=pdk.ViewState(latitude=(dp['lat_cli']+lat_t)/2, longitude=(dp['lon_cli']+lon_t)/2, zoom=15, pitch=45),
            layers=[
                pdk.Layer("LineLayer", data=[{"s": [dp['lon_cli'], dp['lat_cli']], "e": [lon_t, lat_t]}], get_source_position="s", get_target_position="e", get_color=[70, 130, 180, 200], get_width=10),
                pdk.Layer("ScatterplotLayer", data=puntos_df, get_position="[lon, lat]", get_color="color", get_radius=250, pickable=True)
            ],
            tooltip={"text": "{tag}"}
        ))

        # El botón ahora funciona correctamente
        if st.button("🔄 ACTUALIZAR MOVIMIENTO"): st.rerun()

        st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
        st.success(f"✅ Conductor: **{dp['chof']}** en camino.")
        
        if st.button("❌ CANCELAR / NUEVO PEDIDO"):
            st.session_state.viaje_confirmado = False
            st.rerun()
            
    except Exception: st.info("⌛ Esperando señal GPS del taxi...")
