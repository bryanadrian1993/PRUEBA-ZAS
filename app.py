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

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

# AUTO-REFRESCO: Actualiza la app cada 10 segundos para rastreo en vivo
if st.session_state.get('viaje_confirmado', False):
    st_autorefresh(interval=10000, key="datarefresh")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwmdasUK1xYWaJjk-ytEAjepFazngTZ91qxhsuN0VZ0OgQmmjyZnD6nOnCNuwIL3HjD/exec"
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
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R

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
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty: return None, None, None, "S/P"

    # ✅ CORRECCIÓN: Limpiar espacios y preparar búsqueda por palabra clave (ej: "CAMIONETA")
    tipo_busqueda = tipo_sol.split(" ")[0].upper().strip()
    
    # ✅ CORRECCIÓN: Búsqueda flexible en columna 'Estado' y 'Tipo_Vehiculo'
    libres = df_c[
        (df_c['Estado'].astype(str).str.upper().str.contains('LIBRE', na=False)) & 
        (df_c['Tipo_Vehiculo'].astype(str).str.upper().str.contains(tipo_busqueda, na=False))
    ]
    
    if libres.empty: return None, None, None, "S/P"
    
    mejor, menor = None, float('inf')
    for _, chofer in libres.iterrows():
        nom = f"{chofer['Nombre']} {chofer['Apellido']}"
        ubi = df_u[df_u['Conductor'].astype(str).str.strip() == nom.strip()]
        if not ubi.empty:
            try:
                # Obtener la última posición registrada
                c_lat = float(ubi.iloc[-1]['Latitud'])
                c_lon = float(ubi.iloc[-1]['Longitud'])
                d = calcular_distancia_real(lat_cli, lon_cli, c_lat, c_lon)
                if d < menor:
                    menor, mejor = d, chofer
            except: continue
            
    if mejor is not None:
        t_original = str(mejor['Telefono']).split(".")[0]
        t_limpio = re.sub(r'\D', '', t_original)
        placa = str(mejor.get('Placa', 'S/P'))
        return f"{mejor['Nombre']} {mejor['Apellido']}", t_limpio, str(mejor['Foto_Perfil']), placa
    
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat_actual, lon_actual = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (LAT_BASE, LON_BASE)

if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("Tu Nombre:")
        celular_input = st.text_input("WhatsApp (Sin código)")
        ref_cli = st.text_input("Referencia / Dirección:")
        tipo_veh = st.selectbox("¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD")

    if enviar and nombre_cli and ref_cli:
        with st.spinner("🔄 Buscando unidad..."):
            chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
            if chof:
                id_v = f"TX-{random.randint(1000, 9999)}"
                mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                enviar_datos_a_sheets({"accion": "registrar_pedido", "cliente": nombre_cli, "referencia": ref_cli, "conductor": chof, "id_viaje": id_v, "mapa": mapa_url})
                st.session_state.viaje_confirmado = True
                st.session_state.datos_pedido = {"chof": chof, "t_chof": t_chof, "foto": foto_chof, "placa": placa, "id": id_v, "mapa": mapa_url, "lat_cli": lat_actual, "lon_cli": lon_actual, "nombre": nombre_cli, "ref": ref_cli}
                st.rerun()
            else:
                st.error("❌ No hay unidades libres de este tipo en este momento.")

if st.session_state.viaje_confirmado:
    dp = st.session_state.datos_pedido
    try:
        df_u = cargar_datos("UBICACIONES")
        pos_t = df_u[df_u['Conductor'].astype(str).str.strip() == dp['chof'].strip()].iloc[-1]
        lat_t, lon_t = float(pos_t['Latitud']), float(pos_t['Longitud'])

        st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 ID: {dp["id"]}</span></div>', unsafe_allow_html=True)
        st.success(f"✅ Conductor **{dp['chof']}** asignado.")

        msg_wa = urllib.parse.quote(f"🚖 *PEDIDO*\n🆔 *ID:* {dp['id']}\n👤 Cliente: {dp['nombre']}\n📍 Ref: {dp['ref']}\n🗺️ *Mapa:* {dp['mapa']}")
        st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:20px;border-radius:10px;margin-bottom:10px;">📲 CONTACTAR CONDUCTOR</a>', unsafe_allow_html=True)

        if st.button("❌ NUEVO PEDIDO"):
            st.session_state.viaje_confirmado = False
            st.rerun()

        dist_km = calcular_distancia_real(lat_t, lon_t, dp['lat_cli'], dp['lon_cli'])
        st.info(f"📍 El conductor está a {dist_km:.2f} km de tu ubicación.")
        
        # Mapa con PyDeck
        puntos = pd.DataFrame([
            {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [0, 255, 0], "info": "TÚ"},
            {"lon": lon_t, "lat": lat_t, "color": [255, 0, 0], "info": dp['chof']}
        ])
        st.pydeck_chart(pdk.Deck(
            initial_view_state=pdk.ViewState(latitude=lat_t, longitude=lon_t, zoom=14),
            layers=[pdk.Layer("ScatterplotLayer", data=puntos, get_position="[lon, lat]", get_color="color", get_radius=50)]
        ))

    except Exception: st.info("⌛ Esperando actualización de GPS del conductor...")

st.markdown('<div class="footer"><p>© 2025 Taxi Seguro Global</p></div>', unsafe_allow_html=True)
