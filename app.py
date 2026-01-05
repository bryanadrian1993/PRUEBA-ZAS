import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import json
import random
import math
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
import io
import base64

# --- ⚙️ CONFIGURACIÓN ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- SESSION STATE ---
if 'viaje_confirmado' not in st.session_state:
    st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state:
    st.session_state.datos_pedido = {}
if 'lat_guardada' not in st.session_state:
    st.session_state.lat_guardada = None
    st.session_state.lon_guardada = None

# --- ESTILOS ---
st.markdown("""
<style>
.main-title { font-size: 40px; font-weight: bold; text-align: center; }
.sub-title { font-size: 25px; text-align: center; color: #E91E63; }
.id-badge { background:#F0F2F6;padding:5px 15px;border-radius:20px;font-weight:bold; }
.eta-box { background:#FFF3E0;padding:15px;border-radius:10px;font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def calcular_distancia_real(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * R

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.upper().str.strip()
        return df
    except:
        return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}", timeout=10) as r:
            return r.read().decode()
    except:
        return "Error"

# --- INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

# --- GPS (SE GUARDA UNA SOLA VEZ) ---
loc = get_geolocation()

if loc and 'coords' in loc and st.session_state.lat_guardada is None:
    st.session_state.lat_guardada = loc['coords']['latitude']
    st.session_state.lon_guardada = loc['coords']['longitude']

lat_actual = st.session_state.lat_guardada
lon_actual = st.session_state.lon_guardada

if lat_actual:
    st.success("📍 Ubicación detectada")
else:
    st.warning("⚠️ Esperando GPS...")

# ======================
# PANTALLA 1 – PEDIDO
# ======================
if not st.session_state.viaje_confirmado:

    with st.form("pedido"):
        nombre = st.text_input("Tu nombre")
        ref = st.text_input("Referencia")
        tipo = st.selectbox("Vehículo", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 PEDIR UNIDAD")

    if enviar:
        if not (nombre and ref and lat_actual):
            st.error("Faltan datos o GPS")
        else:
            id_v = f"TX-{random.randint(1000,9999)}"
            mapa = f"https://maps.google.com?q={lat_actual},{lon_actual}"

            res = enviar_datos_a_sheets({
                "accion": "registrar_pedido",
                "id_viaje": id_v,
                "cliente": nombre,
                "referencia": ref,
                "mapa": mapa
            })

            if res != "Error":
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {
                    "id": id_v,
                    "nombre": nombre,
                    "ref": ref,
                    "lat": lat_actual,
                    "lon": lon_actual,
                    "mapa": mapa
                }
                st.rerun()

# ======================
# PANTALLA 2 – SEGUIMIENTO
# ======================
else:
    st_autorefresh(interval=5000, key="seguimiento_refresh")

    dp = st.session_state.datos_pedido

    st.markdown(f'<div class="id-badge">🆔 {dp["id"]}</div>', unsafe_allow_html=True)
    st.success("✅ Conductor asignado")
    st.markdown(f"[📍 Ver ubicación]({dp['mapa']})")

    if st.button("❌ CANCELAR / NUEVO PEDIDO"):
        st.session_state.viaje_confirmado = False
        st.session_state.lat_guardada = None
        st.session_state.lon_guardada = None
        st.rerun()

st.markdown("<center>📩 soporte@taxiseguro.com</center>", unsafe_allow_html=True)
