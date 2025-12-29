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

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

# --- 🔄 GESTIÓN DE ESTADO (Para que el mapa no desaparezca) ---
if 'viaje_confirmado' not in st.session_state: st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES TÉCNICAS ---

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    """Obtiene las coordenadas reales de las calles usando OSRM."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data['routes'][0]['geometry']['coordinates']
    except:
        return [[lon1, lat1], [lon2, lat2]] # Respaldo línea recta

def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Limpieza contra KeyError
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

# 1. Formulario inicial (Solo se ve si no hay pedido activo)
if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad más cercana..."):
            chof, t_chof, foto_chof = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            if chof:
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {
                    "chof": chof, "t_chof": t_chof, "foto": foto_chof,
                    "id": f"TX-{random.randint(1000, 9999)}",
                    "lat_cli": lat_actual, "lon_cli": lon_actual,
                    "nombre_cli": nombre_cli, "ref": ref_cli
                }
                st.rerun()
            else: st.error("❌ No hay conductores disponibles de este tipo.")

# 2. Panel de Seguimiento (Persistente)
if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    
    try:
        df_u = cargar_datos("UBICACIONES")
        pos_t = df_u[df_u['Conductor'] == dp['chof']].iloc[-1]
        lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

        st.markdown('<div class="step-header">📍 RASTREO POR CARRETERA</div>', unsafe_allow_html=True)
        
        # OBTENEMOS LA RUTA REAL
        camino_osrm = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)

        

        # Mapa Pydeck Estilo Google Maps 3D
        st.pydeck_chart(pdk.Deck(
            map_style='road',
            initial_view_state=pdk.ViewState(
                latitude=(dp['lat_cli'] + lat_t) / 2, 
                longitude=(dp['lon_cli'] + lon_t) / 2, 
                zoom=15, pitch=45
            ),
            layers=[
                # Capa de camino real
                pdk.Layer(
                    "PathLayer",
                    data=[{"path": camino_osrm}],
                    get_path="path",
                    get_color=[70, 130, 180, 200],
                    get_width=12,
                    width_min_pixels=5
                ),
                # Capa de puntos (Tú y el Taxi)
                pdk.Layer(
                    "ScatterplotLayer",
                    data=[
                        {"pos": [dp['lon_cli'], dp['lat_cli']], "col": [0, 200, 0], "tag": "Tú"},
                        {"pos": [lon_t, lat_t], "col": [255, 0, 0], "tag": "Taxi"}
                    ],
                    get_position="pos",
                    get_color="col",
                    get_radius=250,
                    pickable=True
                )
            ],
            tooltip={"text": "{tag}"}
        ))

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🔄 ACTUALIZAR MAPA"): st.rerun() #
        with col_b2:
            if st.button("❌ NUEVO PEDIDO"):
                st.session_state.viaje_confirmado = False
                st.rerun()

        st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
        st.success(f"✅ **{dp['chof']}** sigue la ruta hacia ti.")
        
        msg_wa = urllib.parse.quote(f"🚖 *PEDIDO*\n🆔 *ID:* {dp['id']}\n👤 Cliente: {dp['nombre_cli']}\n📍 Ref: {dp['ref']}")
        st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;">📲 CONTACTAR CONDUCTOR</a>', unsafe_allow_html=True)
            
    except Exception: st.info("⌛ Esperando señal GPS del taxi para trazar la ruta...")

st.markdown('<div class="footer"><p>© 2025 Taxi Seguro Global</p></div>', unsafe_allow_html=True)
