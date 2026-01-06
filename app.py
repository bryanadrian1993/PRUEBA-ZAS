import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import json
import random
import math
import io
import base64
import pytz
from timezonefinder import TimezoneFinder
from datetime import datetime
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACION ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- ESTILOS ---
st.markdown("""
<style>
.main-title { font-size: 40px; font-weight: bold; text-align: center; margin-bottom: 0; }
.sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-bottom: 20px; }
.stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- ESTADO ---
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
        dlat = math.radians(lat2-lat1)
        dlon = math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except:
        return 0.0

def obtener_hora_gps(lat, lon):
    # Funcion simplificada
    default = datetime.now(pytz.timezone('America/Guayaquil')).strftime("%Y-%m-%d %H:%M:%S")
    if not lat or not lon:
        return default
    try:
        tf = TimezoneFinder()
        zona = tf.timezone_at(lng=float(lon), lat=float(lat))
        if zona:
            return datetime.now(pytz.timezone(zona)).strftime("%Y-%m-%d %H:%M:%S")
        return default
    except:
        return default

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
        req = urllib.request.Request(f"{URL_SCRIPT}?{params}")
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except:
        return "Error"

def obtener_chofer(lat_cli, lon_cli, tipo):
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    if df_c.empty or df_u.empty:
        return None, None, None, "S/P"

    # Filtrar
    tipo_b = tipo.split(" ")[0].upper()
    libres = df_c[df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE']
    
    if len(libres) == 0:
        libres = df_c.copy()
        
    if 'TIPO_VEHICULO' in libres.columns:
        filtro_tipo = libres[libres['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b, na=False)]
        if len(filtro_tipo) > 0:
            libres = filtro_tipo

    # Columnas
    col_cond = next((c for c in df_u.columns if "CONDUCTOR" in c.upper()), None)
    col_lat = next((c for c in df_u.columns if "LAT" in c.upper()), None)
    col_lon = next((c for c in df_u.columns if "LON" in c.upper()), None)

    if not col_cond or not col_lat or not col_lon:
        return None, None, None, "S/P"

    df_u['KEY'] = df_u[col_cond].astype(str).str.strip().str.upper()
    
    mejor = None
    dist_min = float('inf')

    for _, ch in libres.iterrows():
        n = str(ch.get('NOMBRE', '')).replace('nan','').strip()
        a = str(ch.get('APELLIDO', '')).replace('nan','').strip()
        nombre = f"{n} {a}".strip().upper()
        
        pos = df_u[df_u['KEY'] == nombre]
        if not pos.empty:
            try:
                lat_c = float(pos.iloc[-1][col_lat])
                lon_c = float(pos.iloc[-1][col_lon])
                d = calcular_distancia_real(lat_cli, lon_cli, lat_c, lon_c)
                if d < dist_min:
                    dist_min = d
                    mejor = ch
            except:
                pass
                
    if mejor is not None:
        t = str(mejor.get('TELEFONO', '0')).split('.')[0]
        f = str(mejor.get('FOTO_PERFIL', ''))
        p = str(mejor.get('PLACA', ''))
        return mejor, t, f, p
        
    return None, None, None, "S/P"

# --- INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

loc = get_geolocation()
lat, lon = None, None

if loc and 'coords' in loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
    st.session_state.ultima_lat = lat
    st.session_state.ultima_lon = lon
    st.success(f"✅ GPS: {lat:.5f}, {lon:.5f}")
elif st.session_state.ultima_lat:
    lat = st.session_state.ultima_lat
    lon = st.session_state.ultima_lon
    st.info(f"📍 GPS Cache: {lat:.5f}, {lon:.5f}")
else:
    st.warning("📡 Buscando señal GPS...")

# PANTALLAS
if not st.session_state.viaje_confirmado:
    # FORMULARIO
    with st.form("pedido"):
        st.write("📝 **Solicitud de Viaje**")
        nom = st.text_input("Tu Nombre:")
        cel = st.text_input("WhatsApp:")
        ref = st.text_input("Referencia/Dirección:")
        tipo = st.selectbox("Vehículo:", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        btn = st.form_submit_button("SOLICITAR")
    
    if btn:
        if not nom or not ref or not lat:
            st.error("❌ Faltan datos o GPS")
        else:
            with st.spinner("Buscando unidad..."):
                chof, tel, foto, placa = obtener_chofer(lat, lon, tipo)
                
                if chof is not None:
                    n = str(chof.get('NOMBRE','')).strip()
                    a = str(chof.get('APELLIDO','')).strip()
                    n_chof = f"{n} {a}".upper()
                    id_v = f"TX-{random.randint(1000,9999)}"
                    mapa = f"http://maps.google.com/?q={lat},{lon}"
                    
                    st.session_state.datos_pedido = {
                        "chof": n_chof, "tel": tel, "foto": foto, "placa": placa,
                        "id": id_v, "mapa": mapa, "nom": nom, "ref": ref
                    }
                    st.session_state.viaje_confirmado = True
                    
                    # ENVIAR DATOS
                    enviar_datos_a_sheets({
                        "accion": "registrar_pedido",
                        "id_viaje": id_v, "cliente": nom,
                        "Fecha": obtener_hora_gps(lat, lon),
                        "tel_cliente": cel, "referencia": ref,
                        "conductor": n_chof, "tel_conductor": tel, "mapa": mapa
                    })
                    enviar_datos_a_sheets({
                        "accion": "cambiar_estado", "conductor": n_chof, "estado": "OCUPADO"
                    })
                    st.rerun()
                else:
                    st.error("⚠️ No hay unidades disponibles")

else:
    # VIAJE ACTIVO
    dp = st.session_state.datos_pedido
    st.info(f"🆔 VIAJE: {dp['id']}")
    
    col1, col2 = st.columns([1,2])
    with col1:
        try:
            if len(dp['foto']) > 50:
                img = base64.b64decode(dp['foto'])
                st.image(io.BytesIO(img), width=100)
            else:
                st.write("👤")
        except:
            st.write("👤")
            
    with col2:
        st.success(f"🚖 {dp['chof']}")
        st.write(f"🚗 {dp['placa']}")
    
    link = f"https://api.whatsapp.com/send?phone={dp['tel']}&text=Hola%20soy%20{dp['nom']}%20ubicacion:{dp['mapa']}"
    st.markdown(f"[📲 ABRIR WHATSAPP]({link})")
    
    if st.button("❌ CANCELAR / NUEVO"):
        st.session_state.viaje_confirmado = False
        st.rerun()
