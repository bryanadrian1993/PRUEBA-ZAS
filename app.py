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
from streamlit_autorefresh import st_autorefresh
import io
import base64
from PIL import Image

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# AUTO-REFRESCO: Vital para detectar el GPS y actualizar el mapa en vivo
st_autorefresh(interval=5000, key="gps_refresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

# Inicialización de estados
if 'viaje_confirmado' not in st.session_state: 
    st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: 
    st.session_state.datos_pedido = {}

# 🎨 ESTILOS CSS (Tu diseño original)
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    try:
        R = 6371
        dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except: return 0.0

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}]

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper()
        return df
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}", timeout=10) as response:
            return response.read().decode('utf-8')
    except: return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    if df_c.empty or df_u.empty: return None, None, None, "S/P"
    
    tipo_b = tipo_sol.split(" ")[0].upper()
    libres = df_c[(df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE') & 
                  (df_c['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b))]

    if 'DEUDA' in libres.columns:
        libres = libres[pd.to_numeric(libres['DEUDA'], errors='coerce').fillna(0) < 10.00]
    if libres.empty: return None, None, None, "S/P"

    # Normalización de búsqueda en Ubicaciones
    col_cond_u = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
    col_lat_u = next((c for c in df_u.columns if "LAT" in c), None)
    col_lon_u = next((c for c in df_u.columns if "LON" in c), None)
    if not col_cond_u: return None, None, None, "Error Ubi"

    df_u['KEY'] = df_u[col_cond_u].astype(str).str.strip().str.upper()
    mejor, menor = None, float('inf')

    for _, conductor in libres.iterrows():
        n = str(conductor.get('NOMBRE', '')).replace('nan','').strip()
        a = str(conductor.get('APELLIDO', '')).replace('nan','').strip()
        full_name = f"{n} {a}".strip().upper()

        ubi = df_u[df_u['KEY'] == full_name]
        if not ubi.empty:
            try:
                lt, ln = float(ubi.iloc[-1][col_lat_u]), float(ubi.iloc[-1][col_lon_u])
                d = calcular_distancia_real(lat_cli, lon_cli, lt, ln)
                if d < 10000 and d < menor: menor, mejor = d, conductor
            except: continue

    if mejor is not None:
        t = str(mejor.get('TELEFONO', '0000000000')).split('.')[0].strip()
        f = str(mejor.get('FOTO_PERFIL', 'SIN_FOTO'))
        p = str(mejor.get('PLACA', 'S/P'))
        return mejor, t, f, p
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

if not st.session_state.viaje_confirmado:
    if loc: st.success(f"📍 Tu Ubicación: {lat_actual:.5f}, {lon_actual:.5f}")
    else: st.warning("⚠️ Esperando señal GPS...")

    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular_input = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad cercana..."):
            chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            
            if chof is not None:
                n_c = str(chof.get('NOMBRE', '')).replace('nan','').strip()
                a_c = str(chof.get('APELLIDO', '')).replace('nan','').strip()
                nombre_chof = f"{n_c} {a_c}".strip().upper()
                id_v = f"TX-{random.randint(1000, 9999)}"
                mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                
                # Registro y cambio de estado
                res = enviar_datos_a_sheets({
                    "accion": "registrar_pedido", "id_viaje": id_v, "cliente": nombre_cli,
                    "tel_cliente": celular_input, "referencia": ref_cli, "conductor": nombre_chof,
                    "tel_conductor": t_chof, "mapa": mapa_url
                })
                
                if res != "Error":
                    enviar_datos_a_sheets({"accion": "cambiar_estado", "conductor": nombre_chof, "estado": "OCUPADO"})
                    
                    # Transición Crítica
                    st.session_state.datos_pedido = {
                        "chof": nombre_chof, "t_chof": t_chof, "foto": foto_chof, 
                        "placa": placa, "id": id_v, "mapa": mapa_url, 
                        "lat_cli": lat_actual, "lon_cli": lon_actual, 
                        "nombre": nombre_cli, "ref": ref_cli
                    }
                    st.session_state.viaje_confirmado = True
                    st.rerun()
            else:
                 st.warning("⚠️ No hay conductores disponibles cerca de tu ubicación.")

else:
    # --- PANTALLA POSTERIOR (WHATSAPP Y MAPA) ---
    dp = st.session_state.datos_pedido
    st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if dp['foto'] and len(str(dp['foto'])) > 100:
            try: st.image(io.BytesIO(base64.b64decode(dp['foto'])), width=150)
            except: st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
        else: st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)

    st.success(f"✅ Conductor **{dp['chof']}** asignado.")
    st.info(f"🚗 Vehículo: {dp['placa']}")
    
    msg_wa = urllib.parse.quote(f"🚖 *HOLA TAXI SEGURO*\nSoy {dp['nombre']}\n🆔 ID Viaje: {dp['id']}\n📍 Estoy en: {dp['ref']}\n🗺️ Ver mapa: {dp['mapa']}")
    st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;">📲 CHATEAR CON CONDUCTOR</a>', unsafe_allow_html=True)

    if st.button("❌ CANCELAR / NUEVO PEDIDO"):
        st.session_state.viaje_confirmado = False
        st.rerun()

    st.write("---")

    try:
        df_u = cargar_datos("UBICACIONES")
        col_c = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
        col_la = next((c for c in df_u.columns if "LAT" in c), None)
        col_lo = next((c for c in df_u.columns if "LON" in c), None)
        
        if col_c:
            df_u['KEY'] = df_u[col_c].astype(str).str.strip().str.upper()
            pos = df_u[df_u['KEY'] == str(dp['chof']).upper()].iloc[-1]
            lt, ln = float(pos[col_la]), float(pos[col_lo])
            
            dist = calcular_distancia_real(lt, ln, dp['lat_cli'], dp['lon_cli'])
            eta = round((dist / 30) * 60) + 2 
            st.markdown(f'<div class="eta-box">🕒 Llega en aprox. {eta} min ({dist:.2f} km)</div>', unsafe_allow_html=True)
            
            camino = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], ln, lt)
            puntos = pd.DataFrame([
                {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [34, 139, 34], "info": "TÚ"},
                {"lon": ln, "lat": lt, "color": [255, 0, 0], "info": f"TAXI {dp['placa']}"}
            ])

            st.pydeck_chart(pdk.Deck(
                map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                initial_view_state=pdk.ViewState(latitude=(lt + dp['lat_cli'])/2, longitude=(ln + dp['lon_cli'])/2, zoom=14),
                layers=[
                    pdk.Layer("PathLayer", data=camino, get_path="path", get_color=[255, 0, 0], get_width=5),
                    pdk.Layer("ScatterplotLayer", data=puntos, get_position="[lon, lat]", get_fill_color="color", get_radius=25)
                ]
            ))
        if st.button("🔄 ACTUALIZAR MAPA"): st.rerun()
    except: st.warning("📡 Buscando señal del conductor...")

st.markdown('<div class="footer">📩 contacto: soporte@taxiseguro.com</div>', unsafe_allow_html=True)
