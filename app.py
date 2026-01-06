import pytz
from timezonefinder import TimezoneFinder
from datetime import datetime
import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
import urllib.parse
import urllib.request
import json
import random
import math
import io
import base64
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .gps-status { background: linear-gradient(90deg, #4CAF50, #8BC34A); color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO ---
if 'viaje_confirmado' not in st.session_state:
    st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state:
    st.session_state.datos_pedido = {}
if 'ultima_lat' not in st.session_state:
    st.session_state.ultima_lat = None
if 'ultima_lon' not in st.session_state:
    st.session_state.ultima_lon = None

# --- FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    try:
        R = 6371
        dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except:
        return 0.0

def obtener_hora_gps(latitud, longitud):
    try:
        if not latitud or not longitud:
            return datetime.now(pytz.timezone('America/Guayaquil')).strftime("%Y-%m-%d %H:%M:%S")
        
        tf = TimezoneFinder()
        zona = tf.timezone_at(lng=float(longitud), lat=float(latitud))
        
        if zona:
            return datetime.now(pytz.timezone(zona)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return datetime.now(pytz.timezone('America/Guayaquil')).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper()
        return df
    except:
        return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_completa = f"{URL_SCRIPT}?{params}"
        req = urllib.request.Request(url_completa)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except:
        return "Error"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty:
        return None, None, None, "S/P"
    
    tipo_b = tipo_sol.split(" ")[0].upper()
    libres = df_c[df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE']
    
    if len(libres) == 0:
        libres = df_c.copy()
    
    if 'TIPO_VEHICULO' in libres.columns:
        libres = libres[libres['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b, na=False)]
        if len(libres) == 0:
            libres = df_c.copy()

    col_cond_u = next((c for c in df_u.columns if "CONDUCTOR" in c.upper()), None)
    col_lat_u = next((c for c in df_u.columns if "LAT" in c.upper()), None)
    col_lon_u = next((c for c in df_u.columns if "LON" in c.upper()), None)

    if not (col_cond_u and col_lat_u and col_lon_u):
        return None, None, None, "S/P"

    df_u['KEY_CLEAN'] = df_u[col_cond_u].astype(str).str.strip().str.upper()
    mejor_chofer = None
    menor_distancia = float('inf')

    for idx, chofer in libres.iterrows():
        n = str(chofer.get('NOMBRE', '')).replace('nan','').strip()
        a = str(chofer.get('APELLIDO', '')).replace('nan','').strip()
        nombre_completo = f"{n} {a}".strip().upper()
        
        ubi = df_u[df_u['KEY_CLEAN'] == nombre_completo]
        if not ubi.empty:
            try:
                lat_cond = float(ubi.iloc[-1][col_lat_u])
                lon_cond = float(ubi.iloc[-1][col_lon_u])
                d = calcular_distancia_real(lat_cli, lon_cli, lat_cond, lon_cond)
                if d < menor_distancia:
                    menor_distancia = d
                    mejor_chofer = chofer
            except:
                continue

    if mejor_chofer is not None:
        t = str(mejor_chofer.get('TELEFONO', '0000000000')).split('.')[0].strip()
        foto = str(mejor_chofer.get('FOTO_PERFIL', 'SIN_FOTO'))
        placa = str(mejor_chofer.get('PLACA', 'S/P'))
        return mejor_chofer, t, foto, placa
    
    return None, None, None, "S/P"

# --- INTERFAZ ---

st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

# GPS
loc = get_geolocation()
lat_actual, lon_actual = None, None

if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
    st.session_state.ultima_lat = lat_actual
    st.session_state.ultima_lon = lon_actual
    st.markdown(f'<div class="gps-status">✅ GPS ACTIVO: {lat_actual:.5f}, {lon_actual:.5f}</div>', unsafe_allow_html=True)
else:
    if st.session_state.ultima_lat:
        lat_actual = st.session_state.ultima_lat
        lon_actual = st.session_state.ultima_lon
        st.info(f"📍 Última ubicación: {lat_actual:.5f}, {lon_actual:.5f}")
    else:
        st.warning("⚠️ Esperando señal GPS...")

# LÓGICA PRINCIPAL
if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        st.markdown('<div class="step-header">📝 Completa tu solicitud:</div>', unsafe_allow_html=True)
        nombre_cli = st.text_input("👤 Tu Nombre:", key="nombre_input")
        celular_input = st.text_input("📱 WhatsApp:", key="celular_input")
        ref_cli = st.text_input("📍 Referencia:", key="ref_input")
        tipo_veh = st.selectbox("🚗 Tipo:", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD", use_container_width=True)

    if enviar:
        if not nombre_cli or not ref_cli or not lat_actual:
            st.error("❌ Faltan datos o GPS.")
        else:
            with st.spinner("🚀 Buscando..."):
                chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
                
                if chof is not None:
                    n_clean = str(chof.get('NOMBRE', '')).replace('nan','').strip()
                    a_clean = str(chof.get('APELLIDO', '')).replace('nan','').strip()
                    nombre_chof = f"{n_clean} {a_clean}".strip().upper()
                    id_v = f"TX-{random.randint(1000, 9999)}"
                    mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"

                    st.session_state.datos_pedido = {
                        "chof": nombre_chof, "t_chof": t_chof, "foto": foto_chof, "placa": placa,
                        "id": id_v, "mapa": mapa_url, "lat_cli": lat_actual, "lon_cli": lon_actual,
                        "nombre": nombre_cli, "ref": ref_cli
                    }
                    st.session_state.viaje_confirmado = True
                    
                    try:
                        enviar_datos_a_sheets({
                            "accion": "registrar_pedido",
                            "id_viaje": id_v, "cliente": nombre_cli,
                            "Fecha": obtener_hora_gps(lat_actual, lon_actual),
                            "tel_cliente": celular_input, "referencia": ref_cli,
                            "conductor": nombre_chof, "tel_conductor": t_chof, "mapa": mapa_url
                        })
                        enviar_datos_a_sheets({
                            "accion": "cambiar_estado", "conductor": nombre_chof, "estado": "OCUPADO"
                        })
                    except:
                        pass
                    st.rerun()
                else:
                    st.error("⚠️ No hay conductores disponibles.")

else:
    # PANTALLA VIAJE
    dp = st.session_state.datos_pedido
    st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 VIAJE: {dp["id"]}</span></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            img_bytes = base64.b64decode(dp.get('foto', ''))
            st.image(io.BytesIO(img_bytes), width=150)
        except:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)

    st.success(f"✅ Conductor: **{dp['chof']}**")
    st.info(f"🚗 Vehículo: **{dp['placa']}**")
    
    msg_wa = urllib.parse.quote(f"🚖 *HOLA*\nSoy {dp['nombre']}\n🆔 {dp['id']}\n📍 {dp['ref']}\n🗺️ {dp['mapa']}")
    st.markdown(f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" target="_blank" style="background-color:#25D366;color:white;padding:15px;text-align:center;display:block;text-decoration:none;font-weight:bold;font-size:18px;border-radius:10px;margin:15px 0;">📲 PEDIR POR WHATSAPP</a>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ CANCELAR"):
            st.session_state.viaje_confirmado = False
            st.rerun()
    with c2:
        if st.button("🔄 NUEVO"):
            st.session_state.viaje_confirmado = False
            st.rerun()
            
st.markdown('<div class="footer">soporte@taxiseguro.com</div>', unsafe_allow_html=True)
